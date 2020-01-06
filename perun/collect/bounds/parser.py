"""Parse parses the result of the loopus analyzer.

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
import re

RE_FUNCTION = re.compile(r"Function (?P<funcname>\S+)")
RE_FILE = re.compile(r"file (?P<filename>\S+)")
RE_LINE = re.compile(r"line (?P<line>\d+) / (?P<column>\d+)")
RE_TOTAL = re.compile(r"Total Complexity: (?P<total>.+)")


def partition_list(source_list, pred):
    """Helper function that partitions the list to several chunks according to the given predicate.

    First we find all of the elements of the list that satisfy @p pred, then we break the list into
    chunks between these indexes.

    :param list source_list:
    :param pred:
    :return:
    """
    starts = [i for (i, element) in enumerate(source_list) if pred(element)]
    ends = starts[1:] + [len(source_list)]
    partitions = [
        source_list[start:end] for (start, end) in zip(starts, ends)
    ]
    return partitions


def parse_file(file_info):
    """Parses the result of analysis of single file

    Each file consist of several functions which are preceeded by keyword Function and the function
    name. Then a list of individual bounds for each cycle in the function is listed.

    :param str file_info: result of analysis of one single file
    :return: list of resources
    """
    filtered_file = list(filter(lambda line: not re.match(r"^\s*$", line), file_info.split("\n")))
    file_name = RE_FILE.search(filtered_file[0]).group('filename')
    resources = []
    for func in partition_list(filtered_file, lambda x: 'Function' in x):
        resources.extend(parse_function(func, file_name))
    return resources


def parse_function(func_info, file_name):
    """Parses the result of analysis for single function.

    Each function consists of several bounds, for each cycle in the function (since non-cycles has
    constant bounds).

    Each results is of one of the following forms:

      1. The bounds was successfully analysed. Then loopus returns bound (i.e. ranking function)
         and complexity class of the cycle (i.e. the highest polynom, such as n^2, etc.)
        line <row> / <col>
        <bound>
        O(<class>)

      2. The bounds could not be inferred. This is usually caused by either non-determinism, or
         conditions that are not modelled in loopus, such as those involving heap or data fields.

        line <row> / <col>
        FAILED to compute RF  ( RFComputationFailed)

    :param list func_info: list of lines in function
    :param str file_name: the name of the analysed file that contains the function
    :return: list of resources
    """
    resources = []
    function_name = RE_FUNCTION.search(func_info[0]).group('funcname')
    for resource in partition_list(func_info[1:-1], lambda x: 'line' in x):
        line_match = RE_LINE.search(resource[0])
        line, col = line_match.group('line'), line_match.group('column')
        if len(resource) == 3:
            # Case (1): the bounds were successfully inferred; case (2) is omitted
            resources.append({
                'uid': {
                    'function': function_name,
                    'line': int(line),
                    'column': int(col),
                    'source': file_name
                },
                'bound': resource[1].strip(),
                'class': resource[2].strip(),
                'type': 'bound'
            })
    return resources


def parse_output(output):
    """Parses the output of Loopus in the list of resources.

    Each resource specifies the collection fo bounds of functions specified in files.

    :param str output: string output of the Loopus; format is specified above at docstring
    :return: list of resources
    """
    files = [
        finfo for finfo in output.split("--------------------------------------\n") if finfo
    ]
    resources = []
    for file_info in files:
        resources.extend(parse_file(file_info))
    return resources
