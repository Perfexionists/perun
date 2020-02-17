""" Extracts the call graph and control flow graph structures from binary using the
angr framework: http://angr.io/. Note that angr does not support Python <= 3.5, well,
thus angr might need to be invoked as a separate process by Python 3.6+.

"""

import os
import sys
import json
import angr
from angr.knowledge_plugins.functions.function import Function


def extract_from(project, result):
    """ Extracts the call graph and control flow graph from the specified project (i.e., binary)
    in the DiGraph structure.

    :param str project: path to the binary executable file that is to be analyzed
    :param str result: path to the output file where we store the graphs in json format
    """
    # Load the binary into internal representation, ignore libraries and locate main
    proj = angr.Project(project, load_options={'auto_load_libs': False})
    main = proj.loader.main_object.get_symbol("main")
    binary = os.path.basename(project)
    # Run the CFG analysis to obtain the graphs, focus only on functions reachable from main
    cfg = proj.analyses.CFGFast(
        normalize=True, function_starts=[main.rebased_addr], start_at_entry=False, symbols=False,
        function_prologues=False, force_complete_scan=False
    )

    # The resulting output data separate the CG and CFG
    cfg_data = {
        'call_graph': extract_cg(cfg, binary),
        'control_flow': extract_func_cfg(proj, binary)
    }
    with open(result, 'w') as cg_handle:
        json.dump(cfg_data, cg_handle, indent=2)


def extract_cg(cfg, binary):
    """ Extracts the call graph nodes and edges from the angr knowledge base, and constructs
    dictionary that represents the call graph in a better way for further processing.

    Specifically, every dictionary key represents function name and contains sorted list of its
    identified callees.

    :param cfg: the CFG analysis output structure
    :param str binary: the name of the binary executable file

    :return dict: the resulting call graph dictionary
    """
    # Inspired by the angrutils callgraph extraction
    addr_to_func = {}
    for cg_func in cfg.kb.callgraph.nodes():
        kb_func = cfg.kb.functions.get(cg_func, None)
        if kb_func is not None and kb_func.binary_name == binary:
            # Identify functions optimized by the compiler and obtain the base function
            optimized_func = kb_func.name.split('.')
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


def extract_func_cfg(project, binary):
    """ Extracts the control flow graph nodes and edges from the angr knowledge base, and
    constructs CFG dictionary that is used for further processing.

    The dictionary has the following structure:
    {'func':
        {'blocks': [str or lists], # string names of function calls or lists of instructions
        'edges': [[int, int]] # pairs representing the blocks indices connected by an edge
    }

    :param project: the loaded angr Project
    :param str binary: the name of the binary executable file

    :return dict: the resulting call graph dictionary
    """
    # Inspired by the angrutils func graph extraction
    cfgs = {}
    addr_to_pos = {}
    for func in project.kb.functions.values():
        if func.binary_name != binary:
            continue
        cfg = cfgs.setdefault(func.name, {})
        blocks = []
        for idx, block in enumerate(func.transition_graph.nodes):
            blocks.append(block)
            addr_to_pos[block.addr] = idx
        blocks.sort(key=lambda item: item.addr)
        cfg['blocks'] = [_build_block_repr(project, block) for block in blocks]
        cfg['edges'] = [
            (addr_to_pos[e_from.addr], addr_to_pos[e_to.addr])
            for e_from, e_to in func.transition_graph.edges
        ]
    return cfgs


def _build_block_repr(project, block):
    """ Create a CFG block representation based on the basic block type.

    We distinguish two block types: Function and Instruction Block, where the former is
    represented as a string and the latter as a list of instructions + operands.

    :param project: the loaded angr Project
    :param block: the Angr block object

    :return str or list: the basic block representation
    """
    # Function call blocks are represented by the function name
    if isinstance(block, Function):
        return block.name
    # Obtain the ASM instructions and parameters for each block
    else:
        instr = angr.Block(block.addr, project=project, size=block.size).capstone.insns
        return [(i.insn.mnemonic, i.insn.op_str) for i in instr]


# Run the main extraction function
if __name__ == '__main__':
    extract_from(sys.argv[1], sys.argv[2])
    exit(0)
