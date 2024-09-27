from dataclasses import dataclass, field
from typing import List, Optional, Union, Any

from elftools.common.py3compat import bytes2str
from elftools.dwarf.die import DIE
from elftools.dwarf.dwarfinfo import DWARFInfo
from elftools.elf.elffile import ELFFile

from perun.utils.exceptions import PinBinaryScanUnsuccessful

VALUE_UNAVAILABLE_IN_DWARF = "[Not in DWARF]"


@dataclass(repr=False)
class FunctionArgument:
    type: str
    name: str
    index: int
    value: Optional[Union[int, float, str, bool]] = None

    def __repr__(self) -> str:
        return (
            f"{self.index}: {self.type} {self.name} = "
            f'{self.value if self.value else "Unknown value"}'
        )


@dataclass(repr=False)
class FunctionInfo:
    name: str
    arguments: List[FunctionArgument] = field(default_factory=list, compare=False)

    def __repr__(self) -> str:
        return (
            f"function {self.name}("
            f'{", ".join([argument.__repr__() for argument in self.arguments])})'
        )


def get_function_info_from_binary(filename: str) -> List[FunctionInfo]:
    """Reads DWARF debug information form the specified binary file and extracts information
    about functions contained in it. Namely, function name and argument names, types and indices.

    Note: expects DWARF info to be present in the binary

    :param str filename: path to binary with DWARF debug info one wants to analyze

    :return list: list of FunctionInfo objects representing each function contained in
                  the binary file
    :raises PinBinaryScanUnsuccessful: if the DWARF is not present in specified binary file
    """
    with open(filename, "rb") as file_descriptor:
        elf_file: ELFFile = ELFFile(file_descriptor)

        dwarf_info: DWARFInfo = elf_file.get_dwarf_info()

        functions: List[FunctionInfo] = []
        functions_cnt: int = 0
        for compilation_unit in dwarf_info.iter_CUs():
            # Start with the top Debugging Information Entry (DIE), the root for this Compile
            # Unit's DIE tree
            try:
                top_die: DIE = compilation_unit.get_top_DIE()
            except Exception:
                # FIXME the get_top_DIE fails sometimes
                raise PinBinaryScanUnsuccessful

            # FIXME: Temporary solution for duplicate functions
            new_functions: List[FunctionInfo] = _get_function_info_from_die(top_die)
            for new_function in new_functions:
                found: bool = False
                for idx, existing_function in enumerate(functions):
                    if existing_function.name == new_function.name:
                        found = True
                        for existing_argument, new_argument in zip(
                            existing_function.arguments, new_function.arguments
                        ):
                            if (
                                existing_argument.name != new_argument.name
                                and existing_argument.name == VALUE_UNAVAILABLE_IN_DWARF
                            ):
                                functions[idx] = new_function
                                break
                        break

                if not found:
                    functions.append(new_function)
                    functions_cnt += 1

    return functions


def _get_arguments_info_from_die(subprogram_die: DIE) -> List[FunctionArgument]:
    """Gathers information about arguments from specified Debugging Information Entry (DIE).

    Function expects subprogram DIE and iterates over its children to find all the argument DIEs
    and gather information about the name, type and index for each of them. Arguments are skipped
    when their type couldn't be retrieved.

    :param DIE subprogram_die: DIE with information about a function

    :return List: list with information about arguments as FunctionArgument object
    """
    argument_index: int = 0
    function_arguments: List[FunctionArgument] = []

    for subprogram_child in subprogram_die.iter_children():
        if subprogram_child.tag == "DW_TAG_formal_parameter":

            # Get argument type
            argument_type_die: DIE = subprogram_child.get_DIE_from_attribute("DW_AT_type")
            argument_type: str = _get_type_from_die(argument_type_die)
            if not argument_type:
                # Skip an argument, when debug data isn't available
                argument_index += 1
                continue

            # Get argument name
            try:
                argument_name: str = bytes2str(subprogram_child.attributes["DW_AT_name"].value)
            except KeyError:
                argument_name = VALUE_UNAVAILABLE_IN_DWARF

            function_arguments.append(
                FunctionArgument(argument_type, argument_name, argument_index)
            )
            argument_index += 1

    return function_arguments


def _get_function_info_from_die(die: DIE) -> List[FunctionInfo]:
    """Gathers information about functions from specified Debugging Information Entry.

    Function iterates over children of the specified DIE searching for functions and extracts
    function name and its argument names, types and indices the underlying DWARF structures.

    :param DIE die: the debugging information entry from which one wants to extract information
                    about functions

    :return list: list containing information about each function as FunctionInfo object
    """
    functions_in_die: List[FunctionInfo] = []

    for child in die.iter_children():
        if child.tag == "DW_TAG_subprogram":
            # Get function name
            try:
                function_name_attribute: Any = child.attributes["DW_AT_name"]
            except KeyError:
                # NOTE: function name is a key identifier of a function, so if this information
                # can't be retrieved from the subprogram child DIE the function is skipped entirely.
                continue
            function_name: str = bytes2str(function_name_attribute.value)

            # Get arguments information
            function_arguments: List[FunctionArgument] = _get_arguments_info_from_die(child)

            function_info: FunctionInfo = FunctionInfo(
                name=function_name, arguments=function_arguments
            )
            functions_in_die.append(function_info)
    return functions_in_die


def _get_type_from_die(type_die: DIE) -> str:
    """Extracts type from Debugging Information Entry (DIE) to a string.

    :param DIE type_die: DIE containing information about a type

    :return str: string containing type or empty string if not retrievable
    """

    if type_die.tag == "DW_TAG_base_type":
        type_str: str = bytes2str(type_die.attributes["DW_AT_name"].value)
        type_str = type_str if type_str != "_Bool" else "bool"
        return type_str

    elif type_die.tag == "DW_TAG_pointer_type":
        if "DW_AT_type" in type_die.attributes:
            type_die: DIE = type_die.get_DIE_from_attribute("DW_AT_type")
            type_str: str = _get_type_from_die(type_die)
            if type_str:
                return f"{type_str}*"

    elif type_die.tag == "DW_TAG_const_type":
        try:
            type_die: DIE = type_die.get_DIE_from_attribute("DW_AT_type")
            type_str: str = bytes2str(type_die.attributes["DW_AT_name"].value)
        except KeyError:
            return ""
        type_str = type_str if type_str != "_Bool" else "bool"
        return f"const {type_str}"

    return ""
