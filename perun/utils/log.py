"""Set of helper function for logging and printing warnings or errors"""

import logging
import sys
import termcolor
import io
import pydoc
import functools

from perun.utils.helpers import first_index_of_attr
from perun.utils.decorators import static_variables
from perun.utils.helpers import COLLECT_PHASE_ATTRS, COLLECT_PHASE_ATTRS_HIGH

__author__ = 'Tomas Fiedor'
VERBOSITY = 0

# Enum of verbosity levels
VERBOSE_DEBUG = 2
VERBOSE_INFO = 1
VERBOSE_RELEASE = 0

SUPPRESS_WARNINGS = False
SUPPRESS_PAGING = True

# set the logging for the perun
logging.basicConfig(filename='perun.log', level=logging.DEBUG)


def page_function_if(func, paging_switch):
    """Adds paging of the output to standard stream

    This decorator serves as a pager for long outputs to the standard stream. As a pager currently,
    'less -R' is used. Further extension to Windows and weird terminals without less -R is planned.

    Fixme: Try the paging on windows
    Fixme: Uhm, what about standard error?

    Note that this should be used by itself but by @paged_function() decorator

    :param function func: original wrapped function that will be paged
    :param bool paging_switch: external paging condition, if set to tru the function will not be
        paged
    """
    def wrapper(*args, **kwargs):
        """Wrapper for the original function whose output will be paged

        Arguments:
            args(list): list of positional arguments for original function
            kwargs(dict): dictionary of key:value arguments for original function
        """
        if SUPPRESS_PAGING or not paging_switch:
            return func(*args, **kwargs)

        # Replace the original standard output with string buffer
        sys.stdout = io.StringIO()

        # Run the original input with positional and key-value arguments
        result = func(*args, **kwargs)

        # Read the caught standard output and then restore the original stream
        sys.stdout.seek(0)
        stdout_str = "".join(sys.stdout.readlines())
        sys.stdout = sys.__stdout__
        pydoc.pipepager(stdout_str, "less -R")

        return result
    return wrapper


def paged_function(paging_switch):
    """The wrapper of the ``page_function_if`` to serve as a decorator, which partially applies the
    paging_switch. This way the function will accept only the function as parameter and can serve as
    decorator.

    :param bool paging_switch: external paging condition, if set to tru the function will not be
    :return: wrapped paged function
    """
    return functools.partial(page_function_if, paging_switch=paging_switch)


def _log_msg(stream, msg, msg_verbosity, log_level):
    """
    If the @p msg_verbosity is smaller than the set verbosity of the logging
    module, the @p msg is printed to the log with the given @p log_level

    Attributes:
        stream(function): streaming function of the type void f(log_level, msg)
        msg(str): message to be logged if certain verbosity is set
        msg_verbosity(int): level of the verbosity of the message
        log_level(int): log level of the message
    """
    if msg_verbosity <= VERBOSITY:
        stream(log_level, msg)


def msg_to_stdout(message, msg_verbosity, log_level=logging.INFO):
    """
    Helper function for the log_msg, prints the @p msg to the stdout,
    if the @p msg_verbosity is smaller or equal to actual verbosity.
    """
    _log_msg(lambda lvl, msg: print("{}".format(msg)), message, msg_verbosity, log_level)


def msg_to_file(msg, msg_verbosity, log_level=logging.INFO):
    """
    Helper function for the log_msg, prints the @p msg to the log,
    if the @p msg_verbosity is smaller or equal to actual verbosity
    """
    _log_msg(logging.log, msg, msg_verbosity, log_level)


def info(msg):
    """
    Arguments:
        msg(str): info message that will be printed only when there is at least lvl1 verbosity
    """
    print("info: {}".format(msg))


def quiet_info(msg):
    """
    Arguments:
        msg(str): info message to the stream that will be always shown
    """
    msg_to_stdout(msg, VERBOSE_RELEASE)


def error(msg, recoverable=False):
    """
    Arguments:
        msg(str): error message printe to standard output
        recoverable(bool): whether we can recover from the error
    """
    print(termcolor.colored("fatal: {}".format(msg), 'red'), file=sys.stderr)

    # If we cannot recover from this error, we end
    if not recoverable:
        exit(1)


def warn(msg):
    """
    Arguments:
        msg(str): warn message printed to standard output
    """
    if not SUPPRESS_WARNINGS:
        print("warn: {}".format(msg))


def print_current_phase(phase_msg, phase_unit, phase_colour):
    """Print helper coloured message for the current phase

    Arguments:
        phase_msg(str): message that will be printed to the output
        phase_unit(str): additional parameter that is passed to the phase_msg
        phase_colour(str): phase colour defined in helpers.py
    """
    print(termcolor.colored(
        phase_msg.format(
            termcolor.colored(phase_unit, attrs=COLLECT_PHASE_ATTRS_HIGH)
        ), phase_colour, attrs=COLLECT_PHASE_ATTRS
    ))


@static_variables(current_job=1)
def print_job_progress(overall_jobs):
    """Print the tag with the percent of the jobs currently done

    Arguments:
        overall_jobs(int): overall number of jobs to be done
    """
    percentage_done = round((print_job_progress.current_job / overall_jobs) * 100)
    print("[{}%] ".format(
        str(percentage_done).rjust(3, ' ')
    ), end='')
    print_job_progress.current_job += 1


def cprint(string, colour, attrs=None):
    """Wrapper over coloured print without adding new line

    Arguments:
        string(str): string that is printed with colours
        colour(str): colour that will be used to colour the string
        attrs(list): list of additional attributes for the colouring
    """
    attrs = attrs or []
    print(termcolor.colored(string, colour, attrs=attrs), end='')


def cprintln(string, colour, attrs=None, ending='\n'):
    """Wrapper over coloured print with added new line or other ending

    Arguments:
        string(str): string that is printed with colours and newline
        colour(str): colour that will be used to colour the stirng
        attrs(list): list of additional attributes for the colouring
        ending(str): ending of the string, be default new line
    """
    attrs = attrs or []
    print(termcolor.colored(string, colour, attrs=attrs), end=ending)


def done(ending='\n'):
    """Helper function that will print green done to the terminal

    Arguments:
        ending(str): end of the string, by default new line
    """
    print('[', end='')
    cprint("DONE", 'green', attrs=['bold'])
    print(']', end=ending)


def failed(ending='\n'):
    """
    Arguments:
        ending(str): end of the string, by default new line
    """
    print('[', end='')
    cprint("FAILED", 'red', attrs=['bold'])
    print(']', end=ending)


def print_minor_version(minor_version):
    """Helper function for printing minor version to the degradation output

    Currently printed in form of:

    * sha[:6]: desc

    :param MinorVersion minor_version: informations about minor version
    """
    print("* ", end='')
    cprint("{}".format(
        minor_version.checksum[:6]
    ), 'yellow', attrs=[])
    print(": {}".format(
        minor_version.desc.split("\n")[0].strip()
    ))


class History(object):
    """Helper with wrapper, which is used when one wants to visualize the version control history
    of the project, printing specific stuff corresponding to a git history

    :ivar list unresolved_edges: list of parents that needs to be resolved in the vcs graph,
        for each such parent, we keep one column.
    """
    class Edge(object):
        """Represents one edge of the history

        :ivar str next: the parent of the edge, i.e. the previously processed sha
        :ivar str colour: colour of the edge (red for deg, yellow for deg+opt, green for opt)
        :ivar str prev: the child of the edge, i.e. the not yet processed sha
        """
        def __init__(self, n, colour='white', prev=None):
            """Initiates one edge of the history

            :param str n: the next sha that will be processed
            :param str colour: colour of the edge
            :param str prev: the "parent" of the n
            """
            self.next = n
            self.colour = colour
            self.prev = prev

        def to_ascii(self, char):
            """Converts the edge to ascii representation

            :param str char: string that represents the edge
            :return: string representing the edge in ascii
            """
            return char if self.colour == 'white' \
                else termcolor.colored(char, self.colour, attrs=['bold'])

    def __init__(self, head):
        """Creates a with wrapper, which keeps and prints the context of the current vcs
        starting at head

        :param str head: head minor version
        """
        self.unresolved_edges = [History.Edge(head)]

    def __enter__(self):
        """When entering, we create a new string io object to catch standard output

        :return: the history object
        """
        # We will get the original standard output with string buffer and handle writing ourselves
        sys.stdout = io.StringIO()
        return self

    def __exit__(self, *_):
        """Restores the stdout to the original state

        :param list _: list of unused parameters
        """
        # Restore the stdout
        sys.stdout = sys.__stdout__

    def get_left_border(self):
        """Returns the string representing the currently unresolved branches.

        Each unresolved branch is represented as a '|' characters

        The left border can e.g. look as follows:

        | | | | |

        :return: string representing the columns of the unresolved branches
        """
        return " ".join(edge.to_ascii("|") for edge in self.unresolved_edges) + "  "

    def _merge_parents(self, merged_parent):
        """Removes the duplicate instances of the merge parent.

        E.g. given the following parents:

            [p1, p2, p3, p2, p4, p2]

        End we merge the parent p2, the we will obtain the following:

            [p1, p2, p3, p4]

        This is used, when we are outputing the parent p2, and first we merged the branches, print
        the information about p2 and then actualize the unresolved parents with parents of p2.

        :param str merged_parent: sha of the parent that is going to be merged in the unresolved
        """
        filtered_unresolved = []
        already_found_parent = False
        for parent in self.unresolved_edges:
            if parent.next == merged_parent and already_found_parent:
                continue
            already_found_parent = already_found_parent or parent.next == merged_parent
            filtered_unresolved.append(parent)
        self.unresolved_edges = filtered_unresolved

    def _print_minor_version(self, minor_version_info):
        """Prints the information about minor version.

        The minor version is visualized as follows:

         | * | {sha:6} {desc}

        I.e. all of the unresolved parents are output as | and the printed parent is output as *.
        The further we print first six character of minor version checksum and first line of desc

        :param MinorVersion minor_version_info: printed minor version
        """
        minor_str = " ".join(
            "*" if p.next == minor_version_info.checksum else p.to_ascii("|")
            for p in self.unresolved_edges
        )
        print(minor_str, end='')
        cprint(" {}".format(
            minor_version_info.checksum[:6]
        ), 'yellow', attrs=[])
        print(": {} | ".format(
            minor_version_info.desc.split("\n")[0].strip()
        ), end='')

    def progress_to_next_minor_version(self, minor_version_info):
        """Progresses the history of the VCS to next minor version

        This flushes the current caught buffer, resolves the fork points (i.e. when we forked the
        history from the minor_version), prints the information about minor version and the resolves
        the merges (i.e. when the minor_version is spawned from the merge). Finally this updates the
        unresolved parents with parents of minor_version.

        Prints the following:

        | | | |/ / /
        | | | * | | sha: desc
        | | | |\ \ \

        :param MinorVersion minor_version_info: information about minor version
        """
        minor_sha = minor_version_info.checksum
        self.flush(with_border=True)
        self._process_fork_point(minor_sha)
        self._merge_parents(minor_sha)
        self._print_minor_version(minor_version_info)

    def finish_minor_version(self, minor_version_info, degradation_list):
        # Update the unresolved parents
        minor_sha = minor_version_info.checksum
        version_index = first_index_of_attr(self.unresolved_edges, 'next', minor_sha)
        self._process_merge_point(version_index, minor_version_info.parents)
        self.unresolved_edges[version_index:version_index+1] = [
            History.Edge(p, 'white', minor_sha) for p in minor_version_info.parents
        ]
        self._taint_parents(minor_sha, degradation_list)

        # Flush the history
        self.flush()

    def flush(self, with_border=False):
        """Flushes the stdout optionally with left border of unresolved parent columns

        :param bool with_border: if true, then every line is printed with the border of unresolved
            parents
        """
        # flush the stdout
        sys.stdout.seek(0)
        for line in sys.stdout.readlines():
            if with_border:
                sys.__stdout__.write(self.get_left_border())
            sys.__stdout__.write(line)

        # create new stringio
        sys.stdout = io.StringIO()

    def _taint_parents(self, target, degradation_list):
        """According to the given list of degradation, sets the parents either as tainted
        or fixed.

        Tainted parents are output with red colour, while fixed parents with green colour.

        :param str target: target minor version
        :param list degradation_list: list of found degradations
        """
        # First we process all of the degradations and optimization
        taints = set()
        fixes = set()
        for deg, _, baseline in degradation_list:
            if deg.result.name == "Degradation":
                taints.add(baseline)
            elif deg.result.name == "Optimization":
                fixes.add(baseline)

        # At last we colour the edges; edges that contain both optimizations and degradations
        # are coloured yellow
        for edge in self.unresolved_edges:
            if edge.prev == target:
                tainted = edge.next in taints
                fixed = edge.next in fixes
                if tainted and fixed:
                    edge.colour = 'yellow'
                elif tainted:
                    edge.colour = 'red'
                elif fixed:
                    edge.colour = 'green'

    def _process_merge_point(self, merged_at, merged_parents):
        """Updates the printed tree after we merged list of parents in the given merge_at index.

        This prints up to merged_at unresolved parents, and then creates a merge point (|\) that
        branches of to the length of the merged_parents columns.

        Prints the following:

        | | | * \ \ sha: desc
        | | | |\ \ \
        | | | | | | |

        :param int merged_at: index, where the merged has happened
        :param list merged_parents: list of merged parents
        """
        parent_num = len(merged_parents)
        rightmost_branches_num = len(self.unresolved_edges) - merged_at - 1
        for _ in range(1, parent_num):
            print("| "*merged_at + "|\\" + "\\ " * rightmost_branches_num)
            merged_at += 1

    def _process_fork_point(self, fork_point):
        """Updates the printed tree after we forked from the given sha.

        Prints the following:

        | | | | | | |
        | | | |/ / /
        | | | * | |

        :param str fork_point: sha of the point, where we are forking
        """
        ulen = len(self.unresolved_edges)
        forked_index = first_index_of_attr(self.unresolved_edges, 'next', fork_point)
        src_index_map = list(range(0, ulen))
        tgt_index_map = [
            forked_index if self.unresolved_edges[i].next == fork_point else i for i in range(0, ulen)
        ]

        while src_index_map != tgt_index_map:
            line = list(" "*(max(src_index_map)+1)*2)
            for i, (lhs, rhs) in enumerate(zip(src_index_map, tgt_index_map)):
                # for this index we are moving to the left
                diff = -1 if rhs - lhs else 0
                if diff == 0:
                    line[2*lhs] = '|'
                else:
                    line[2*lhs-1] = '/'
                src_index_map[i] += diff
            print("".join(line))
