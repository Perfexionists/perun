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

import click

import perun.collect.complexity.strategy as strategy
import perun.logic.runner as runner
import perun.utils.exceptions as exceptions

# The profiling record template
_ProfileRecord = collections.namedtuple('record', ['offset', 'func', 'timestamp'])

# The collect phase status messages
_COLLECTOR_STATUS_MSG = {
    0:  'OK',
    1:  'SystemTap related issue, see the corresponding <cmd>_stap.log file.',
    2:  'SystemTap dependency missing.',
    3:  'c++filt dependency missing'
}

# The collector subtypes
_COLLECTOR_SUBTYPES = {
    'delta': 'time delta'
}

# The time conversion constant
_MICRO_TO_SECONDS = 1000000.0


def before(**kwargs):
    """ Assembles the SystemTap script according to input parameters and collection strategy

    :param dict kwargs: dictionary containing the configuration settings for the collector
    :returns: tuple (int as a status code, nonzero values for errors,
                    string as a status message, mainly for error states,
                    dict of modified kwargs with 'script' value as a path to the script file)
    """
    try:
        print('Starting the pre-processing phase... ', end='')

        # Check the command (must be file)
        if not os.path.isfile(kwargs['cmd']):
            raise ValueError('The command argument (-c) is not a file.')

        # Assemble script according to the parameters
        kwargs['cmd'], kwargs['cmd_dir'], kwargs['cmd_base'] = _get_path_dir_file(kwargs['cmd'])
        kwargs['script'] = strategy.assemble_script(**kwargs)

        print('Done.\n')
        return 0, _COLLECTOR_STATUS_MSG[0], dict(kwargs)
    # The "expected" exception types
    except (OSError, ValueError, subprocess.CalledProcessError,
            UnicodeError, exceptions.StrategyNotImplemented) as exception:
        print('Failed.\n')
        return 1, str(exception), kwargs


def collect(**kwargs):
    """ Runs the created SystemTap script on the input executable

    :param dict kwargs: dictionary containing the configuration settings for the collector
    :returns: (int as a status code, nonzero values for errors,
              string as a status message, mainly for error states,
              dict of modified kwargs with 'output' value representing the trace records)
    """
    print('Running the collector, progress output stored in <cmd>_stap.log.\n'
          'This may take a while... ', end='')
    try:
        # Call the system tap
        code, kwargs['output'] = _call_stap(**kwargs)
        if code == 0:
            print('Done.\n')
        else:
            print('Failed.\n')
        return code, _COLLECTOR_STATUS_MSG[code], dict(kwargs)
    except (OSError, subprocess.CalledProcessError) as exception:
        print('Failed.\n')
        return 1, str(exception), kwargs


def after(**kwargs):
    """ Handles the complexity collector output and transforms it into resources

    :param dict kwargs: dictionary containing the configuration settings for the collector
    :returns: tuple (int as a status code, nonzero values for errors,
                    string as a status message, mainly for error states,
                    dict of modified kwargs with 'profile' containing the processed trace)
    """

    print('Starting the post-processing phase... ', end='')
    resources, call_stack = [], []
    func_map = dict()

    # Get the trace log path
    try:
        with open(kwargs['output'], 'r') as profile:

            # Create demangled counterparts of the function names
            demangler = shutil.which('c++filt')
            if demangler is None:
                print('Failed.\n')
                return 3, _COLLECTOR_STATUS_MSG[3], dict(kwargs)
            demangle = subprocess.check_output(demangler, stdin=profile, shell=False)
            profile = demangle.decode(sys.stdout.encoding)

            for line in profile.splitlines(True):
                # Split the line into action, function name, timestamp and size
                record = _parse_record(line)

                # Process the record
                if _process_file_record(record, call_stack, resources, func_map) != 0:
                    # Stack error
                    err_msg = 'Call stack error, record: ' + record.func
                    if not call_stack:
                        err_msg += ', stack top: empty'
                    else:
                        err_msg += ', stack top: ' + call_stack[-1].func

                    print('Failed.\n')
                    return 1, err_msg, kwargs

        # Update the profile dictionary
        kwargs['profile'] = {
            'global': {
                'time': sum(res['amount'] for res in resources) / _MICRO_TO_SECONDS,
                'resources': resources
            }
        }
        print('Done.\n')
        return 0, _COLLECTOR_STATUS_MSG[0], dict(kwargs)
    except (OSError, subprocess.CalledProcessError) as exception:
        print('Failed.\n')
        return 1, str(exception), kwargs


def _get_path_dir_file(target):
    """ Extracts the target's absolute path, location directory and base name

    :param str target: name or location
    :returns: tuple (the absolute target path, the target directory, the target base name)
    """
    path = os.path.realpath(target)
    path_dir = os.path.dirname(path)
    if path_dir and path_dir[-1] != '/':
        path_dir += '/'
    return path, path_dir, os.path.basename(path)


def _call_stap(**kwargs):
    """Wrapper for SystemTap call and execution

    :param dict kwargs: complexity collector configuration parameters
    :returns: tuple (int code value - nonzero for errors, path to the SystemTap output)
    """
    # Resolve the system tap path
    stap = shutil.which('stap')
    if stap is None:
        return 2, ''

    script_path, script_dir, _ = _get_path_dir_file(kwargs['script'])
    # Create the output file and collection log
    output = script_dir + kwargs['cmd_base'] + '_stap_record.txt'
    with open(script_dir + kwargs['cmd_base'] + '_stap.log', 'w') as log:
        # Start the collector
        stap_runner = subprocess.Popen(('sudo', stap, '-v', script_path, '-o',
                                        output, '-c', kwargs['cmd']),
                                       cwd=script_dir, stderr=log, shell=False)
        stap_runner.communicate()
        if stap_runner.returncode != 0:
            code = 1
        else:
            code = 0
    return code, output


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
    elif record.offset == call_stack[-1].offset - 1:
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


def sampling_to_dictionary(ctx, param, value):
    """Sampling cli option converter callback. Transforms each sampling tuple into dictionary.

    :param dict ctx: click context
    :param object param: the parameter object
    :param list value: the list of sampling values
    :returns: list of dict -- list of sampling dictionaries
    """
    if value is not None:
        # Initialize
        sampling_list = []
        # Transform the tuple to more human readable dictionary
        for sample in value:
            sampling_list.append({
                "func": sample[0],
                "sample": sample[1]
            })
        return sampling_list


@click.command()
@click.option('--method', '-m', type=click.Choice(strategy.get_supported_strategies()),
              default=strategy.get_default_strategy(), required=True,
              help='Select strategy for probing the binary. See documentation for'
                   ' detailed explanation for each strategy.')
@click.option('--rules', '-r', type=str, multiple=True,
              help='Set the probe points for profiling.')
@click.option('--sampling', '-s', type=(str, int), multiple=True, callback=sampling_to_dictionary,
              help='Set the runtime sampling of the given probe points.')
@click.option('--global_sampling', '-g', type=int,
              help='Set the global sample for all probes, --sampling parameter for specific'
                   ' rules have higher priority.')
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
