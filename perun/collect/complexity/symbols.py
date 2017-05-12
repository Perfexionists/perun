""" Module for function symbols extraction, filtering and processing.

    This module produces function symbols exclude list from configuration executable's symbol table.
    The list is then used for compile-time exclusion of functions that need not to be instrumented.

    It also provides functions that handle symbol to address mapping, but only of compile-time known
    symbols (i.e. not symbols that are provided by shared libraries). This mapping is useful for
    runtime configuration of collector executable (ccicc, see configurator.py).

"""


import sys
import subprocess
import exceptions
import collections

# Symbol table columns constants
_SYMTABLE_NAME_COLUMN = 8
_SYMTABLE_ADDR_COLUMN = 2

# The named tuple collection for storage of decomposed function prototypes
PrototypeParts = collections.namedtuple('prototype_parts', ['identifier', 'args', 'scoped_body', 'scoped_args',
                                                            'full_body', 'full_args'])
# The named tuple collection serving as a key for include list
RuleKey = collections.namedtuple('rule_key', ['mangled_name', 'rule'])


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


def extract_symbol_address_map(executable_path):
    """ Extracts defined function symbol addresses and demangled names

    Arguments:
        executable_path(str): path to the executable

    Returns:
        dict: function symbols map in form 'hex address: demangled name'

    Raises:
        OSError: in case of invalid system util command
        ValueError: in case of invalid arguments to the system calls
        UnicodeError: in case of bytes decode failure
    """
    # Get the mangled function names and addresses
    symbols = _get_symbols(executable_path, [_SYMTABLE_ADDR_COLUMN, _SYMTABLE_NAME_COLUMN])
    # Create address map as hex address: mangled name
    address_map = {('0x' + symbols[i].lstrip('0')): symbols[i + 1] for i in range(0, len(symbols), 2)}
    # Translate the mangled names
    name_map = translate_mangled_symbols(list(address_map.values()))
    for record in address_map:
        address_map[record] = name_map[address_map[record]]
    return address_map


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
    if '' in demangled_names:
        demangled_names.remove('')

    # Map the names
    return dict(zip(mangled_names, demangled_names))


def filter_symbols(symbols, profile_rules):
    """ Filters the function symbols and creates the static exclude and include dict

    Arguments:
        symbols(list): function symbols mangled names extracted from an executable
        profile_rules(list): rules specifying which functions should be profiled

    Returns:
        tuple: list of include symbols as rule_key tuple
               list of statically excluded function symbols
               list of runtime filtered function symbols in mangled format

    Raises:
        UnexpectedPrototypeSyntaxError encountered unexpected function prototype syntax
    """
    # Get the symbol name mapping
    symbols_name_map = translate_mangled_symbols(symbols)
    # Filter the functions to be profiled
    include_list, exclude_list = _apply_profile_rules(profile_rules, symbols_name_map)
    # Get the final exclude list version and runtime filter
    exclude_list, runtime_filter = _finalize_exclude_lists(exclude_list, include_list)
    return list(include_list.keys()), exclude_list, runtime_filter


def unify_sample_func(function):
    """ Unifies the sampling function specification.

    Arguments:
        function(str): the function prototype to be unified

    Returns:
        str: the unified function prototype
    """
    body, args = _unify_function_format(function)
    return body + args


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

    # # readelf -sW exec | awk '$4 == "FUNC" && $7 != "UND"' | awk '{$2=$2};1' | cut -d' ' -f columns
    cmd = "readelf -sW " + executable_path + \
          " | awk '$4 == \"FUNC\" && $7 != \"UND\"' | awk '{$2=$2};1' | cut -d' ' -f " + columns_str
    ps = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    symbols = ps.communicate()[0]

    # Decode the bytes and create list
    symbols = symbols.decode(sys.stdout.encoding).replace(' ', '\n').split('\n')
    # Remove the redundant element
    if '' in symbols:
        symbols.remove('')

    return symbols


def _finalize_exclude_lists(exclude_list, include_list):
    """ Finalizes the static exclude list, solves symbols collision in exclude / include list due
        to function overloading and identifier duplication, provides final static exclude list
        and runtime filter list.

    Arguments:
        exclude_list(dict): function symbols to be excluded as 'mangled name: prototype parts tuple'
        include_list(dict): function symbols to be profiled as 'rule_key tuple: prototype parts tuple'

    Returns:
        tuple: list of statically excluded function identifiers
               list of runtime filtered function symbols in mangled format
    """
    # Solves the collisions in names
    exclude_list, runtime_filter = _find_exclude_collisions(exclude_list, include_list)

    # Transform the exclude dict to the list of identifiers
    final_exclude_list = ['operator']
    for func_identifier in (getattr(exclude_list[func], 'identifier') for func in exclude_list):
        final_exclude_list.append(func_identifier)

    # Remove the duplicates if any
    return list(set(final_exclude_list)), list(runtime_filter.keys())


def _dismantle_symbols(symbol_map):
    """ Decomposes all symbols from symbol map to parts to simplify rule match. The parts are:
        identifier; argument list; scoped identifier name; scoped argument list; full identifier
        name (with all template specializations); full argument list (also template specializations)

    Arguments:
        symbol_map(dict): symbol name map in form 'mangled name: demangled name'

    Returns:
        dict: decomposed symbol map in form 'mangled name: prototype_parts tuple'

    Raises:
        UnexpectedPrototypeSyntaxError: encountered unexpected function prototype syntax
    """
    specification_map = dict()
    for key in symbol_map.keys():
        # Process each symbol from the map
        try:
            specification_map[key] = _process_symbol(symbol_map[key])
        except exceptions.UnexpectedPrototypeSyntaxError as e:
            # print(repr(e), file=sys.stderr)
            pass
    return specification_map


def _process_symbol(function_prototype):
    """ Decomposes the function prototype to the parts specified in _dismantle_symbols

    Arguments:
        function_prototype(str): the full demangled function prototype name

    Returns:
        tuple: the prototype_parts named tuple with all the function parts

    Raises:
        UnexpectedPrototypeSyntaxError: encountered unexpected function prototype syntax
    """
    # Unify the function prototype
    prototype_body, prototype_args = _unify_function_format(function_prototype)
    # Get the scoped specification
    scoped_body = _remove_templates(prototype_body)
    scoped_args = _remove_templates(prototype_args)
    # Get the function identifier and arguments without scopes
    identifier = _extract_function_identifier(scoped_body)
    arguments = _remove_argument_scopes(scoped_args)

    # Build the tuple from prototype parts
    return PrototypeParts(identifier, arguments, scoped_body, scoped_args, prototype_body, prototype_args)


def _unify_function_format(function_prototype):
    """ Unifies the format in which are functions stored, compared etc. Notably all redundant whitespaces
        are removed, return type is removed and function prototype is split into prototype body and
        argument list.

    Arguments:
        function_prototype(str): the 'raw' function prototype

    Returns:
        tuple: the normalized function prototype body and argument list
    """
    # Remove the redundant whitespaces
    function_prototype = function_prototype.replace(', ', ',')
    function_prototype = function_prototype.replace(' >', '>')

    # Split the function to a body and arguments
    function_body, function_args = _split_prototype(function_prototype)
    # Remove the return type if present
    function_body = _remove_return_type(function_body)

    return function_body, function_args


def _find_argument_list_boundary(function):
    """ Finds the start and end position of function argument list specified by the parentheses

    Arguments:
        function(str): the function to be processed

    Returns:
        tuple: start, end position as ints, -1 if no argument list was found

    Raises:
        UnexpectedPrototypeSyntaxError encountered unexpected function prototype syntax
    """
    # Find the argument braces in the prototype
    arg_brace = [i for i, char in enumerate(function) if char == '(' or char == ')']

    if len(arg_brace) == 2 and function[arg_brace[0]] == '(' and function[arg_brace[1]] == ')':
        # Braces found
        return arg_brace[0], arg_brace[1]
    elif not arg_brace:
        # No argument list
        return -1, -1
    else:
        # Unexpected number or order in parentheses
        raise exceptions.UnexpectedPrototypeSyntaxError("In prototype: " + function)


def _split_prototype(function_prototype):
    """ Splits the given function prototype to its body and argument list parts

    Arguments:
        function_prototype(str): the function to be split

    Returns:
        tuple: function body, function argument list

    Raises:
        UnexpectedPrototypeSyntaxError encountered unexpected function prototype syntax
    """
    arg_start, arg_end = _find_argument_list_boundary(function_prototype)
    # Split the prototype into body and argument part
    if arg_start != -1:
        return function_prototype[:arg_start], function_prototype[arg_start:arg_end + 1]
    else:
        return function_prototype, ''


def _extract_function_identifier(function_prototype):
    """ Extracts the function identifier from its prototype

    Arguments:
        function_prototype(str): the function prototype

    Returns:
        str: the extracted function identifier

    Raises:
        UnexpectedPrototypeSyntaxError encountered unexpected function prototype syntax
    """
    # Slice the function identifier from the left side, only scope is possible delimiter
    scope = function_prototype.rfind('::')
    if scope == -1:
        return function_prototype
    return function_prototype[scope + 2:]


def _remove_templates(function_part):
    """ Removes all template specifications from the function prototype or its part

    Arguments:
        function_part(str): the function prototype part to be processed

    Returns:
        str: the function part without template specifications
    """
    # Find all template braces
    braces = [i for i, br in enumerate(function_part) if br == '<' or br == '>']
    if not braces:
        return function_part

    # Stack-like traversing of the braces and pairing template blocks
    new_prototype = ''
    inner_level = 0
    last_end = len(function_part)
    for i in braces[::-1]:
        if function_part[i] == '>':
            if inner_level == 0:
                # New block start recognized, slice the trailing chars
                new_prototype = function_part[i+1:last_end] + new_prototype
            inner_level += 1
        else:
            inner_level -= 1
            if inner_level == 0:
                # End of a template block
                last_end = i

    return function_part[:last_end] + new_prototype


def _remove_return_type(function_body):
    """ Removes the function return type (if present) from the function body,
        which should not contain the argument list!

    Arguments:
        function_body(str): the body part of the function prototype

    Returns:
        str: the function body without the return type specification
    """
    # Check if function might contain return type specification
    return_type_delim = -1
    if ' ' in function_body:
        control_sequence = [i for i, c in enumerate(function_body)
                            if c == '<' or c == '>' or c == ' ']
        inner_state = 0
        for i in control_sequence:
            # Find first whitespace that is not in a template specification
            if function_body[i] == '<':
                inner_state += 1
            elif function_body[i] == '>':
                inner_state -= 1
            else:
                if inner_state == 0:
                    return_type_delim = i
                    break
    # Return the new function body
    return function_body[return_type_delim + 1:]


def _remove_argument_scopes(function_args):
    """ Removes all type scope specification from the function argument list

    Arguments:
        function_args(str): the function argument list in form '(...)'

    Returns:
        str: the argument list without scope specification
    """
    # Empty operation on empty args
    if function_args == '':
        return function_args
    # Get the argument list
    args = function_args[1:-1].split(',')
    new_args = '('
    for arg in args:
        scope_op = arg.rfind('::')
        if scope_op != -1:
            # The argument is scoped, slice
            arg = arg[scope_op + 2:]
        new_args += arg + ','
    # Replace the last comma with end parentheses
    new_args = new_args[:-1]
    new_args += ')'

    return new_args


def _prepare_profile_rules(profile_rules):
    """ Analyzes the profiling rules and creates their unified representation as a list of parts.
        Both body and argument part can be specified to certain level of detail, such as
        scoped identifier or fully specified identifier with template instantiation detail etc.

    Arguments:
        profile_rules(list): the list of profiling rules specified by the user

    Returns:
        dict: the rule details in the form 'rule: [body part, arg part (optional)]'
    """
    details = dict()
    for rule in profile_rules:
        # First unify the function format
        function_body, function_arg = _unify_function_format(rule)
        unified_func = function_body + function_arg
        # Check how much is the rule function specified
        body_scope, body_template = _check_rule_specification_detail(function_body)
        arg_scope, arg_template = _check_rule_specification_detail(function_arg)

        parts = []
        # Set the rule specification detail for its body part
        if body_template:
            parts.append('full_body')
        elif body_scope:
            parts.append('scoped_body')
        else:
            parts.append('identifier')
        # Set the rule specification detail for its argument part
        if function_arg:
            if arg_template:
                parts.append('full_args')
            elif arg_scope:
                parts.append('scoped_args')
            else:
                parts.append('args')
        details[unified_func] = parts
    return details


def _check_rule_specification_detail(rule_part):
    """ Checks if the rule contains scope or template specifications

    Arguments:
        rule_part(str): the part of the rule (function body or argument lit)

    Returns:
        tuple: is scope used, is template used (True/False)
    """
    template = False
    scope = False
    if rule_part:
        # Check if rule part contains template specification
        if '<' in rule_part and '>' in rule_part:
            template = True

        # Check if rule part contains scope specifications
        if '::' in rule_part:
            scope = True

    return scope, template


def _build_symbol_from_rules(symbol_parts, rule_details):
    """ Builds the symbol from its part, which are specified in the rule details

    Arguments:
        symbol_parts(dict): the symbol parts dictionary in form 'mangled name: prototype_parts tuple'
        rule_details(list): list of prototype_parts attribute names which are used to build the symbol

    Returns:
        str: the built symbol
    """
    symbol = ''
    # Build the symbol from the given parts
    for detail in rule_details:
        symbol += getattr(symbol_parts, detail)
    return symbol


def _apply_profile_rules(profile_rules, symbol_map):
    """ Applies the profiling rules given by the user to the extracted symbol table
        and thus creates the include and exclude list.

    Arguments:
        profile_rules(list): the list of profiling rules
        symbol_map(dict): symbols name map in form 'mangled name: demangled name'

    Returns:
        tuple: include dict in form 'rule_key tuple: prototype parts tuple'
               exclude dict as 'mangled name: prototype parts tuple'
    """
    # Decompose the symbols
    symbol_parts = _dismantle_symbols(symbol_map)
    # Decompose the rules
    rules_details = _prepare_profile_rules(profile_rules)

    include_list = dict()
    # We need to check all symbols for every rule to find all matches
    for rule in rules_details:
        remove_list = []
        for symbol_key in symbol_parts:
            # Build the symbol according to the rule specification details
            symbol = _build_symbol_from_rules(symbol_parts[symbol_key], rules_details[rule])
            if symbol == rule:
                # The rule matches with the symbol
                include_list[RuleKey(symbol_key, rule)] = symbol_parts[symbol_key]
                remove_list.append(symbol_key)
        # Remove already matched symbols from the iterated symbol parts
        for symbol in remove_list:
            del symbol_parts[symbol]

    return include_list, symbol_parts


def _find_exclude_collisions(exclude_list, include_list):
    """ Finds the collisions in exclude and include list, which are solved by the runtime filter.

    Arguments:
        exclude_list(dict): function exclude list as 'mangled name: prototype parts tuple'
        include_list(dict): function include list as 'rule_key tuple: prototype parts tuple'

    Returns:
        tuple: exclude dict without the collisions as 'mangled name: prototype parts tuple'
               runtime filter dict as 'mangled name: prototype parts tuple'
    """
    runtime_filter = dict()
    # Check if included function identifier is substring of some excluded function identifier
    for func_include in include_list.keys():
        collision_list = dict()
        for func_exclude in exclude_list:
            if exclude_list[func_exclude].identifier in include_list[func_include].identifier:
                # Collision found, the excluded function must be runtime filtered instead
                collision_list[func_exclude] = exclude_list[func_exclude]

        # Move the collisions to the runtime filter and remove them from the exclude list
        for collision in collision_list:
            runtime_filter[collision] = collision_list[collision]
            del exclude_list[collision]
    return exclude_list, runtime_filter
