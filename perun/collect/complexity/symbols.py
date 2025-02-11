"""Module for function symbols extraction, filtering and processing.

This module produces function symbols exclude list from configuration executable's symbol table.
The list is then used for compile-time exclusion of functions that need not to be instrumented.

It also provides functions that handle symbol to address mapping, but only of compile-time known
symbols (i.e. not symbols that are provided by shared libraries). This mapping is useful for
runtime configuration of collector executable (ccicc, see configurator.py).

"""

from __future__ import annotations

# Standard Imports
import dataclasses

# Third-Party Imports

# Perun Imports
from perun.utils.external import commands
from perun.utils import exceptions

# Symbol table columns constants
_SYMTABLE_NAME_COLUMN = 8
_SYMTABLE_ADDR_COLUMN = 2


@dataclasses.dataclass(frozen=True)
class PrototypeParts:
    __slots__ = ["identifier", "args", "scoped_body", "scoped_args", "full_body", "full_args"]

    identifier: str
    args: str
    scoped_body: str
    scoped_args: str
    full_body: str
    full_args: str


@dataclasses.dataclass(frozen=True)
class RuleKey:
    __slots__ = ["mangled_name", "rule"]

    mangled_name: str
    rule: str


def extract_symbols(executable_path: str) -> list[str]:
    """Extracts only defined function symbol names from the executable

    :param executable_path: path to the executable

    :return: function symbol names
    """
    return _get_symbols(executable_path, [_SYMTABLE_NAME_COLUMN])


def extract_symbol_map(executable_path: str) -> dict[str, str]:
    """Extracts defined function symbol names and their addresses from the executable

    :param executable_path: path to the executable

    :return: function symbols map in form 'mangled name: hex address'
    """
    # Get the mangled function names and addresses
    symbols = _get_symbols(executable_path, [_SYMTABLE_ADDR_COLUMN, _SYMTABLE_NAME_COLUMN])
    # Create symbol map as name: address in hex format
    symbol_map = {
        symbols[i + 1]: ("0x" + symbols[i].lstrip("0")) for i in range(0, len(symbols), 2)
    }
    return symbol_map


def extract_symbol_address_map(executable_path: str) -> dict[str, str]:
    """Extracts defined function symbol addresses and demangled names

    :param executable_path: path to the executable

    :return: function symbols map in form 'hex address: demangled name'
    """
    # Get the mangled function names and addresses
    symbols = _get_symbols(executable_path, [_SYMTABLE_ADDR_COLUMN, _SYMTABLE_NAME_COLUMN])
    # Create address map as hex address: mangled name
    address_map = {
        ("0x" + symbols[i].lstrip("0")): symbols[i + 1] for i in range(0, len(symbols), 2)
    }
    # Translate the mangled names
    name_map = translate_mangled_symbols(list(address_map.values()))
    for record in address_map:
        address_map[record] = name_map[address_map[record]]
    return address_map


def translate_mangled_symbols(mangled_names: list[str]) -> dict[str, str]:
    """Translates the mangled names to their demangled counterparts

    :param mangled_names: the names to be translated

    :return: function symbols name map in form 'mangled name: demangled name'
    """
    # Transform the names to string parameter
    mangled_str = "\n".join(mangled_names)

    # Create demangled counterparts of the function names
    demangled_bytes, _ = commands.run_safely_external_command(f"echo '{mangled_str}' | c++filt")
    demangled_names = demangled_bytes.decode("utf-8").split("\n")
    if "" in demangled_names:
        demangled_names.remove("")

    # Map the names
    return dict(zip(mangled_names, demangled_names))


def filter_symbols(
    symbols: list[str], profile_rules: list[str]
) -> tuple[list[RuleKey], list[str], list[str]]:
    """Filters the function symbols and creates the static exclude and include dict

    :param symbols: function symbols mangled names extracted from an executable
    :param profile_rules: rules specifying which functions should be profiled

    :return:  list of include symbols as rule_key tuple
                    list of statically excluded function symbols
                    list of runtime filtered function symbols in mangled format
    """
    # Get the symbol name mapping
    symbols_name_map = translate_mangled_symbols(symbols)
    # Filter the functions to be profiled
    include_list, exclude_list = _apply_profile_rules(profile_rules, symbols_name_map)
    # Get the final exclude list version and runtime filter
    final_exclude_list, runtime_filter = _finalize_exclude_lists(exclude_list, include_list)
    return list(include_list.keys()), final_exclude_list, runtime_filter


def unify_sample_func(func: str) -> str:
    """Unifies the sampling function specification.

    :param func: the function prototype to be unified

    :return: str: the unified function prototype
    """
    body, args = _unify_function_format(func)
    return body + args


def _get_symbols(executable_path: str, columns: list[int]) -> list[str]:
    """Creates the pipe of linux utils to access and filter executable symbol table

    :param executable_path: path to the executable
    :param columns: symbol table column numbers which should be captured

    :return: sequential symbol table values [column1, column2, column1, ...]
    """
    # Convert the columns list to string parameter
    columns_str = ",".join(str(column) for column in columns)

    cmd = (
        "readelf -sW "
        + executable_path
        + " | awk '$4 == \"FUNC\" && $7 != \"UND\"' | awk '{$2=$2};1' | cut -d' ' -f "
        + columns_str
    )

    # Run the command to obtain function symbols
    symbols_bytes, _ = commands.run_safely_external_command(cmd)

    # Decode the bytes and create list
    symbols = symbols_bytes.decode("utf-8").replace(" ", "\n").split("\n")
    # Remove the redundant element
    if "" in symbols:
        symbols.remove("")

    return symbols


def _finalize_exclude_lists(
    exclude_list: dict[str, PrototypeParts], include_list: dict[RuleKey, PrototypeParts]
) -> tuple[list[str], list[str]]:
    """Finalizes the static exclude list, solves symbols collision in exclude / include list due
        to function overloading and identifier duplication, provides final static exclude list
        and runtime filter list.

    :param exclude_list: function symbols to be excluded as
                                'mangled name: prototype parts tuple'
    :param include_list: function symbols to be profiled as
                                'rule_key tuple: prototype parts tuple'

    :return:  list of statically excluded function identifiers
                    list of runtime filtered function symbols in mangled format
    """
    # Solves the collisions in names
    exclude_list, runtime_filter = _find_exclude_collisions(exclude_list, include_list)

    # Transform the exclude dict to the list of identifiers
    # operator is the default excluded function since it probably cannot be easily filtered and
    # clutters the performance output
    final_exclude_list = ["operator"]
    for func_identifier in (getattr(exclude_list[func], "identifier") for func in exclude_list):
        final_exclude_list.append(func_identifier)

    # Remove the duplicates if any
    return list(set(final_exclude_list)), list(runtime_filter.keys())


def _dismantle_symbols(symbol_map: dict[str, str]) -> dict[str, PrototypeParts]:
    """Decomposes all symbols from symbol map to parts to simplify rule match. The parts are:
        identifier; argument list; scoped identifier name; scoped argument list; full identifier
        name (with all template specializations); full argument list (also template specializations)

    :param symbol_map: symbol name map in form 'mangled name: demangled name'

    :return: decomposed symbol map in form 'mangled name: prototype_parts tuple'
    """
    specification_map = dict()
    for key in symbol_map.keys():
        # Process each symbol from the map
        with exceptions.SuppressedExceptions(exceptions.UnexpectedPrototypeSyntaxError):
            specification_map[key] = _process_symbol(symbol_map[key])
    return specification_map


def _process_symbol(function_prototype: str) -> PrototypeParts:
    """Decomposes the function prototype to the parts specified in _dismantle_symbols

    :param function_prototype: the full demangled function prototype name

    :return: the prototype_parts named tuple with all the function parts
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
    return PrototypeParts(
        identifier, arguments, scoped_body, scoped_args, prototype_body, prototype_args
    )


def _unify_function_format(function_prototype: str) -> tuple[str, str]:
    """Unifies the format in which are functions stored, compared etc.

    Notably all redundant whitespaces are removed, return type is removed and function
    prototype is split into prototype body and argument list.

    :param function_prototype: the 'raw' function prototype

    :return: the normalized function prototype body and argument list
    """
    # Remove the redundant whitespaces
    function_prototype = function_prototype.replace(", ", ",")
    function_prototype = function_prototype.replace(" >", ">")

    # Split the function to a body and arguments
    function_body, function_args = _split_prototype(function_prototype)
    # Remove the return type if present
    function_body = _remove_return_type(function_body)

    return function_body, function_args


def _find_argument_list_boundary(func: str) -> tuple[int, int]:
    """Finds the start and end position of function argument list specified by the parentheses

    :param func: the function to be processed

    :return: start, end position as ints, -1 if no argument list was found
    """
    # Find the argument braces in the prototype
    arg_brace = _find_all_braces(func, "(", ")")

    if len(arg_brace) == 2 and func[arg_brace[0]] == "(" and func[arg_brace[1]] == ")":
        # Braces found
        return arg_brace[0], arg_brace[1]
    elif not arg_brace:
        # No argument list
        return -1, -1
    else:
        # Unexpected number or order in parentheses
        raise exceptions.UnexpectedPrototypeSyntaxError(
            func, "unexpected number or order of parenthesis"
        )


def _find_all_braces(target: str, opening: str, ending: str) -> list[int]:
    """Finds all indices of the given 'opening':'ending' brace pairs

    :param target: the string where to find the braces
    :param opening: the opening brace
    :param ending: the ending brace

    :return: the list of brace indices
    """
    return [i for i, char in enumerate(target) if char in (opening, ending)]


def _split_prototype(function_prototype: str) -> tuple[str, str]:
    """Splits the given function prototype to its body and argument list parts

    :param function_prototype: the function to be split

    :return: function body, function argument list
    """
    arg_start, arg_end = _find_argument_list_boundary(function_prototype)
    # Split the prototype into body and argument part
    if arg_start != -1:
        return (
            function_prototype[:arg_start],
            function_prototype[arg_start : arg_end + 1],
        )
    return function_prototype, ""


def _extract_function_identifier(function_prototype: str) -> str:
    """Extracts the function identifier from its prototype

    :param function_prototype: the function prototype

    :return: the extracted function identifier
    """
    # Slice the function identifier from the left side, only scope is possible delimiter
    scope = function_prototype.rfind("::")
    if scope == -1:
        return function_prototype
    return function_prototype[scope + 2 :]


def _remove_templates(function_part: str) -> str:
    """Removes all template specifications from the function prototype or its part

    :param function_part: the function prototype part to be processed

    :return: the function part without template specifications
    """
    # Find all template braces
    braces = _find_all_braces(function_part, "<", ">")
    if not braces:
        return function_part

    # Stack-like traversing of the braces and pairing template blocks
    new_prototype = ""
    inner_level = 0
    last_end = len(function_part)
    for i in braces[::-1]:
        if function_part[i] == ">":
            if inner_level == 0:
                # New block start recognized, slice the trailing chars
                new_prototype = function_part[i + 1 : last_end] + new_prototype
            inner_level += 1
        else:
            inner_level -= 1
            if inner_level == 0:
                # End of a template block
                last_end = i

    return function_part[:last_end] + new_prototype


def _remove_return_type(function_body: str) -> str:
    """Removes the function return type (if present) from the function body,
        which should not contain the argument list!

    :param function_body: the body part of the function prototype

    :return: the function body without the return type specification
    """
    # Check if function might contain return type specification
    return_type_delim = -1
    if " " in function_body:
        control_sequence = [i for i, c in enumerate(function_body) if c in ("<", ">", " ")]
        inner_state = 0
        for i in control_sequence:
            # Find first whitespace that is not in a template specification
            if function_body[i] == "<":
                inner_state += 1
            elif function_body[i] == ">":
                inner_state -= 1
            else:
                if inner_state == 0:
                    return_type_delim = i
                    break
    # Return the new function body
    return function_body[return_type_delim + 1 :]


def _remove_argument_scopes(function_args: str) -> str:
    """Removes all type scope specification from the function argument list

    :param function_args: the function argument list in form '(...)'

    :return: the argument list without scope specification
    """
    # Empty operation on empty args
    if function_args == "":
        return function_args
    # Get the argument list
    args = function_args[1:-1].split(",")
    new_args = "("
    for arg in args:
        scope_op = arg.rfind("::")
        new_args += (arg[scope_op + 2 :] if scope_op != -1 else arg) + ","
    # Replace the last comma with end parentheses
    new_args = new_args[:-1]
    new_args += ")"

    return new_args


def _prepare_profile_rules(profile_rules: list[str]) -> dict[str, list[str]]:
    """Analyzes the profiling rules and creates their unified representation as a list of parts.
        Both body and argument part can be specified to certain level of detail, such as
        scoped identifier or fully specified identifier with template instantiation detail etc.

    :param profile_rules: the list of profiling rules specified by the user

    :return: the rule details in the form 'rule: [body part, arg part (optional)]'
    """
    details = dict()
    for rule in profile_rules:
        # First unify the function format
        function_body, function_arg = _unify_function_format(rule)
        unified_func = function_body + function_arg
        # Check how much is the rule function specified
        body_scope, body_template = _check_rule_specification_detail(function_body)
        arg_scope, arg_template = _check_rule_specification_detail(function_arg)

        # Get the body and args PrototypeParts value
        parts = [_specification_detail_to_parts(body_template, body_scope, "body")]
        if function_arg:
            parts.append(_specification_detail_to_parts(arg_template, arg_scope, "args"))

        details[unified_func] = parts
    return details


def _specification_detail_to_parts(template: bool, scope: bool, section: str) -> str:
    """Transforms the specification detail to members of the PrototypeParts

    :param template: true if template was part of the specification
    :param scope: true if the rule was scoped
    :param section: the currently inspected rule section ('body' or 'args')

    :return: the resulting PrototypeParts value
    """
    if template:
        return f"full_{section}"
    elif scope:
        return f"scoped_{section}"
    else:
        return "identifier" if section == "body" else "args"


def _check_rule_specification_detail(rule_part: str) -> tuple[bool, bool]:
    """Checks if the rule contains scope or template specifications

    :param rule_part: the part of the rule (function body or argument lit)

    :return: is scope used, is template used (True/False)
    """
    template = False
    scope = False
    if rule_part:
        # Check if rule part contains template specification
        if "<" in rule_part and ">" in rule_part:
            template = True

        # Check if rule part contains scope specifications
        if "::" in rule_part:
            scope = True

    return scope, template


def _build_symbol_from_rules(symbol_parts: PrototypeParts, rule_details: list[str]) -> str:
    """Builds the symbol from its part, which are specified in the rule details

    :param symbol_parts: the symbol parts
    :param rule_details: list of prototype_parts attribute names which are used to build the
                              symbol

    :return: the built symbol
    """
    symbol = ""
    # Build the symbol from the given parts
    for detail in rule_details:
        symbol += getattr(symbol_parts, detail)
    return symbol


def _apply_profile_rules(
    profile_rules: list[str], symbol_map: dict[str, str]
) -> tuple[dict[RuleKey, PrototypeParts], dict[str, PrototypeParts]]:
    """Applies the profiling rules given by the user to the extracted symbol table
        and thus creates the include and exclude list.

    :param profile_rules: the list of profiling rules
    :param symbol_map: symbols name map in form 'mangled name: demangled name'

    :return:  include dict in form 'rule_key tuple: prototype parts tuple'
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


def _find_exclude_collisions(
    exclude_list: dict[str, PrototypeParts], include_list: dict[RuleKey, PrototypeParts]
) -> tuple[dict[str, PrototypeParts], dict[str, PrototypeParts]]:
    """Finds the collisions in exclude and include list, which are solved by the runtime filter.

    :param exclude_list: function exclude list as 'mangled name: prototype parts tuple'
    :param include_list: function include list as 'rule_key tuple: prototype parts tuple'

    :return:  exclude dict without the collisions as 'mangled name: prototype parts tuple'
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
