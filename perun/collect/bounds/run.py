"""Wrapper of the loopus and looper tools.

First compiles the given sources using clang into LLVM IR representation,
each compiled file is then analysed by loopus. The output of loopus is finally
parsed by internal scanner resulting into profile.
"""

import os
import shutil
import time as systime

from subprocess import SubprocessError
from typing import List, Tuple, Dict

import click

import perun.collect.bounds.parser as parser
import perun.logic.runner as runner
import perun.utils.log as log
import perun.utils as utils
from perun.utils.structs import CollectStatus

_CLANG_COMPILER = 'clang-3.5'
_CLANG_COMPILATION_PARAMS = ['-g', '-emit-llvm', '-c']
_LLVM_EXT = '.bc'
_LIB_Z3 = "libz3.so"


def before(sources: List[str], **kwargs: Dict) -> Tuple[CollectStatus, str, Dict]:
    """Compiles the sources into LLVM intermediate code

        $ clang-3.5 -g -emit-llvm -c ${sources}
    """
    pwd = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bin')
    include_path = os.path.join(pwd, 'include')
    clang_bin = \
        _CLANG_COMPILER if shutil.which(_CLANG_COMPILER) else os.path.join(pwd, _CLANG_COMPILER)
    cmd = " ".join([clang_bin] + ['-I', include_path] + _CLANG_COMPILATION_PARAMS + list(sources))
    log.info("Compiling source codes: {}".format(
        ",".join(sources)
    ))
    my_env = os.environ.copy()
    my_env['LD_LIBRARY_PATH'] = pwd
    try:
        utils.run_safely_external_command(cmd, check_results=True, env=my_env, quiet=False)
    except SubprocessError as sub_err:
        log.failed()
        return CollectStatus.ERROR, str(sub_err), dict(kwargs)

    log.done()
    return CollectStatus.OK, "status_message", dict(kwargs)


def collect(sources: List[str], **kwargs: Dict) -> Tuple[CollectStatus, str, Dict]:
    """Runs the Loopus on compiled LLVM sources

        $ export $LD_LIBRARY_PATH="${DIR}/libz3.so"
        $ ./loopus -zPrintComplexity ${src}.bc

    Finally, parses the output of Loopus into a profile
    """
    pwd = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bin')
    loopus_bin = os.path.join(pwd, 'loopus')
    source_filenames = [os.path.splitext(os.path.split(src)[1])[0] + _LLVM_EXT for src in sources]
    my_env = os.environ.copy()
    my_env['LD_LIBRARY_PATH'] = pwd

    log.info("Running Loopus on compiled source codes: {}". format(
        " ".join(source_filenames)
    ))

    before_analysis = systime.time()
    try:
        cmd = loopus_bin \
              + " -zPrintComplexity -zEnableOptimisticAssumptionsOnPointerAliasAndShapes " \
              + " ".join(source_filenames)
        out, _ = utils.run_safely_external_command(cmd, check_results=True, env=my_env)
        out = out.decode('utf-8')
    except SubprocessError as sub_err:
        log.failed()
        return CollectStatus.ERROR, str(sub_err), dict(kwargs)
    overall_time = systime.time() - before_analysis

    # Parse the out, but first fix the one file analysis, which has different format
    if len(sources) == 1:
        out = "file {}\n".format(source_filenames[0]) + out
    source_map = {
        bc: src for (bc, src) in zip(source_filenames, sources)
    }
    resources = parser.parse_output(out, source_map)

    log.done()
    return CollectStatus.OK, "status message", {'profile': {
        'global': {
            'timestamp': overall_time,
            'resources': resources
        }
    }}


def lookup_source_files(ctx: click.Context, _: click.Option, value: List[str]) -> List[str]:
    """Lookus up sources for the analysis.

    The sources can either be single file, or directory which contains .c files.

    :param Context ctx: context of the called command
    :param click.Option _: parameter that is being parsed and read from commandline
    :param str value: value that is being read from the commandline
    """
    # Initialize sources if it does not exist
    if 'sources' not in ctx.params.keys():
        ctx.params['sources'] = []

    # Walk through the file directory and collect files
    for src in value:
        if os.path.isdir(src):
            for root, _, files in os.walk(src):
                for file in files:
                    if os.path.splitext(file)[1] in {'.c'}:
                        ctx.params['sources'].append(os.path.join(root, file))
        elif os.path.splitext(src)[1] in {'.c'}:
            ctx.params['sources'].append(src)
    return value


@click.command()
@click.pass_context
@click.option('--source', '--src', '-s', type=click.Path(exists=True, resolve_path=True),
              multiple=True, metavar='<path>', callback=lookup_source_files,
              help='Source C file that will be analyzed.')
@click.option('--source-dir', '-d', type=click.Path(resolve_path=True), multiple=True,
              metavar='<dir>', callback=lookup_source_files,
              help='Directory, where source C files are stored. All of the existing files with '
                   'valid extensions (.c).')
def bounds(ctx: click.Context, **kwargs: Dict):
    """Generates `memory` performance profile, capturing memory allocations of
    different types along with target address and full call trace.

    \b
      * **Limitations**: C/C++ binaries
      * **Metric**: `memory`
      * **Dependencies**: ``libunwind.so`` and custom ``libmalloc.so``
      * **Default units**: `B` for `memory`

    The following snippet shows the example of resources collected by `memory`
    profiler. It captures allocations done by functions with more detailed
    description, such as the type of allocation, trace, etc.


  .. code-block:: json

    \b
    {
            "uid": {
                "source": "../test.c",
                "function": "main",
                "line": 22
                "column": 40
            }
            "bound": "1 + max(0, (k + -1))",
            "class": "O(n^1)"
            "type": "bound",
    }


    `Memory` profiles can be efficiently interpreted using :ref:`views-heapmap`
    technique (together with its `heat` mode), which shows memory allocations
    (by functions) in memory address map.

    Refer to :ref:`collectors-memory` for more thorough description and
    examples of `memory` collector.
    """
    runner.run_collector_from_cli_context(ctx, 'bounds', kwargs)
