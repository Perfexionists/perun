""" The Pin engine implementation.
"""

import os
import subprocess
from jinja2 import select_autoescape
from typing import List, Dict, Union, Optional, Generator, Any

import perun.collect.trace.collect_engine as engine
import perun.collect.trace.pin.scan_binary as scan_binary
from perun.templates import factory as templates
from perun.collect.trace.values import check
from perun.collect.trace.pin.parse import ProgramData
from perun.collect.trace.pin.parse import (
    PinDynamicOutputParser,
    PinStaticOutputParser,
    PinTimeOutputParser,
    PinInstructionOutputParser,
    PinMemoryOutputParser,
)
from perun.logic.pcs import get_tmp_directory
from perun.utils.external.commands import run_safely_external_command
from perun.utils.log import msg_to_stdout
from perun.utils.exceptions import (
    InvalidBinaryException,
    PinInvalidPinRoot,
    PinBinaryInstrumentationFailed,
    InvalidParameterException,
)

from elftools.elf.elffile import ELFFile


class PinEngine(engine.CollectEngine):
    """Implementation of CollectEngine using Intel's PIN framework.

    :ivar str pintool_src: an absolute path to pintool source file
    :ivar str pintool_makefile: an absolute path to pintool makefile
    :ivar str dynamic_data: an absolute path to file containing data, collected by pintool,
                            that changes dynamically during the runtime of the program
    :ivar str static_data: an absolute path to file containing data, collected by pintool,
                           that does not change during the runtime of the program
    :ivar list functions_in_binary: an array of function information form specified binary
    """

    name = "pin"

    def __init__(self, config) -> None:
        """Constructs the engine object.

        :param Configuration config: collection parameters
        """
        super().__init__(config)
        self.pintool_src: str = f"{get_tmp_directory()}/pintool.cpp"
        self.pintool_makefile: str = f"{get_tmp_directory()}/makefile"

        self.dynamic_data: str = self._assemble_file_name("dynamic-data", ".txt")
        self.static_data: str = self._assemble_file_name("static-data", ".txt")

        self.functions_in_binary: List[scan_binary.FunctionInfo] = []
        self.__dependencies: List[str] = ["g++", "make"]
        # Note: float and bool are currently not stable - PIN collects wrong values in some cases
        self.__supported_base_argument_types: List[str] = ["int", "char", "float", "double", "bool"]
        self.__pin_root: str = ""

        msg_to_stdout(
            (
                f"[Debug]: Creating collect files: {self.dynamic_data}, {self.static_data}, "
                f"{self.pintool_src}, {self.pintool_makefile}"
            ),
            3,
        )
        super()._create_collect_files(
            [self.dynamic_data, self.static_data, self.pintool_src, self.pintool_makefile]
        )

    def check_dependencies(self) -> None:
        """Check that the tools for pintool creation are available and if pin's root folder is
        specified.

        :raises: PinInvalidPinRoot: the PIN_ROOT environment variable is not set or contains
                                    wrong path
        :raises: InvalidBinaryException: binary has no dwarf info
        """
        msg_to_stdout("[Info]: Checking dependencies.", 2)
        check(self.__dependencies)

        # Check if PIN_ROOT environmental variable is set
        # TODO: maybe add check if the specified directory contains some of the required contents
        # TODO: check the version of pin (currently the version is capped on 3.27 because the
        #       pintool compilation changes in 3.28 with addition of dwarf reading capability)
        if (
            "PIN_ROOT" not in os.environ.keys()
            or not os.path.isdir(os.environ["PIN_ROOT"])
            or not os.path.isabs(os.environ["PIN_ROOT"])
        ):
            raise PinInvalidPinRoot()
        self.__pin_root = os.environ["PIN_ROOT"]

        # The specified binary needs to include dwarf4 info
        with open(self.binary, "rb") as binary:
            if not ELFFile(binary).has_dwarf_info():  # File has no DWARF info
                raise InvalidBinaryException(self.binary)

    def available_usdt(self, **_) -> dict:
        """This method isn't used by the pin engine and therefore returns empty dictionary."""
        return {}

    def assemble_collect_program(self, **kwargs) -> None:
        """Assemble a pintool for the collection based on selected configuration options.

        :param kwargs: the configuration parameters
        """
        # TODO: The parameters are somewhat checked here. Should they be checked elsewhere?
        configuration: Dict[str, Union[bool, str]] = {
            "mode": kwargs["mode"],
            "probed": kwargs["probed"],
            "collect_functions": (
                kwargs["mode"] == "memory"
                or (kwargs["mode"] == "time" and not kwargs["collect_basic_blocks_only"])
            ),
            "collect_arguments": (
                kwargs["collect_arguments"]
                and kwargs["mode"] == "time"
                and not kwargs["collect_basic_blocks_only"]
            ),
            "collect_basic_blocks": (
                kwargs["collect_basic_blocks"]
                or kwargs["collect_basic_blocks_only"]
                or kwargs["mode"] == "instructions"
            ),
        }
        msg_to_stdout(f"[Debug]: Configuration: {configuration}.", 3)
        if configuration["mode"] not in ["time", "instructions", "memory"]:
            # TODO: exception
            raise Exception("Unknown pin engine mode!")

        if configuration["collect_arguments"]:
            # Note: When collecting arguments of functions, the dwarf debug information
            # in binary is scanned before the pintool is created. This is done to gather
            # information about arguments of functions contained in it. Currently, the
            # binary is scanned using pyelftools and only basic datatypes are retrieved.
            # TODO: Improve the extraction of the argument information (namely extraction of types).
            # TODO: Explore options of gathering this information exclusively in pintool
            #       with little overhead increase - requires PIN 3.28+.
            msg_to_stdout("[Info]: Scanning binary for functions and their arguments.", 2)
            self.functions_in_binary = scan_binary.get_function_info_from_binary(self.binary)
            self._filter_functions_in_binary()

        msg_to_stdout("[Info]: Assembling the pintool.", 2)
        self._assemble_pintool(**configuration)

        msg_to_stdout("[Debug]: Building the pintool.", 3)
        run_safely_external_command(f"make -C {get_tmp_directory()}")
        msg_to_stdout("[Debug]: The pintool is built.", 3)

    def collect(self, **kwargs: Dict[str, Any]) -> None:
        """Collect the raw performance data using the assembled pintool.

        :param Configuration config: the configuration object

        :raises PinBinaryInstrumentationFailed: execution of pin with generated pintool failed
        """
        msg_to_stdout("[Info]: Collecting the performance data.", 2)
        config = kwargs["config"]
        collection_cmd: str = (
            f"{self.__pin_root}/pin "
            f"-t {get_tmp_directory()}/obj-intel64/pintool.so "
            f"-- {config.executable}"
        )

        msg_to_stdout(f"[Debug]: Running the pintool with command: {collection_cmd}.", 3)
        try:
            run_safely_external_command(collection_cmd)
        except subprocess.CalledProcessError:
            raise PinBinaryInstrumentationFailed

    def transform(self, **kwargs) -> Generator[Dict[str, Union[str, int]], None, None]:
        """Transform the raw performance data into a resources as used in the profiles.

        :param Configuration config: the configuration object

        :return iterable: a generator object that produces the resources
        """
        msg_to_stdout("[Info]: Transforming the collected data to perun profile.", 2)
        config = kwargs["config"]

        # Transform function information from DWARF debug info into a map based on name
        function_arguments_map = {}
        if self.functions_in_binary:
            for function_info in self.functions_in_binary:
                function_arguments_map[function_info.name] = function_info

        msg_to_stdout(f"[Debug]: Parsing data from {self.static_data}", 3)
        static_parser: PinStaticOutputParser = PinStaticOutputParser(
            self.static_data, function_arguments_map
        )
        program_data: ProgramData = static_parser.parse_static_data()

        msg_to_stdout(f"[Debug]: Parsing data from {self.dynamic_data}", 3)
        dynamic_parser: Optional[PinDynamicOutputParser] = None
        mode: str = kwargs["mode"]
        workload: str = config.executable.workload
        basic_blocks_only: bool = kwargs["collect_basic_blocks_only"]

        if mode == "time":
            dynamic_parser = PinTimeOutputParser(
                self.dynamic_data,
                program_data,
                workload=workload,
                collect_basic_blocks_only=basic_blocks_only,
            )
        elif mode == "memory":
            dynamic_parser = PinMemoryOutputParser(
                self.dynamic_data, program_data, workload=workload
            )
        elif mode == "instructions":
            dynamic_parser = PinInstructionOutputParser(
                self.dynamic_data, program_data, workload=workload
            )
        else:
            # TODO: exception
            # Note: this should not be reachable - checked when pintool is being assembled
            Exception("Unknown pin engine mode!")

        return dynamic_parser.parse_dynamic_data_file()

    def cleanup(self, **kwargs: Dict[str, Any]) -> None:
        """Cleans up all the engine-related resources such as files, processes, locks, etc.

        :param Configuration config: collection parameters
        """
        msg_to_stdout("[Info]: Cleaning up.", 2)
        config = kwargs["config"]
        if os.path.exists(f"{get_tmp_directory()}/obj-intel64"):
            msg_to_stdout("[Debug]: Removing the built pintool.", 3)
            run_safely_external_command(f"make -C {get_tmp_directory()} clean-obj-intel64")

        msg_to_stdout(
            f'[Debug]: {"Store" if config.keep_temps or config.zip_temps else "Remove"} '
            "the generated pintool source code and collected data.",
            3,
        )
        file_names: List[str] = ["dynamic_data", "static_data", "pintool_src", "pintool_makefile"]
        super()._finalize_collect_files(file_names, config.keep_temps, config.zip_temps)

    def _assemble_pintool(
        self,
        mode: str = "time",
        probed: bool = False,
        collect_functions: bool = True,
        collect_basic_blocks: bool = True,
        collect_arguments: bool = False,
    ) -> None:
        """Creates a pintool and makefile for it based on Jinja2 templates.

        :param str mode: Specifies what will be collected by the pintool
                         (One of: 'time', 'memory', 'instructions').
        :param bool probed: If True the pintool will instrument using probes instead of
                            the just-in-time compiler.
        :param bool collect_functions: If True pintool will be able to collect functions. Not yet
                                       supported by the 'instructions' mode.
        :param bool collect_arguments: If True pintool will be able to collect arguments based on
                                       the dwarf information extracted from the binary. This is
                                       supported only when collect_functions is enabled and
                                       probed is disabled.
        :param bool collect_basic_blocks: If True pintool will be able to collect basic blocks.
                                          This is not supported when probed is enabled.

        :raises InvalidParameterException: when an invalid parameter is detected
        """
        env = templates.get_environment(autoescape=select_autoescape())

        if probed and collect_basic_blocks:
            raise InvalidParameterException(
                "collect_basic_blocks", True, "Can not be used when Probed mode is enabled."
            )

        function_names: str = ""
        func_len: int = 0
        if self.functions_in_binary:
            # enclose the function names in quotes for declaration of name array in the pintool
            function_names = ", ".join([f'"{func.name}"' for func in self.functions_in_binary])
            func_len = len(self.functions_in_binary)

        pintool_info: Dict[str, Union[str, bool, List[scan_binary.FunctionInfo]]] = {
            "mode": mode,
            "dynamic_data_file": self.dynamic_data,
            "static_data_file": self.static_data,
            "collect_basic_blocks": collect_basic_blocks,
            "collect_functions": collect_functions,
            "collect_arguments": collect_arguments,
            "probed": probed,
            "function_arguments_info": self.functions_in_binary,
            "function_names": function_names,
            "function_count": func_len,
        }
        pin_root_info: Dict[str, str] = {"pin_root": self.__pin_root}

        # Generate the pintool and its makefile
        source_code: str = env.get_template("pin_pintool.jinja2").render(pintool_info)
        makefile_rules: str = env.get_template("pin_makefile.jinja2").render(pin_root_info)

        with open(self.pintool_src, "w") as pt, open(self.pintool_makefile, "w") as mf:
            pt.write(source_code)
            mf.write(makefile_rules)

    def _is_supported_argument_type(self, argument_type: str) -> bool:
        """Returns True if the specified argument type is supported by the engine and should be
        collected by PIN.

        :param str argument_type: type of the argument as string
        :return bool: True if supported, False otherwise
        """
        # NOTE: Lets the types like 'long long int' through
        is_pointer: bool = argument_type.count("*") > 0
        for supported_type in self.__supported_base_argument_types:
            if supported_type in argument_type.replace("*", "").split():
                # match the argument type to one of the supported base types
                return not is_pointer or supported_type == "char"  # only supported pointer is char*
        return False

    def _filter_functions_in_binary(self) -> None:
        """Remove functions from the self.functions_in_binary list so that it contains only
        functions that have arguments and don't start with '__'.

        The resulting functions will also have their arguments filtered so that they include
        only arguments with supported types by PIN argument collection.
        """
        # Filter out the functions for which the argument gathering doesn't need to be done
        filtered_functions_in_binary: List[scan_binary.FunctionInfo] = []
        for function in self.functions_in_binary:
            if not function.arguments or function.name.startswith("__"):
                continue

            filtered_arguments: List[scan_binary.FunctionArgument] = []
            for argument in function.arguments:
                if argument.type.count("*") <= 1 and self._is_supported_argument_type(
                    argument.type
                ):
                    filtered_arguments.append(argument)
            if filtered_arguments:
                function.arguments = filtered_arguments
                filtered_functions_in_binary.append(function)

        self.functions_in_binary = filtered_functions_in_binary
