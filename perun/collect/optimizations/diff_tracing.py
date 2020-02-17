"""
The Diff Tracing method is inspired by some of the recent applications of analysers
(such as FBInfer) in CI of large code-bases. In particular, these approaches optimize
the analysis process for regular, day-to-day incremental updates to the project so that
the developers can promptly analyze the found issues of (only) the freshly introduced changes.
We propose we can achieve such precisely targeted optimization by leveraging the CG and CFG
resources, as well as exploiting the integration of VCS within the Perun that grants us access
to the project history and changes associated with specific project versions.
"""


import perun.vcs as vcs
from perun.collect.optimizations.structs import DiffCfgMode


# The set of ASM JUMP instruction that are omitted during the operands check
JUMP_INSTRUCTIONS = [
    'call', 'jmp', 'je', 'jne', 'jz', 'jnz', 'jg', 'jge', 'jnle', 'jnl', 'jl', 'jle', 'jnge',
    'jng', 'ja', 'jae', 'jnbe', 'jnb', 'jb', 'jbe', 'jnae', 'jna', 'jxcz', 'jc', 'jnc', 'jo',
    'jno', 'jp', 'jpe', 'jnp', 'jpo', 'js', 'jns'
]


def diff_tracing(call_graph, call_graph_old, keep_leaf, inspect_all, cfg_mode):
    """ The Diff Tracing method.

    :param CallGraphResource call_graph: the CGR of the current project version
    :param CallGraphResource call_graph_old: the CGR of the previous project version
    :param bool keep_leaf: if set to True, changed leaf functions will be kept
    :param bool inspect_all: turns on a deep analysis of changes that includes the whole CG
    :param DiffCfgMode cfg_mode: equivalence criterion for comparing CFGs
    """
    if call_graph is None or call_graph_old is None:
        print('missing call graph')
        return
    cg_funcs = call_graph.cg_map.keys()
    # Compare the call graphs and find new, modified or renamed functions
    new, modified, renamed = _compare_cg(call_graph, call_graph_old, inspect_all)
    # Inspect the git diff output to find modified functions that are not detectable using simple
    # call graph comparison
    diff_funcs = _parse_git_diff(cg_funcs, call_graph_old.minor, call_graph.minor)
    # Exclude leaf functions since their profiling often inflicts noticeable overhead
    if not keep_leaf:
        new = set(_filter_leaves(new, call_graph))
        modified = set(_filter_leaves(modified, call_graph))
        diff_funcs = set(_filter_leaves(diff_funcs, call_graph))
    # Do not compare the cfg if function is new or already identified as modified
    cfg_candidates = (diff_funcs - new) - modified
    changes = _compare_cfgs(cfg_candidates, renamed, call_graph.cfg, call_graph_old.cfg, cfg_mode)
    call_graph.set_diff(list(new | modified | changes))


def _compare_cg(call_graph, call_graph_old, inspect_all):
    """ The call graph comparison routine

    :param CallGraphResource call_graph: the CGR of the current project version
    :param CallGraphResource call_graph_old: the CGR of the previous project version
    :param bool inspect_all: turns on a deep analysis of changes that includes the whole CG

    :return tuple: sets of new, modified and renamed function according to the CG analysis
    """
    cg_funcs, cg_old_funcs = set(call_graph.cg_map.keys()), set(call_graph_old.cg_map.keys())
    new_funcs = list(cg_funcs - cg_old_funcs)
    deleted_funcs = list(cg_old_funcs - cg_funcs)
    # Find functions that have been only renamed - compare the callers / callees sets
    renamed = {}
    if new_funcs and deleted_funcs:
        renamed = _find_renames(new_funcs, deleted_funcs, call_graph, call_graph_old)
    # Remove the renamed function from the new / deleted lists
    for rename_to, rename_from in renamed.items():
        new_funcs.remove(rename_to)
        deleted_funcs.remove(rename_from)

    # Inspect the whole call graph and identify functions that have different callees
    # Such functions should also be profiled
    modified = []
    if inspect_all:
        modified = _inspect_all(call_graph, call_graph_old, new_funcs, renamed)

    return set(new_funcs), set(modified), renamed


def _compare_cfgs(funcs, renames, cfg, cfg_old, mode):
    """ The CFG comparison routine

    :param set funcs: the set of functions that we compare CFG for
    :param dict renames: the renames mapping
    :param dict cfg: the CFGs from the current project version
    :param dict cfg_old: the CFGs from the previous project version
    :param DiffCfgMode mode: equivalence criterion for comparing CFGs

    :return set: a set of changed functions according to the CFG analysis
    """
    changes = []
    for func in funcs:
        func_blocks, cfg_edges = cfg[func]['blocks'], cfg[func]['edges']
        func_blocks_old, cfg_edges_old = cfg_old[func]['blocks'], cfg_old[func]['edges']
        # Quick check that the number of blocks and edges is equal
        if len(func_blocks) != len(func_blocks_old) or len(cfg_edges) != len(cfg_edges_old):
            changes.append(func)
            continue
        # Compare the CFG edges
        if not _compare_cfg_edges(cfg_edges, cfg_edges_old):
            changes.append(func)
            continue
        # Compare the CFG blocks according to the mode
        if not _compare_cfg_blocks(func_blocks, func_blocks_old, renames, mode):
            changes.append(func)
            continue
    return set(changes)


def _compare_cfg_edges(edges, edges_old):
    """ Compare the edges of new and old CFG

    :param list edges: the list of edges from the current CFG
    :param list edges_old: the list of edges from the previous CFG

    :return bool: True if the edges match
    """
    for (edge_from, edge_to), (edge_old_from, edge_old_to) in zip(edges, edges_old):
        if edge_from != edge_old_from or edge_to != edge_old_to:
            return False
    return True


def _compare_cfg_blocks(blocks, blocks_old, renames, mode):
    """ Compare the blocks of new and old CFG

    :param list blocks: the list of blocks from the current CFG
    :param list blocks_old: the list of blocks from the previous CFG
    :param dict renames: the function rename mapping
    :param DiffCfgMode mode: equivalence criterion for comparing CFGs

    :return bool: True if the blocks match
    """
    for block, block_old in zip(blocks, blocks_old):
        # Soft mode only compares the number of instructions
        if mode == DiffCfgMode.Soft:
            if len(block) != len(block_old):
                return False
        else:
            # The block is a function call, compare the names of the functions
            if isinstance(block, str) and isinstance(block_old, str):
                # Don't forget to apply the rename if there is one!
                if renames.get(block, block) != block_old:
                    return False
            # The block type is different
            elif isinstance(block, str) or isinstance(block_old, str):
                return False
            # The block is a list of ASM instructions and operands
            else:
                for (instr, op), (instr_old, op_old) in zip(block, block_old):
                    # Semi-strict mode checks only that the instructions are the same
                    if instr != instr_old:
                        return False
                    # Strict mode also checks the operands unless they are calls or jumps
                    # (both conditional and unconditional) since the address can be different
                    # but refer to the same CFG block - this jump / call destinations is however
                    # already covered by the CFG edges
                    if mode == DiffCfgMode.Strict and instr not in JUMP_INSTRUCTIONS:
                        if op != op_old:
                            return False
    return True


def _filter_leaves(funcs, cg):
    """ Filter leaf functions

    :param set funcs: the set of functions to filter
    :param CallGraphResource cg: the corresponding CGR

    :return list: list of non-leaf functions
    """
    return [func for func in funcs if not cg[func]['leaf']]


def _inspect_all(call_graph, call_graph_old, new_funcs, renamed):
    """ Performs deep analysis of the CG structure in order to find differences

    :param CallGraphResource call_graph: the CGR of the current project version
    :param CallGraphResource call_graph_old: the CGR of the previous project version
    :param list new_funcs: a collection of new functions
    :param dict renamed: the function rename mapping

    :return list: a collection of changed function nodes
    """
    changed = []
    for func in call_graph.cg_map.values():
        # Skip functions that are new (since they will be profiled anyway)
        # or renamed (no need to check twice)
        if func['name'] in new_funcs or func['name'] in renamed:
            continue
        # Obtain the new and old callees with respect to the renames
        _, callees = _get_callers_and_callees(func['name'], call_graph, renamed)
        _, old_callees = _get_callers_and_callees(func['name'], call_graph_old)
        # If the callees are not identical, the function should be profiled
        if callees != old_callees:
            changed.append(func['name'])
    return changed


def _find_renames(new_funcs, del_funcs, cg, cg_old):
    """ Creates the renames mapping

    :param list new_funcs: a collection of new functions
    :param list del_funcs: a collection of deleted functions
    :param CallGraphResource cg: the CGR of the current project version
    :param CallGraphResource cg_old: the CGR of the previous project version

    :return dict: the renames mapping
    """
    renamed = {}
    # Get the new functions sorted by level in descending order
    new_funcs = cg.sort_by_level(new_funcs)
    # Get the deleted functions sorted by level and also obtain their callers / callees
    deleted_funcs = []
    for del_name, _ in cg_old.sort_by_level(del_funcs):
        deleted_funcs.append((del_name, _get_callers_and_callees(del_name, cg_old)))

    # Iterate the new functions and compare the callers / callees
    for new_name, _ in new_funcs:
        callers, callees = _get_callers_and_callees(new_name, cg, renamed)
        for idx, (del_name, (del_callers, del_callees)) in enumerate(deleted_funcs):
            # If the callers / callees match, then we assume that rename took place
            if callers == del_callers and callees == del_callees:
                renamed[new_name] = del_name
                # We want 1:1 mapping for every renamed function so terminate the loop
                del deleted_funcs[idx]
                break
    return renamed


def _get_callers_and_callees(func_name, cg, rename_map=None):
    """ Obtain callers and callees for a specified function

    :param str func_name: the function name
    :param CallGraphResource cg: the CGR of the current project version
    :param dict rename_map: the renames mapping

    :return tuple: (callers, callees)
    """
    func = cg[func_name]
    callers, callees = func['callers'], func['callees']
    return set(_rename_funcs(callers, rename_map)), set(_rename_funcs(callees, rename_map))


def _rename_funcs(collection, rename_map=None):
    """ Rename functions in the collection according to the rename mapping.

    :param iterable collection: the collection of function names
    :param dict rename_map: the rename mapping

    :return iterable: the initial collection with some renamed functions
    """
    if rename_map is None:
        return collection
    new_collection = []
    for name in collection:
        # Map the old name to the new name, if the mapping exists, otherwise use the name as is
        new_collection.append(rename_map.get(name, name))
    return new_collection


def _parse_git_diff(funcs, version_1, version_2):
    """ Parse the output of Git diff applied to two different project versions.

    :param list funcs: a collection of all functions
    :param str version_1: identification of the first project version
    :param str version_2: identification of the second project version

    :return set: a set of modified functions according to the git diff
    """
    diff_output = vcs.minor_versions_diff(version_1, version_2)
    modified_funcs = []
    # Iterate the lines and search for hunk headers
    for line in diff_output.splitlines():
        # Identify the hunk header
        if not line.startswith('@@'):
            continue
        # Remove the hunk
        hunk_end = line.find('@@', 2)
        if hunk_end == -1:
            continue
        # The rest of the line may contain the git function context
        context_func = line[hunk_end + 2:]
        # Find the possible starts of a parameter list
        args_candidates = [idx for idx, char in enumerate(context_func) if char == '(']
        # Test the identifier before the potential parameter list
        for func_args in args_candidates:
            func_name_candidate = context_func[:func_args].split()[-1]
            if func_name_candidate in funcs:
                modified_funcs.append(func_name_candidate)
                break
    return set(modified_funcs)
