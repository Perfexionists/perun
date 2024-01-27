""" The Pin engine implementation.
"""
from jinja2 import Environment, PackageLoader, select_autoescape
import os
import subprocess
from typing import List, Dict, Union

import perun.collect.trace.collect_engine as engine
from perun.utils.log import msg_to_stdout
from perun.collect.trace.values import check
from perun.logic.pcs import get_tmp_directory
import perun.utils as utils
import perun.collect.trace.pin.parse as parse
import perun.collect.trace.pin.scan_binary as scan_binary
from perun.utils.exceptions import (
    InvalidBinaryException,
    PinUnspecifiedPinRoot,
    PinBinaryInstrumentationFailed,
    InvalidParameterException
)
from elftools.elf.elffile import ELFFile


class PinEngine(engine.CollectEngine):
    """ Implementation of CollectEngine using PIN framework.

    :ivar str pintool_src: an absolute path to pintool source file
    :ivar str pintool_makefile: an absolute path to pintool makefile
    :ivar str data: an absolute path to raw performance data file
    :ivar list functions_in_binary: an array of function information form specified binary
    """

    name = 'pin'

    def __init__(self, config, **kwargs):
        """ Constructs the engine object.

        :param Configuration config: the collection parameters stored in the configuration object
        """
        super().__init__(config)
        # TODO: check if the combination of engine cli options makes sense

        self.pintool_src: str = f'{get_tmp_directory()}/pintool.cpp'
        self.pintool_makefile: str = f'{get_tmp_directory()}/makefile'

        self.dynamic_data: str = self._assemble_file_name('dynamic-data', '.txt')
        # TODO: the static data file is not needed for memory collection
        self.static_data: str = self._assemble_file_name('static-data', '.txt')

        self.functions_in_binary: List[scan_binary.FunctionInfo] = []
        self.__dependencies: List[str] = ['g++', 'make']
        self.__supported_base_argument_types: List[str] = ["int", "char", "float", "double", "bool"]
        self.__pin_root: str = ''

        msg_to_stdout((f'[Debug]: Creating collect files: {self.dynamic_data}, {self.static_data}, '
                       f'{self.pintool_src}, {self.pintool_makefile}'), 3)
        super()._create_collect_files([self.dynamic_data, self.static_data, self.pintool_src, self.pintool_makefile])

    def check_dependencies(self):
        """ Check that the tools for pintool creation are available and if pin's root folder is specified.
        """
        msg_to_stdout('[Info]: Checking dependencies.', 2)
        check(self.__dependencies)

        # Check if PIN_ROOT environmental variable is set
        # TODO: maybe add check if the specified directory contains some of the required contents
        if 'PIN_ROOT' not in os.environ.keys():
            raise PinUnspecifiedPinRoot()
        self.__pin_root = os.environ['PIN_ROOT']
        if not os.path.isdir(self.__pin_root) or not os.path.isabs(self.__pin_root):
            msg_to_stdout(f'[Debug]: PIN_ROOT environmental variable exists, but is not valid absolute path.', 3)
            raise PinUnspecifiedPinRoot()

        # The specified binary needs to include dwarf4 info
        with open(self.binary, 'rb') as binary:
            if not ELFFile(binary).has_dwarf_info():  # File has no DWARF info
                raise InvalidBinaryException(self.binary)

    def available_usdt(self, **_):
        """ This method isn't used by the pin engine and therefore returns empty dictionary.
        """
        return {}

    def assemble_collect_program(self, **kwargs):
        """ Assemble a pintool for the collection based on selected configuration options.

        :param kwargs: the configuration parameters
        """
        if kwargs['collect_arguments']:
            msg_to_stdout('[Info]: Scanning binary for functions and their arguments.', 2)
            self.functions_in_binary = scan_binary.get_function_info_from_binary(self.binary)
            import pprint
            pprint.pprint(self.functions_in_binary)
            self._filter_functions_in_binary()

        msg_to_stdout('[Info]: Assembling the pintool.', 2)
        self._assemble_pintool(kwargs['collect_arguments'],
                               kwargs['collect_basic_blocks'], kwargs['collect_basic_blocks_only'],
                               kwargs['probed'], kwargs['mode'])
        msg_to_stdout('[Debug]: Building the pintool.', 3)
        utils.run_safely_external_command(f'make -C {get_tmp_directory()}')

    def collect(self, config, **_):
        """ Collect the raw performance data using the assembled pintool.

        :param Configuration config: the configuration object
        """
        msg_to_stdout('[Info]: Collecting the performance data.', 2)
        collection_cmd: str = f'{self.__pin_root}/pin -t {get_tmp_directory()}/obj-intel64/pintool.so -- {config.executable}'

        msg_to_stdout(f'[Debug]: Running the pintool with command: {collection_cmd}.', 3)
        try:
            utils.run_safely_external_command(collection_cmd)
        except subprocess.CalledProcessError:
            raise PinBinaryInstrumentationFailed

    def transform(self, config, **kwargs):
        """ Transform the raw performance data into a resources as used in the profiles.

        :param Configuration config: the configuration object

        :return iterable: a generator object that produces the resources
        """
        msg_to_stdout('[Info]: Transforming the collected data to perun profile.', 2)
        msg_to_stdout(f'[Debug]: Parsing data from {self.dynamic_data} and {self.static_data}', 3)
        # TODO: decide what options to pass (not the whole kwargs dict)
        return parse.parse_data(options=kwargs, dynamic_data_file=self.dynamic_data, static_data_file=self.static_data,
                                workload=config.executable.workload, functions_information=self.functions_in_binary)

    def cleanup(self, config, **_):
        """ Cleans up all the engine-related resources such as files, processes, locks, etc.

        :param Configuration config: the configuration object
        """
        msg_to_stdout('[Info]: Cleaning up.', 2)
        if os.path.exists(f'{get_tmp_directory()}/obj-intel64'):
            utils.run_safely_external_command(f'make -C {get_tmp_directory()} clean-obj-intel64')
        # super()._finalize_collect_files(['data', 'pintool_src', 'pintool_makefile'],
        #                                 config.keep_temps, config.zip_temps)

    def _assemble_pintool(self, collect_args: bool = False, collect_bbls: bool = False,
                          collect_bbls_only: bool = False, probed: bool = False, mode: str = 'time'):
        """ Creates makefile for pintool and the pintool itself from Jinja2 templates.

        :param bool collect_args: if True pintool will be able to collect arguments specified in functions_in_binary
        :param bool collect_bbls: if True pintool will be able to collect basic block run-times
                                  (can't be used when in probed mode)
        :param bool probed: if True the pintool will instrument using probes instead of just in time compiler
        """

        env = Environment(
            loader=PackageLoader('perun', package_path='collect/trace/pin/templates'),
            autoescape=select_autoescape()
        )

        if probed and collect_bbls:
            raise InvalidParameterException("collect_basic_blocks", True,
                                            "Can't be used when Probed mode is enabled.")
        if collect_bbls_only:
            collect_bbls = True

        function_names: str = ''
        func_len: int = 0
        if self.functions_in_binary:
            # enclose the function names in quotes for declaration of name array in the pintool
            function_names = ', '.join([f'"{function.name}"' for function in self.functions_in_binary])
            func_len = len(self.functions_in_binary)

        pintool_info: Dict[str, Union[str, bool, List[scan_binary.FunctionInfo]]] = {
            'mode': mode, 'dynamic_data_file': self.dynamic_data, 'static_data_file': self.static_data,
            'collect_basic_blocks': collect_bbls, 'collect_basic_blocks_only': collect_bbls_only,
            'collect_arguments': collect_args, 'probed': probed,
            'function_arguments_info': self.functions_in_binary, 'function_names': function_names,
            'function_count': func_len
        }

        # Generate the pintool and its makefile
        source_code = env.get_template('pintool.jinja2').render(pintool_info)
        makefile_rules = env.get_template('makefile.jinja2').render({'pin_root': self.__pin_root})

        with open(self.pintool_src, 'w') as pt, open(self.pintool_makefile, 'w') as mf:
            pt.write(source_code)
            mf.write(makefile_rules)

    def _is_supported_argument_type(self, argument_type: str) -> bool:
        """ Returns True if the specified argument type is supported by the engine and should be collected by PIN.

        :param str argument_type: type of the argument as string
        :return bool: True if supported, False otherwise
        """
        # NOTE: Lets the types like 'long long int' through
        is_pointer: bool = argument_type.count('*') > 0
        for supported_type in self.__supported_base_argument_types:
            if supported_type in argument_type.replace('*', '').split():
                # match the argument type to one of the supported base types
                return not is_pointer or supported_type == 'char'  # only supported pointer is char*
        return False

    def _filter_functions_in_binary(self):
        """ Remove functions from the self.functions_in_binary list so that it contains only
        functions that have arguments and don't start with '__'.

        The resulting functions will also have their arguments filtered so that they include
        only arguments with supported types by PIN argument collection.
        """
        msg_to_stdout('[Debug]: Filtering functions and their arguments:', 4)
        # Filter out the functions for which the argument gathering doesn't need to be done
        filtered_functions_in_binary = []
        for function in self.functions_in_binary:
            msg_to_stdout(f'\t - {function.name}:', 4)
            filtered_out = True

            if function.arguments and not function.name.startswith('__'):
                # Function that doesn't start with '__' - filters out unwanted internal functions
                filtered_arguments = []
                for argument in function.arguments:
                    if argument.type.count('*') <= 1 and self._is_supported_argument_type(argument.type):
                        filtered_arguments.append(argument)
                if filtered_arguments:
                    function.arguments = filtered_arguments
                    filtered_functions_in_binary.append(function)
                    filtered_out = False

            # NOTE: shows only supported arguments for the functions that haven't been filtered
            msg_to_stdout(f'\t\t - {"not " if not filtered_out else ""}filtered out \n\t\t - {function}', 4)
        self.functions_in_binary = filtered_functions_in_binary
