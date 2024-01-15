"""Parse parses the result of the Loopus analyzer.

The example of the format is as follows:
--------------------------------------
file partitioning.bc

 Function nondetnon2


Total Complexity: O(1)

 Function bench_vmcai_bench_003_partitioning

    line 34 / 42
    1 + max(0, (k + -1))
    O(n^1)
      line 55 / 58
      1 + max(0, (k + -1))
      O(n^1)
    line 64 / 69
    2 + max(0, (k + -1))
    O(n^1)

Total Complexity: O(n^1)

--------------------------------------
file func-queue.bc

 Function bench_vmcai_bench_008_func_queue

    line 29 / 58
    1 + max(k, 0)
    O(n^1)
      line 47 / 54
      max(k, 0)
      O(n^1)
    line 61 / 65
    FAILED to compute RF  ( RFComputationFailed)

Total Complexity: FAILED

"""
from __future__ import annotations

# Standard Imports
from typing import Callable, Any
import re

# Third-Party Imports

# Perun Imports

RE_FUNCTION = re.compile(r"Function (?P<funcname>\S+)")
RE_FILE = re.compile(r"file (?P<filename>\S+)")
RE_LINE = re.compile(r"line (?P<line>\d+) / (?P<column>\d+)")
RE_TOTAL = re.compile(r"Total Complexity: (?P<total>.+)")


def partition_list(source_list: list[str], pred: Callable[[str], bool]) -> list[list[str]]:
    """Helper function that partitions the list to several chunks according to the given predicate.

    First we find all the elements of the list that satisfy @p pred, then we break the list into
    chunks between these indexes.

    :param list source_list:
    :param pred:
    :return:
    """
    starts = [i for (i, element) in enumerate(source_list) if pred(element)]
    ends = starts[1:] + [len(source_list)]
    partitions = [source_list[start:end] for (start, end) in zip(starts, ends)]
    return partitions


def parse_file(file_info: str, source_map: dict[str, str]) -> list[dict[str, Any]]:
    """Parses the result of analysis of single file

    Each file consist of several functions which are preceded by keyword Function and the function
    name. Then a list of individual bounds for each cycle in the function is listed.

    :param str file_info: result of analysis of one single file
    :param dict source_map: mapping of compiled files to real sources
    :return: list of resources
    """
    filtered_file = list(filter(lambda line: not re.match(r"^\s*$", line), file_info.split("\n")))
    file_match = RE_FILE.search(filtered_file[0])
    file_name = file_match.group("filename") if file_match else "<unknown_filename>"
    resources = []
    for func in partition_list(filtered_file, lambda x: "Function" in x):
        resources.extend(parse_function(func, source_map[file_name]))
    return resources


def lookup_function_location(
    function_name: str, file_name: str, lines_for_bounds: list[int]
) -> tuple[int, int]:
    """For given function, finds its location in the file, i.e. the line and column.

    If no bounds were inferred we return 0, 0, since we do not really precisely detect the position.

    :param str function_name: name of the looked-up function
    :param str file_name: source file, where function is defined
    :param list lines_for_bounds: list of inferred bounds
    :return: line and column of the definition of given function
    """
    if not lines_for_bounds:
        return 0, 0
    with open(file_name, "r") as fp:
        lines = fp.readlines()
    line = [
        (i, l) for (i, l) in enumerate(lines) if function_name in l and i < min(lines_for_bounds)
    ]
    prototype_lineno, prototype_line = line[-1]
    return prototype_lineno, prototype_line.find(function_name)


def parse_function(func_info: list[str], file_name: str) -> list[dict[str, Any]]:
    """Parses the result of analysis for single function.

    Each function consists of several bounds, for each cycle in the function (since non-cycles has
    constant bounds).

    Each result is one of the following forms:

      1. The bounds were successfully analysed. Then Loopus returns bound (i.e. ranking function)
         and complexity class of the cycle (i.e. the highest polynom, such as n^2, etc.)
        line <row> / <col>
        <bound>
        O(<class>)

      2. The bounds could not be inferred. This is usually caused by either non-determinism, or
         conditions that are not modelled in Loopus, such as those involving heap or data fields.

        line <row> / <col>
        FAILED to compute RF  ( RFComputationFailed)

    :param list func_info: list of lines in function
    :param str file_name: the name of the analysed file that contains the function
    :return: list of resources
    """
    resources = []
    collective_bounds = []
    collective_lines = []
    total_complexity_line = func_info[-1].replace("\u001b[37;31mFAILED\u001b[0m", "FAILED").strip()
    function_match = RE_FUNCTION.search(func_info[0])
    function_name = function_match.group("funcname") if function_match else "<unknown function>"
    for resource in partition_list(func_info[1:-1], lambda x: "line" in x):
        line_match = RE_LINE.search(resource[0])
        line = line_match.group("line") if line_match else -1
        col = line_match.group("column") if line_match else -1
        if len(resource) == 3:
            # Case (1): the bounds were successfully inferred;
            bound = resource[1].strip()
            class_of_bound = resource[2].strip()
        else:
            # Case (2): the bounds could not be inferred
            bound = resource[1].replace("\u001b[37;31mFAILED\u001b[0m", "FAILED").strip()
            class_of_bound = "O(∞)"
        collective_bounds.append(bound)
        collective_lines.append(int(line))
        resources.append(
            {
                "uid": {
                    "function": function_name,
                    "line": int(line),
                    "column": int(col),
                    "source": file_name,
                },
                "bound": bound,
                "class": class_of_bound,
                "type": "local bound",
            }
        )

    line, column = lookup_function_location(function_name, file_name, collective_lines)
    total_class = total_complexity_line.split(":", 1)[1].strip()
    resources.append(
        {
            "uid": {
                "function": function_name,
                "line": line,
                "column": column,
                "source": file_name,
            },
            "bound": total_class if "FAILED" in total_class else " + ".join(collective_bounds),
            "class": "O(∞)" if "FAILED" in total_class else total_class,
            "type": "total bound",
        }
    )

    return resources


def parse_output(output: str, source_map: dict[str, str]) -> list[dict[str, Any]]:
    """Parses the output of Loopus in the list of resources.

    Each resource specifies the collection fo bounds of functions specified in files.

    :param str output: string output of the Loopus; format is specified above at docstring
    :param dict source_map: mapping of compiled files to real sources
    :return: list of resources
    """
    files = [finfo for finfo in output.split("--------------------------------------\n") if finfo]
    resources = []
    for file_info in files:
        resources.extend(parse_file(file_info, source_map))
    return resources
