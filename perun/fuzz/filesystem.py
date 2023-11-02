""" Module contains functions dedicated for various operations over files and directories in
file system, helpful for fuzzing process."""
from __future__ import annotations

import os
import os.path as path
import re

from perun.fuzz.structs import Mutation, FuzzingProgress
import perun.utils.log as log
import perun.utils.helpers as helpers


def get_corpus(workloads: list[str], pattern: str) -> list[Mutation]:
    """Iteratively search for files to fill input corpus.

    :param list workloads: list of paths to sample files or directories of sample files
    :param str pattern: regular expression for filtering the workloads
    :return list: list of dictonaries, dictionary contains information about file
    """
    init_seeds = []

    try:
        filter_regexp = re.compile(pattern)
    except re.error:
        filter_regexp = re.compile("")

    for workload in workloads:
        if path.isdir(workload) and os.access(workload, os.R_OK):
            for root, _, files in os.walk(workload):
                if files:
                    init_seeds.extend(
                        [
                            Mutation(path.join(path.abspath(root), filename), [], None)
                            for filename in files
                            if filter_regexp.match(filename)
                        ]
                    )
        else:
            init_seeds.append(Mutation(path.abspath(workload), [], None))
    return init_seeds


def move_file_to(filename: str, directory: str) -> str:
    """Useful function for moving file to the special output directory.

    :param str filename: path to a file
    :param str directory: path of destination directory, where file should be moved
    :return str: new path of the moved file
    """
    _, file = path.split(filename)
    os.rename(filename, os.path.join(directory, file))
    return os.path.join(directory, file)


def make_output_dirs(output_dir: str, new_dirs: list[str]) -> dict[str, str]:
    """Creates special output directories for diffs and mutations causing fault or hang.

    :param str output_dir: path to user-specified output directory
    :param list new_dirs: names of new directories
    :return list: paths to newly created directories
    """
    dirs_dict = {}
    for dir_name in new_dirs:
        os.makedirs(os.path.join(output_dir, dir_name), exist_ok=True)
        dirs_dict[dir_name] = os.path.join(output_dir, dir_name)
    return dirs_dict


def del_temp_files(
    parents: list[Mutation], fuzz_progress: FuzzingProgress, output_dir: str
) -> None:
    """Deletes temporary files that are not positive results of fuzz testing

    :param list parents: list of parent mutations
    :param FuzzingProgress fuzz_progress: progress of the fuzzing
    :param str output_dir: path to directory, where fuzzed files are stored
    """
    log.info("Removing remaining mutations", end="")
    for mutation in parents:
        if (
            mutation not in fuzz_progress.final_results
            and mutation not in fuzz_progress.hangs
            and mutation not in fuzz_progress.faults
            and mutation.path.startswith(output_dir)
            and path.isfile(mutation.path)
        ):
            with helpers.SuppressedExceptions(FileNotFoundError):
                os.remove(mutation.path)
                log.info(".")
        log.info("-")
    log.done()
