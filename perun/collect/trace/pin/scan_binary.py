from elftools.elf.elffile import ELFFile
from elftools.common.py3compat import bytes2str
from elftools.dwarf.die import DIE
from typing import List 

from perun.utils.exceptions import PinBinaryScanUnsuccessful


class FunctionArgument:

    def __init__(self, arg_type: str, arg_name: str, arg_index: int):
        self.type = arg_type
        self.name = arg_name
        self.index = arg_index
        self.value = None

    def __repr__(self) -> str:
        return f"{self.type} {self.name}:{self.index} = {self.value}"

    def __eq__(self, other) -> bool:
        return self.name == other.name and self.type == other.type and \
               self.index == other.index and self.value == other.value


class FunctionInfo:

    def __init__(self, name: str, arguments: list = []):
        self.name = name
        self.arguments = arguments
    
    def __repr__(self) -> str:
        return f"func {self.name} - {self.arguments}"

    def __eq__(self, other) -> bool:
        return self.name == other.name


def get_function_info_from_binary(filename: str) -> List[FunctionInfo]:
    """ Function reads DWARF debug information form the specified binary file and extracts 
    information about functions contained in it. Namely function name and argument names, 
    types and indices.

    :param str filename: binary with DWARF debug info one wants to analyze

    :return list: list containing FunctionInfo objects representing each function contained in the binary file
    """

    with open(filename, 'rb') as f:
        elffile = ELFFile(f)

        if not elffile.has_dwarf_info():
            # File has no DWARF info
            raise PinBinaryScanUnsuccessful

        dwarf_info = elffile.get_dwarf_info()

        functions = []
        for compilation_unite in dwarf_info.iter_CUs():
            # Start with the top Debugging Information Entry (DIE), the root for this Compile Unit's DIE tree
            try:
                top_DIE = compilation_unite.get_top_DIE()
            except Exception:
                #FIXME exception - this fails sometimes (needs more testing to determine when)
                raise PinBinaryScanUnsuccessful

            functions += _get_function_info_from_die(top_DIE)

    return functions


def _get_arguments_info_from_die(subprogram_die: DIE) -> List[FunctionArgument]:
    """ Gathers information about arguments from specified Debugging Information Entry.

    Function expects subprogram DIE and iterates over its children to find all the arguments DIEs
    and gather information about the name, type and index for each of them. Arguments are skipped
    when their type couldn't be retrieved.

    :param DIE subprogram_die: DIE with information about a function

    :return List: list with information about arguments as FunctionArgument object
    """

    argument_index = -1
    function_arguments = []

    for subprogram_child in subprogram_die.iter_children():
        
        if subprogram_child.tag == 'DW_TAG_formal_parameter':
            argument_index += 1

            # Get argument type
            argument_type_die = subprogram_child.get_DIE_from_attribute('DW_AT_type')
            argument_type = _get_type_from_die(argument_type_die)
            if not argument_type: 
                # Skip an argument, when debug data isn't available
                continue
            
            # Get argument name
            try:
                argument_name = bytes2str(subprogram_child.attributes['DW_AT_name'].value)
            except KeyError:
                argument_name = '[No name in DWARF]'

            function_argument = FunctionArgument(arg_type=argument_type, 
                                                 arg_name=argument_name, 
                                                 arg_index=argument_index)
            function_arguments.append(function_argument)

    return function_arguments


def _get_function_info_from_die(die: DIE) -> List[FunctionInfo]:
    """ Gathers information about functions from specified Debugging Information Entry. 

    Function iterates over children of the specified DIE searching for functions and extracts function name and 
    its argument names, types and indices the underlying DWARF structures.

    :param DIE die: the debugging information entry from which one wants to extract information about functions

    :return list: list containing information about each function as FunctionInfo object
    """

    functions_in_die = []
    for child in die.iter_children():

        if child.tag == 'DW_TAG_subprogram':

            # Get function name
            try:
                function_name_attribute = child.attributes['DW_AT_name']
            except KeyError:
                #NOTE: function name identifies the function, so if this information can't be 
                # retrieved from the subprogram child DIE the function is skipped entirely.
                continue
            function_name = bytes2str(function_name_attribute.value) 

            # Get arguments information
            function_arguments = _get_arguments_info_from_die(child)

            function_info = FunctionInfo(name=function_name, arguments=function_arguments) 
            functions_in_die.append(function_info)

    return functions_in_die 


def _get_type_from_die(type_die: DIE) -> str:
    """ Extracts type from Debugging Information Entry to a string.

    :param DIE type_die: debugging information entry containing information about a type

    :return str: type in str or empty if not retrievable
    """

    if type_die.tag == 'DW_TAG_base_type':
        type_str = bytes2str(type_die.attributes['DW_AT_name'].value)
        type_str = type_str if type_str != '_Bool' else 'bool'
        return type_str

    elif type_die.tag == 'DW_TAG_pointer_type':
        if 'DW_AT_type' in type_die.attributes:
            type_die = type_die.get_DIE_from_attribute('DW_AT_type')
            type_str = _get_type_from_die(type_die)
            if type_str:
                return type_str + '*'

    elif type_die.tag == 'DW_TAG_const_type':
        try:
            type_die = type_die.get_DIE_from_attribute('DW_AT_type')
            type_str = bytes2str(type_die.attributes['DW_AT_name'].value)
        except KeyError:
            return ''

        type_str = type_str if type_str != '_Bool' else 'bool'
        return 'const ' + type_str
    
    return ''