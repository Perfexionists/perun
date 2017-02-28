""" Module for function symbols extraction, filtering and processing.

    This module produces function symbols exclude list from configuration executable's symbol table.
    The list is then used for compile-time exclusion of functions that need not to be instrumented.

    It also provides functions that handle symbol to address mapping, but only of compile-time known
    symbols (i.e. not symbols that are provided by shared libraries). This mapping is useful for
    runtime configuration of collector executable (ccicc, see configurator.py).

"""

import sys
import subprocess

_SYMTABLE_NAME_COLUMN = 8
_SYMTABLE_ADDR_COLUMN = 2


def extract_symbols(executable_path):
    """ Extracts only defined function symbol names from the executable

    Arguments:
        executable_path(str): path to the executable

    Returns:
        list: function symbol names

    Raises:
        OSError: in case of invalid system util command
        ValueError: in case of invalid arguments to the system calls
        UnicodeError: in case of bytes decode failure
    """
    return _get_symbols(executable_path, [_SYMTABLE_NAME_COLUMN])


def extract_symbol_map(executable_path):
    """ Extracts defined function symbol names and their addresses from the executable

    Arguments:
        executable_path(str): path to the executable

    Returns:
        dict: function symbols map in form 'mangled name: hex address'

    Raises:
        OSError: in case of invalid system util command
        ValueError: in case of invalid arguments to the system calls
        UnicodeError: in case of bytes decode failure
    """
    # Get the mangled function names and addresses
    symbols = _get_symbols(executable_path, [_SYMTABLE_ADDR_COLUMN, _SYMTABLE_NAME_COLUMN])
    # Create symbol map as name: address in hex format
    symbol_map = {symbols[i+1]: ('0x' + symbols[i].lstrip('0')) for i in range(0, len(symbols), 2)}

    return symbol_map


def translate_mangled_symbols(mangled_names):
    """ Translates the mangled names to their demangled counterparts

    Arguments:
        mangled_names(list): the names to be translated

    Returns:
        dict: function symbols name map in form 'mangled name: demangled name'

    Raises:
        OSError: in case of invalid system util command
        ValueError: in case of invalid arguments to the system calls
        UnicodeError: in case of bytes decode failure
    """
    # Transform the names to string parameter
    mangled_str = '\n'.join(mangled_names)

    # Create demangled counterparts of the function names
    demangle = subprocess.Popen('c++filt', stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    demangled_names = demangle.communicate(input=mangled_str.encode(sys.stdout.encoding))[0]
    demangle.stdout.close()
    demangled_names = demangled_names.decode(sys.stdout.encoding).split('\n')
    try:
        demangled_names.remove('')
    except ValueError:
        pass

    # Map the names
    return dict(zip(mangled_names, demangled_names))


def filter_symbols(symbols, profile_rules):
    """ Filters the function symbols and creates the static exclude and include dict

    Arguments:
        symbols(list): function symbols mangled names extracted from an executable
        profile_rules(list): rules specifying which functions should be profiled

    Returns:
        tuple: list of statically excluded function symbols
               list of runtime filtered function symbols in mangled format
    """
    # TODO: upgrade the filtering algorithm, still trivial prototype version
    # TODO: Refactor A LOT
    # TODO: Ambiguity
    symbols_name_map = translate_mangled_symbols(symbols)
    exclude_list = _filter_invalid_functions(symbols_name_map)

    # Build up include list from the rules
    include_list = dict()
    for rule in profile_rules:
        # Check if the rule contains fully specified function name
        if '(' not in rule:
            # If not, then add brace for easier searching
            rule += '('
        # Search the function names for rule match
        remove_list = []
        for func_key, func_val in symbols_name_map.items():
            if rule in func_val:
                # Rule match, save the function key
                include_list[func_key] = func_val
                remove_list.append(func_key)
        # Remove the keys that are already in the include list
        for func in remove_list:
            del symbols_name_map[func]

    # Extend the exclude list of functions that do not match any rule
    exclude_list.update(symbols_name_map)
    # Get the final exclude list version
    return _finalize_static_lists(exclude_list, include_list)


def _get_symbols(executable_path, columns):
    """ Creates the pipe of linux utils to access and filter executable symbol table

    Arguments:
        executable_path(str): path to the executable
        columns(list): symbol table column numbers which should be captured

    Returns:
        list: sequential symbol table values [column1, column2, column1, ...]

    Raises:
        OSError: in case of invalid system util command
        ValueError: in case of invalid arguments to the system calls
        UnicodeError: in case of bytes decode failure
    """
    # Convert the columns list to string parameter
    columns_str = ','.join(str(column) for column in columns)

    # readelf -sW exec | awk '$4 == "FUNC" && $7 != "UND"' | awk '{$2=$2};1' | cut -d' ' -f columns
    sym_table_full = subprocess.Popen(('readelf', '-sW', executable_path),
                                      stdout=subprocess.PIPE)
    sym_table_func = subprocess.Popen(('awk', '$4 == "FUNC" && $7 != "UND"'),
                                      stdin=sym_table_full.stdout, stdout=subprocess.PIPE)
    sym_table_whsp = subprocess.Popen(('awk', '{$2=$2};1'),
                                      stdin=sym_table_func.stdout, stdout=subprocess.PIPE)
    sym_table_filt = subprocess.Popen(('cut', '-d', ' ', '-f', columns_str),
                                      stdin=sym_table_whsp.stdout, stdout=subprocess.PIPE)
    # Close the pipes output
    sym_table_full.stdout.close()
    sym_table_func.stdout.close()
    sym_table_whsp.stdout.close()
    # Save the filtered table
    symbols = sym_table_filt.communicate()[0]
    sym_table_filt.stdout.close()

    # Decode the bytes and create list
    symbols = symbols.decode(sys.stdout.encoding).replace(' ', '\n').split('\n')
    # Remove the redundant element
    try:
        symbols.remove('')
    except ValueError:
        pass

    return symbols


def _finalize_static_lists(exclude_list, include_list):
    """ Finalizes the static exclude list, solves symbols collision in exclude / include list due
        to function overloading and identifier duplication, provides final static exclude list
        and runtime filter list (TODO)

    Arguments:
        exclude_list(dict): function symbols to be excluded as 'mangled name: demangled name'
        include_list(dict): function symbols to be profiled as 'mangled name: demangled name'

    Returns:
        tuple: list of statically excluded function symbols
               list of runtime filtered function symbols in mangled format
    """
    for func_key, func_val in include_list.items():
        include_list[func_key] = _extract_function_identifier(func_val)

    for func_key, func_val in exclude_list.items():
        exclude_list[func_key] = _extract_function_identifier(func_val)

    # TODO: Here should go the advanced checking for runtime filter etc
    runtime_filter = []

    return list(exclude_list.values()), runtime_filter


def _filter_invalid_functions(workload_symbols):
    """ Filters function symbols that don't contain argument brace, except for main.
        Usually various pre and post main calls, unable to instrument them anyways

    Arguments:
        workload_symbols(dict): function symbols as 'mangled name: demangled name'

    Returns:
        dict: symbols to be excluded as 'mangled name: demangled name',
              these symbols are removed from the workload_symbols
    """
    # Filter the functions without argument braces
    exclude_list = dict()
    for func_key, func_val in workload_symbols.items():
        if ('(' not in func_val or ')' not in func_val) and func_val != 'main':
            exclude_list[func_key] = func_val

    # Remove them from symbol dict
    for invalid_record_key in exclude_list:
        del workload_symbols[invalid_record_key]

    return exclude_list


def _extract_function_identifier(function_prototype):
    """ Extracts the function identifier from its prototype

    Arguments:
        function_prototype(str): the function prototype

    Returns:
        str: the extracted function identifier
    """
    # TODO: Improve, still trivial prototype version
    # Simple version, remove scope until identifier with argument brace is not found
    scope = function_prototype.find('::')
    arg = function_prototype.find('(')
    # Remove all scopes before arg brace
    while scope != -1 and scope < arg:
        function_prototype = function_prototype[scope + 2:]
        scope = function_prototype.find('::')
        arg = function_prototype.find('(')
    if arg == -1:
        return function_prototype
    else:
        identifier = function_prototype[:arg]
        return identifier
