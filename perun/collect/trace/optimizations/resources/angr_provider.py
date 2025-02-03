"""The wrapper for invoking angr tool since Perun currently runs on Python 3.5 which is
incompatible with angr atm.

"""

import os
import angr

import perun.logic.stats as stats
from perun.utils.exceptions import StatsFileNotFoundException, SuppressedExceptions


def extract(stats_name, binary, cache, **kwargs):
    """Extract the Call Graph and Control Flow Graph representation using the angr framework.

    When caching is enabled and the current project version already has a call graph object
    stored in the 'stats' directory, the cached version is used instead of extracting.

    :param stats_name: name of the call graph stats file name
    :param binary: path to the binary executable file
    :param cache: sets the cache on / off mode
    :param kwargs: additional optional parameters

    :return: the extracted and transformed CG and CFG dictionaries
    """
    # Attempt to retrieve the call graph for the given configuration if it already exists
    if cache:
        with SuppressedExceptions(StatsFileNotFoundException):
            return stats.get_stats_of(stats_name, ["perun_cg"]).get("perun_cg", {})

    # Otherwise extract the call graph using angr
    # Load the binary (and selected libs) into internal representation
    libs = kwargs.get("libs", [])
    proj = angr.Project(binary, load_options={"auto_load_libs": False, "force_load_libs": libs})

    # Set parameters for Control Flow Graph analysis
    cfg_params = {"normalize": True}
    # Restricted search means that we want to analyze only functions reachable from main which
    # represents the program starting point
    if kwargs.get("restricted_search", True):
        main = proj.loader.main_object.get_symbol("main")
        cfg_params.update(
            {
                "function_starts": [main.rebased_addr],
                "start_at_entry": False,
                "symbols": False,
                "function_prologues": False,
                "force_complete_scan": False,
            }
        )

    # Run the CFG analysis to obtain the graphs
    cfg = proj.analyses.CFGFast(**cfg_params)
    # Separate the CG and CFG from the resulting output data
    binaries = [os.path.basename(target) for target in [binary] + libs]
    return {
        "call_graph": extract_cg(cfg, binaries),
        "control_flow": extract_func_cfg(proj, binaries),
    }


def extract_cg(cfg, binaries):
    """Extracts the call graph nodes and edges from the angr knowledge base, and constructs
    dictionary that represents the call graph in a better way for further processing.

    Specifically, every dictionary key represents function name and contains sorted list of its
    identified callees.

    :param cfg: the CFG analysis output structure
    :param binaries: the names of the binary executable files

    :return: the resulting call graph dictionary
    """
    # Inspired by the angrutils callgraph extraction
    addr_to_func = {}
    for cg_func in cfg.kb.callgraph.nodes():
        kb_func = cfg.kb.functions.get(cg_func, None)
        if kb_func is not None and kb_func.binary_name in binaries:
            # Identify functions optimized by the compiler and obtain the base function
            optimized_func = kb_func.name.split(".")
            if len(optimized_func) > 1:
                addr_to_func[cg_func] = optimized_func[0]
            else:
                addr_to_func[cg_func] = kb_func.name

    func_map = {name: [] for name in addr_to_func.values()}
    for cg_source, cg_dest in cfg.kb.callgraph.edges():
        if cg_source in addr_to_func and cg_dest in addr_to_func:
            func_map[addr_to_func[cg_source]].append(addr_to_func[cg_dest])
    # Make sure there are no duplicate callees
    for func, callee_list in func_map.items():
        func_map[func] = sorted(list(set(callee_list)))
    return func_map


def extract_func_cfg(project, binaries):
    """Extracts the control flow graph nodes and edges from the angr knowledge base, and
    constructs CFG dictionary that is used for further processing.

    The dictionary has the following structure:
    {'func':
        {'blocks': [str or lists], # string names of function calls or lists of instructions
        'edges': [[int, int]] # pairs representing the blocks indices connected by an edge
    }

    :param project: the loaded angr Project
    :param binaries: the names of the binary executable files

    :return: the resulting call graph dictionary
    """
    # Inspired by the angrutils func graph extraction
    cfgs = {}
    addr_to_pos = {}
    for func in project.kb.functions.values():
        if func.binary_name not in binaries:
            continue
        cfg = cfgs.setdefault(func.name.split(".")[0], {})
        blocks = []
        for idx, block in enumerate(func.transition_graph.nodes):
            blocks.append(block)
            addr_to_pos[block.addr] = idx
        blocks.sort(key=lambda item: item.addr)
        cfg["blocks"] = [_build_block_repr(project, block) for block in blocks]
        cfg["edges"] = [
            (addr_to_pos[e_from.addr], addr_to_pos[e_to.addr])
            for e_from, e_to in func.transition_graph.edges
        ]
    return cfgs


def _build_block_repr(project, block):
    """Create a CFG block representation based on the basic block type.

    We distinguish two block types: Function and Instruction Block, where the former is
    represented as a string and the latter as a list of instructions + operands.

    :param project: the loaded angr Project
    :param block: the Angr block object

    :return: the basic block representation
    """
    # Function call blocks are represented by the function name
    if isinstance(block, angr.knowledge_plugins.Function):
        return block.name.split(".")[0]

    # Obtain the ASM instructions and parameters for each block
    instr = angr.Block(block.addr, project=project, size=block.size).capstone.insns
    return [(i.insn.mnemonic, i.insn.op_str) for i in instr]
