"""Wrapper for complexity collector, which collects profiling data about
running times and sizes of structures.

Specifies before, collect and after functions to perform the initialization,
collection and postprocessing of collection data.
"""

import collections
import os
import sys
import subprocess
import shutil
import shlex
import time

import click

import perun.collect.complexity.strategy as strategy
import perun.collect.complexity.systemtap as systemtap
import perun.logic.runner as runner
import perun.utils.exceptions as exceptions
import perun.utils as utils

from perun.utils.helpers import CollectStatus

# The profiling record template
_ProfileRecord = collections.namedtuple('record', ['offset', 'func', 'timestamp'])


# The converter for collector statuses
_COLLECTOR_STATUS = {
    systemtap.Status.OK: (CollectStatus.OK, 'Ok'),
    systemtap.Status.STAP: (CollectStatus.ERROR,
                            'SystemTap related issue, see the corresponding collect_log_<timestamp>.txt file.'),
    systemtap.Status.STAP_DEP: (CollectStatus.ERROR, 'SystemTap dependency missing.'),
    systemtap.Status.EXCEPT: (CollectStatus.ERROR, '')  # The msg should be set by the exception
}

# The collector subtypes
_COLLECTOR_SUBTYPES = {
    'delta': 'time delta'
}

# The time conversion constant
_MICRO_TO_SECONDS = 1000000.0


def before(function, function_sampled, static, static_sampled, dynamic, dynamic_sampled, **kwargs):
    """ Assembles the SystemTap script according to input parameters and collection strategy

    :param kwargs: dictionary containing the configuration settings for the collector
    :returns: tuple (int as a status code, nonzero values for errors,
                    string as a status message, mainly for error states,
                    dict of modified kwargs with 'script' value as a path to the script file)
    """
    try:
        print('Starting the pre-processing phase... ', end='')

        kwargs['timestamp'] = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())
        kwargs['function'] = _merge_probes_lists(function, function_sampled, kwargs['global_sampling'])
        kwargs['static'] = _merge_probes_lists(static, static_sampled, kwargs['global_sampling'])
        kwargs['dynamic'] = _merge_probes_lists(dynamic, dynamic_sampled, kwargs['global_sampling'])

        # Assemble script according to the parameters
        kwargs['cmd'], kwargs['cmd_dir'], kwargs['cmd_base'] = utils.get_path_dir_file(kwargs['cmd'])
        kwargs['script'] = strategy.assemble_script(**kwargs)

        print('Done.\n')
        return _COLLECTOR_STATUS[systemtap.Status.OK][0], _COLLECTOR_STATUS[systemtap.Status.OK][1], dict(kwargs)
    # The "expected" exception types
    except (OSError, ValueError, subprocess.CalledProcessError,
            UnicodeError, exceptions.StrategyNotImplemented) as exception:
        print('Failed.\n')
        return _COLLECTOR_STATUS[systemtap.Status.EXCEPT][0], str(exception), dict(kwargs)


def collect(**kwargs):
    """ Runs the created SystemTap script on the input executable

    :param dict kwargs: dictionary containing the configuration settings for the collector
    :returns: (int as a status code, nonzero values for errors,
              string as a status message, mainly for error states,
              dict of modified kwargs with 'output' value representing the trace records)
    """
    print('Running the collector, progress output stored in collect_log_{0}.txt\n'
          'This may take a while... '.format(kwargs['timestamp']))
    try:
        # Call the system tap
        code, kwargs['output'] = systemtap.systemtap_collect(**kwargs)
        if code == systemtap.Status.OK:
            print('Done.\n')
        else:
            print('Failed.\n')
        return _COLLECTOR_STATUS[code][0], _COLLECTOR_STATUS[code][1], dict(kwargs)
    except (OSError, subprocess.CalledProcessError) as exception:
        print('Failed.\n')
        return CollectStatus.ERROR, str(exception), dict(kwargs)


def after(**kwargs):
    """ Handles the complexity collector output and transforms it into resources

    :param kwargs: dictionary containing the configuration settings for the collector
    :returns: tuple (int as a status code, nonzero values for errors,
                    string as a status message, mainly for error states,
                    dict of modified kwargs with 'profile' containing the processed trace)
    """

    print('Starting the post-processing phase... ', end='')
    resources, call_stack = [], []
    func_map = dict()

    # Get the trace log path
    try:
        # with open(kwargs['output'], 'r') as profile:
        #
        #     # Create demangled counterparts of the function names
        #     demangler = shutil.which('c++filt')
        #     if demangler:
        #         demangler = shlex.split(shlex.quote(demangler))
        #         demangle = subprocess.check_output(demangler, stdin=profile, shell=False)
        #         profile = demangle.decode(sys.__stdout__.encoding)
        #
        #     for line in profile.splitlines(True):
        #         # Split the line into action, function name, timestamp and size
        #         record = _parse_record(line)
        #
        #         # Process the record
        #         if _process_file_record(record, call_stack, resources, func_map) != 0:
        #             # Stack error
        #             err_msg = 'Call stack error, record: ' + record.func
        #             if not call_stack:
        #                 err_msg += ', stack top: empty'
        #             else:
        #                 err_msg += ', stack top: ' + call_stack[-1].func
        #
        #             print('Failed.\n')
        #             return _COLLECTOR_STATUS[stap.Status.EXCEPT][0], err_msg, dict(kwargs)
        #
        # # Update the profile dictionary
        # kwargs['profile'] = {
        #     'global': {
        #         'time': sum(res['amount'] for res in resources) / _MICRO_TO_SECONDS,
        #         'resources': resources
        #     }
        # }
        print('Done.\n')
        return _COLLECTOR_STATUS[systemtap.Status.OK][0], _COLLECTOR_STATUS[systemtap.Status.OK][1], dict(kwargs)
    except (OSError, subprocess.CalledProcessError) as exception:
        print('Failed.\n')
        return _COLLECTOR_STATUS[systemtap.Status.EXCEPT], str(exception), dict(kwargs)


def _call_stap(**kwargs):
    """Wrapper for SystemTap call and execution

    :param kwargs: complexity collector configuration parameters
    :returns: tuple (int code value - nonzero for errors, path to the SystemTap output)
    """
    # Resolve the system tap path
    stap = shutil.which('stap')
    if not stap:
        return stap.Status.STAP_DEP, ''

    script_path, script_dir, _ = utils.get_path_dir_file(kwargs['script'])
    # Create the output file and collection log
    output = script_dir + kwargs['cmd_base'] + '_stap_record.txt'
    with open(script_dir + kwargs['cmd_base'] + '_stap.log', 'w') as log:
        # Start the collector
        stap = shlex.split(
            'sudo {0} -v {1} -o {2} -c {3}'.format(shlex.quote(stap), shlex.quote(script_path),
                                                   shlex.quote(output), shlex.quote(kwargs['cmd'])))
        stap_runner = subprocess.Popen(stap, cwd=script_dir, stderr=log, shell=False)
        stap_runner.communicate()
    return stap.Status(int(stap_runner.returncode != 0)), output  # code 0 = False = .OK


def _process_file_record(record, call_stack, resources, sequences):
    """ Processes the next profile record and tries to pair it with stack record if possible

    :param namedtuple record: the _ProfileRecord tuple containing the record data
    :param list call_stack: the call stack with file records
    :param list resources: the list of resource dictionaries
    :param dict sequences: stores the sequence counter for every function
    :returns: int -- status code, nonzero values for errors
    """
    if record.func:
        # Function entry, add to stack and note the sequence number
        call_stack.append(record)
        if record.func in sequences:
            sequences[record.func] += 1
        else:
            sequences[record.func] = 0
        return 0
    elif call_stack and record.offset == call_stack[-1].offset - 1:
        # Function exit, match with the function enter to create resources record
        matching_record = call_stack.pop()
        resources.append({'amount': int(record.timestamp) - int(matching_record.timestamp),
                          'uid': matching_record.func,
                          'type': 'mixed',
                          'subtype': 'time delta',
                          'structure-unit-size': sequences[matching_record.func]})
        return 0
    else:
        return 1


def _parse_record(line):
    """ Parses line into record tuple consisting of call stack offset, function name and timestamp.

    :param str line: one line from the trace output
    :returns: namedtuple -- the _ProfileRecord tuple
    """

    # Split the line into timestamp : offset func
    parts = line.partition(':')
    # Parse the timestamp
    time = parts[0].split()[0]
    # Parse the offset and function name
    right_section = parts[2].rstrip('\n')
    func = right_section.lstrip(' ')
    offset = len(right_section) - len(func)
    return _ProfileRecord(offset, func, time)


def _validate_gsamp(ctx, param, global_sampling):
    """Global sampling cli option converter callback. Checks the global sampling value.

    :param dict ctx: click context
    :param object param: the parameter object
    :param int global_sampling: the global sampling value
    :returns: the checked global sampling value or None
    """
    if global_sampling <= 1:
        return 0
    else:
        return global_sampling


def _merge_probes_lists(probes, probes_sampled, global_sampling):
    # Add global sampling (default 0) to the probes without sampling specification
    probes = [{'name': probe, 'sample': global_sampling} for probe in probes]

    # Validate the sampling values and merge the lists
    for probe in probes_sampled:
        if probe[1] < 2:
            probes.append({'name': probe[0], 'sample': global_sampling})
        else:
            probes.append({'name': probe[0], 'sample': probe[1]})
    return probes


# TODO: allow multiple executables to be specified
@click.command()
@click.option('--method', '-m', type=click.Choice(strategy.get_supported_strategies()),
              default=strategy.get_default_strategy(), required=True,
              help='Select strategy for probing the binary. See documentation for'
                   ' detailed explanation for each strategy.')
@click.option('--function', '-f', type=str, multiple=True,
              help='Set the probe point for the given function.')
@click.option('--static', '-s', type=str, multiple=True,
              help='Set the probe point for the given static location.')
@click.option('--dynamic', '-d', type=str, multiple=True,
              help='Set the probe point for the given dynamic location.')
@click.option('--function-sampled', '-fs', type=(str, int), multiple=True,
              help='Set the probe point and sampling for the given function.')
@click.option('--static-sampled', '-ss', type=(str, int), multiple=True,
              help='Set the probe point and sampling for the given static location.')
@click.option('--dynamic-sampled', '-ds', type=(str, int), multiple=True,
              help='Set the probe point and sampling for the given dynamic location.')
@click.option('--global-sampling', '-g', type=int, default=0, callback=_validate_gsamp,
              help='Set the global sample for all probes, sampling parameter for specific'
                   ' rules have higher priority.')
@click.option('--binary', '-b', type=click.Path(exists=True),
              help='The profiled executable')
@click.pass_context
def complexity(ctx, **kwargs):
    """Generates `complexity` performance profile, capturing running times of
    function depending on underlying structural sizes.

    \b
      * **Limitations**: C/C++ binaries
      * **Metric**: `mixed` (captures both `time` and `size` consumption)
      * **Dependencies**: ``SystemTap`` (+ corresponding requirements e.g. kernel -dbgsym version)
      * **Default units**: `us` for `time`, `element number` for `size`

    Example of collected resources is as follows:

    .. code-block:: json

        \b
        {
            "amount": 11,
            "subtype": "time delta",
            "type": "mixed",
            "uid": "SLList_init(SLList*)",
            "structure-unit-size": 0
        }

    Complexity collector provides various collection *strategies* which are supposed to provide
    sensible default settings for collection. This allows the user to choose suitable
    collection method without the need of detailed rules / sampling specification. Currently
    supported strategies are:

    \b
      * **userspace**: This strategy traces all userspace functions / code blocks without
      the use of sampling. Note that this strategy might be resource-intensive.
      * **all**: This strategy traces all userspace + library + kernel functions / code blocks
      that are present in the traced binary without the use of sampling. Note that this strategy
      might be very resource-intensive.
      * **u_sampled**: Sampled version of the **userspace** strategy. This method uses sampling
      to reduce the overhead and resources consumption.
      * **a_sampled**: Sampled version of the **all** strategy. Its goal is to reduce the
      overhead and resources consumption of the **all** method.
      * **custom**: User-specified strategy. Requires the user to specify rules and sampling
      manually.

    Note that manually specified parameters have higher priority than strategy specification
    and it is thus possible to override concrete rules / sampling by the user.

    Complexity profiles are suitable for postprocessing by
    :ref:`postprocessors-regression-analysis` since they capture dependency of
    time consumption depending on the size of the structure. This allows one to
    model the estimation of complexity of individual functions.

    Scatter plots are suitable visualization for profiles collected by
    `complexity` collector, which plots individual points along with regression
    models (if the profile was postprocessed by regression analysis). Run
    ``perun show scatter --help`` or refer to :ref:`views-scatter` for more
    information about `scatter plots`.

    Refer to :ref:`collectors-complexity` for more thorough description and
    examples of `complexity` collector.
    """
    runner.run_collector_from_cli_context(ctx, 'complexity', kwargs)
