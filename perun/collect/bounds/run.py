"""Wrapper of the loopus and looper tools.

First compiles the given sources using clang into LLVM IR representation,
each compiled file is then analysed by loopus. The output of loopus is finally
parsed by internal scanner resulting into profile.
"""
from __future__ import annotations

# Standard Imports
from subprocess import SubprocessError
from typing import Any
import os
import shutil
import time as systime

# Third-Party Imports
import click

# Perun Imports
from perun.collect.bounds import parser
from perun.logic import runner
from perun.utils import log
from perun.utils.external import commands
from perun.utils.structs import CollectStatus

_CLANG_COMPILER = "clang-3.5"
_CLANG_COMPILATION_PARAMS = ["-g", "-emit-llvm", "-c"]
_LLVM_EXT = ".bc"
_LIB_Z3 = "libz3.so"


def before(sources: list[str], **kwargs: Any) -> tuple[CollectStatus, str, dict[str, Any]]:
    """Compiles the sources into LLVM intermediate code

    $ clang-3.5 -g -emit-llvm -c ${sources}
    """
    log.major_info("Compiling to LLVM", no_title=True)
    pwd = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
    include_path = os.path.join(pwd, "include")
    clang_bin = (
        _CLANG_COMPILER if shutil.which(_CLANG_COMPILER) else os.path.join(pwd, _CLANG_COMPILER)
    )
    log.minor_status(f"{log.highlight('clang')} found", status=log.path_style(clang_bin))
    cmd = " ".join([clang_bin] + ["-I", include_path] + _CLANG_COMPILATION_PARAMS + list(sources))

    log.minor_status("Compiling source codes", status=f"{','.join(sources)}")
    my_env = os.environ.copy()
    my_env["LD_LIBRARY_PATH"] = pwd
    try:
        commands.run_safely_external_command(cmd, check_results=True, env=my_env, quiet=False)
    except SubprocessError as sub_err:
        log.minor_fail("Compiling to LLVM")
        return CollectStatus.ERROR, str(sub_err), dict(kwargs)

    log.minor_success("Compiling to LLVM")
    return CollectStatus.OK, "status_message", dict(kwargs)


def collect(sources: list[str], **kwargs: Any) -> tuple[CollectStatus, str, dict[str, Any]]:
    """Runs the Loopus on compiled LLVM sources

        $ export $LD_LIBRARY_PATH="${DIR}/libz3.so"
        $ ./loopus -zPrintComplexity ${src}.bc

    Finally, parses the output of Loopus into a profile
    """
    log.major_info("Running Loopus")
    pwd = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
    loopus_bin = os.path.join(pwd, "loopus")
    source_filenames = [os.path.splitext(os.path.split(src)[1])[0] + _LLVM_EXT for src in sources]
    my_env = os.environ.copy()
    my_env["LD_LIBRARY_PATH"] = pwd

    log.minor_status(f"{log.highlight('Loopus')} found at", status=log.path_style(loopus_bin))
    log.minor_status(
        "Running Loopus on compiled source codes", status=f"{' '.join(source_filenames)}"
    )

    before_analysis = systime.time()
    try:
        cmd = (
            loopus_bin
            + " -zPrintComplexity -zEnableOptimisticAssumptionsOnPointerAliasAndShapes "
            + " ".join(source_filenames)
        )
        returned_out, _ = commands.run_safely_external_command(cmd, check_results=True, env=my_env)
        out = returned_out.decode("utf-8")
    except SubprocessError as sub_err:
        log.minor_fail("Collection of bounds")
        return CollectStatus.ERROR, str(sub_err), dict(kwargs)
    overall_time = systime.time() - before_analysis
    log.minor_success("Collection of bounds")

    # Parse the out, but first fix the one file analysis, which has different format
    if len(sources) == 1:
        out = f"file {source_filenames[0]}\n" + out
    source_map = {bc: src for (bc, src) in zip(source_filenames, sources)}
    resources = parser.parse_output(out, source_map)
    log.minor_success("Parsing collected output")

    return (
        CollectStatus.OK,
        "status message",
        {"profile": {"global": {"timestamp": overall_time, "resources": resources}}},
    )


def lookup_source_files(ctx: click.Context, __: click.Option, value: list[str]) -> list[str]:
    """Looks up sources for the analysis.

    The sources can either be single file, or directory which contains .c files.

    :param Context ctx: context of the called command
    :param click.Option __: parameter that is being parsed and read from commandline
    :param str value: value that is being read from the commandline
    """
    # Initialize sources if it does not exist
    if "sources" not in ctx.params.keys():
        ctx.params["sources"] = []

    # Walk through the file directory and collect files
    for src in value:
        if os.path.isdir(src):
            for root, _, files in os.walk(src):
                for file in files:
                    if os.path.splitext(file)[1] in {".c"}:
                        ctx.params["sources"].append(os.path.join(root, file))
        elif os.path.splitext(src)[1] in {".c"}:
            ctx.params["sources"].append(src)
    return value


@click.command()
@click.pass_context
@click.option(
    "--source",
    "--src",
    "-s",
    type=click.Path(exists=True, resolve_path=True),
    multiple=True,
    metavar="<path>",
    callback=lookup_source_files,
    help="Source C file that will be analyzed.",
)
@click.option(
    "--source-dir",
    "-d",
    type=click.Path(resolve_path=True),
    multiple=True,
    metavar="<dir>",
    callback=lookup_source_files,
    help=(
        "Directory, where source C files are stored. All of the existing files with "
        "valid extensions (.c)."
    ),
)
def bounds(ctx: click.Context, **kwargs: Any) -> None:
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

      Refer to :ref:`collectors-bounds` for more thorough description and
      examples of `bounds` collector.
    """
    runner.run_collector_from_cli_context(ctx, "bounds", kwargs)
