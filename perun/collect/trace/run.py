"""Wrapper for trace collector, which collects profiling data about
running times and sizes of structures.

Specifies before, collect and after functions to perform the initialization,
collection and postprocessing of collection data.
"""

from subprocess import CalledProcessError
import time
import os

import click

import perun.collect.trace.strategy as strategy
import perun.collect.trace.systemtap as systemtap
import perun.collect.trace.systemtap_script as stap_script
import perun.logic.runner as runner
import perun.utils.exceptions as exceptions
import perun.utils as utils
import perun.utils.log as log

from perun.utils.helpers import CollectStatus


# The collector subtypes
_COLLECTOR_SUBTYPES = {
    'delta': 'time delta'
}


# The converter for collector statuses
_COLLECTOR_STATUS = {
    systemtap.Status.OK: (CollectStatus.OK, 'Ok'),
    systemtap.Status.STAP: (CollectStatus.ERROR,
                            'SystemTap related issue, see the corresponding {log} file.'),
    systemtap.Status.STAP_DEP: (CollectStatus.ERROR, 'SystemTap dependency missing.'),
    systemtap.Status.EXCEPT: (CollectStatus.ERROR, '')  # The msg should be set by the exception
}


# The time conversion constant
_MICRO_TO_SECONDS = 1000000.0


def before(**kwargs):
    """ Assembles the SystemTap script according to input parameters and collection strategy

    The output dictionary is updated with:
     - timestamp: current timestamp that is used for saved files
     - cmd, cmd_dir, cmd_base: absolute path to the command, its directory and the command base name
     - script_path: path to the generated script file
     - log_path: path to the collection log
     - output_path: path to the collection output

    :param kwargs: dictionary containing the configuration settings for the collector
    :returns: tuple (int as a status code, nonzero values for errors,
                    string as a status message, mainly for error states,
                    dict of kwargs and new values)
    """
    try:
        log.cprint('Starting the pre-processing phase... ', 'white')

        # Update the configuration dictionary with some additional values
        kwargs['timestamp'] = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())
        _, kwargs['cmd_dir'], kwargs['cmd_base'] = utils.get_path_dir_file(kwargs['cmd'])
        kwargs['script_path'] = _create_collector_file('script', '.stp', **kwargs)
        kwargs['log_path'] = _create_collector_file('log', **kwargs)
        kwargs['output_path'] = _create_collector_file('record', **kwargs)

        # Validate collection parameters
        kwargs = _validate_input(**kwargs)

        # Extract and / or post process the collect configuration
        kwargs = strategy.extract_configuration(**kwargs)
        if not kwargs['func'] and not kwargs['static'] and not kwargs['dynamic']:
            return CollectStatus.ERROR, ('No function, static or dynamic probes to be profiled '
                                         '(due to invalid specification, failed extraction or '
                                         'filtering)'), dict(kwargs)

        # Assemble script according to the parameters
        stap_script.assemble_system_tap_script(**kwargs)

        log.done()
        result = _COLLECTOR_STATUS[systemtap.Status.OK]
        return result[0], result[1], dict(kwargs)

    except (OSError, ValueError, CalledProcessError,
            UnicodeError, exceptions.InvalidBinaryException) as exception:
        log.failed()
        return _COLLECTOR_STATUS[systemtap.Status.EXCEPT][0], str(exception), dict(kwargs)


def collect(**kwargs):
    """ Runs the created SystemTap script and the profiled command

    The output dictionary is updated with:
     - output: path to the collector output file

    :param dict kwargs: dictionary containing the configuration settings for the collector
    :returns: (int as a status code, nonzero values for errors,
              string as a status message, mainly for error states,
              dict of kwargs and new values)
    """
    log.cprintln('Running the collector, progress output stored in collect_log_{0}.txt\n'
                 'This may take a while... '.format(kwargs['timestamp']), 'white')
    try:
        # Call the system tap
        code, kwargs['output_path'] = systemtap.systemtap_collect(**kwargs)
        result = _COLLECTOR_STATUS[code]
        if code != systemtap.Status.OK:
            log.failed()
            # Add specific return for STAP error which includes the precise log file path
            if code == systemtap.Status.STAP:
                return result[0], result[1].format(kwargs['log_path']), dict(kwargs)
        return result[0], result[1], dict(kwargs)

    except (OSError, CalledProcessError) as exception:
        log.failed()
        return CollectStatus.ERROR, str(exception), dict(kwargs)


def after(**kwargs):
    """ Handles the trace collector output and transforms it into resources

    The output dictionary is updated with:
     - profile: the performance profile contents created from the collector output

    :param kwargs: dictionary containing the configuration settings for the collector
    :returns: tuple (int as a status code, nonzero values for errors,
                    string as a status message, mainly for error states,
                    dict of kwargs and new values)
    """
    log.cprint('Starting the post-processing phase... ', 'white')

    # Get the trace log path
    try:
        resources = list(systemtap.trace_to_profile(**kwargs))

        # Update the profile dictionary
        kwargs['profile'] = {
            'global': {
                'timestamp': sum(res['amount'] for res in resources) / _MICRO_TO_SECONDS,
                'resources': resources
            }
        }
        log.done()
        result = _COLLECTOR_STATUS[systemtap.Status.OK]
        return result[0], result[1], dict(kwargs)

    except (CalledProcessError, exceptions.TraceStackException) as exception:
        log.failed()
        return _COLLECTOR_STATUS[systemtap.Status.EXCEPT], str(exception), dict(kwargs)


def _validate_input(**kwargs):
    """Validate the collector input parameters and transform them to expected format.

    :param kwargs: the collector input parameters
    :return dict: validated and transformed input parameters
    """
    kwargs['func'] = list(kwargs.get('func', ''))
    kwargs['func_sampled'] = list(kwargs.get('func_sampled', ''))
    kwargs['static'] = list(kwargs.get('static', ''))
    kwargs['static_sampled'] = list(kwargs.get('static_sampled', ''))
    kwargs['dynamic'] = list(kwargs.get('dynamic', ''))
    kwargs['dynamic_sampled'] = list(kwargs.get('dynamic_sampled', ''))
    kwargs['global_sampling'] = kwargs.get('global_sampling', 1)

    # Normalize global sampling
    if kwargs['global_sampling'] <= 1:
        kwargs['global_sampling'] = 1

    # Normalize timeout value
    if 'timeout' not in kwargs or kwargs['timeout'] <= 0:
        kwargs['timeout'] = None

    # Set the with-static if not provided
    if 'with_static' not in kwargs:
        kwargs['with_static'] = True

    if 'cleanup' not in kwargs:
        kwargs['cleanup'] = True

    # Set the binary if not provided
    if not kwargs['binary']:
        kwargs['binary'] = os.path.realpath(kwargs['cmd'])
    if not os.path.exists(kwargs['binary']) or not utils.is_executable_elf(kwargs['binary']):
        raise exceptions.InvalidBinaryException(kwargs['binary'])
    return kwargs


def _create_collector_file(name, suffix='.txt', **kwargs):
    """Prepares path to the requested file used during collection.
    The format is as follows: 'collect_<name>_<timestamp><suffix>

    :param str name: further specification of collector file name
    :param str suffix: the file suffix
    :param kwargs: additional parameters, e.g. timestamp
    :return str: assembled path to the file
    """
    return os.path.join(kwargs['cmd_dir'], 'collect_{name}_{time}{suffix}'
                        .format(name=name, time=kwargs['timestamp'], suffix=suffix))


# TODO: allow multiple executables to be specified
@click.command()
@click.option('--method', '-m', type=click.Choice(strategy.get_supported_strategies()),
              default=strategy.get_default_strategy(), required=True,
              help='Select strategy for probing the binary. See documentation for'
                   ' detailed explanation for each strategy.')
@click.option('--func', '-f', type=str, multiple=True,
              help='Set the probe point for the given function.')
@click.option('--static', '-s', type=str, multiple=True,
              help='Set the probe point for the given static location.')
@click.option('--dynamic', '-d', type=str, multiple=True,
              help='Set the probe point for the given dynamic location.')
@click.option('--func-sampled', '-fs', type=(str, int), multiple=True,
              help='Set the probe point and sampling for the given function.')
@click.option('--static-sampled', '-ss', type=(str, int), multiple=True,
              help='Set the probe point and sampling for the given static location.')
@click.option('--dynamic-sampled', '-ds', type=(str, int), multiple=True,
              help='Set the probe point and sampling for the given dynamic location.')
@click.option('--global-sampling', '-g', type=int, default=1,
              help='Set the global sample for all probes, sampling parameter for specific'
                   ' rules have higher priority.')
@click.option('--with-static/--no-static', default=True,
              help='The selected method will also extract and profile static probes.')
@click.option('--binary', '-b', type=click.Path(exists=True),
              help='The profiled executable. If not set, then the command is considered '
                   'to be the profiled executable and is used as a binary parameter')
@click.option('--timeout', '-t', type=int, default=0,
              help='Set time limit for the profiled command, i.e. the command will be terminated '
                   'after reaching the time limit. Useful for endless commands etc.')
@click.option('--cleanup/--no-cleanup', default=True,
              help='Enable/disable the pre-cleanup of possibly running systemtap processes that'
                   ' could cause the corruption of the output file due to multiple writes.')
@click.pass_context
def trace(ctx, **kwargs):
    """Generates `trace` performance profile, capturing running times of
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

    Trace collector provides various collection *strategies* which are supposed to provide
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

    The collector interface operates with two seemingly same concepts: (external) command
    and binary. External command refers to the script, executable, makefile, etc. that will
    be called / invoked during the profiling, such as 'make test', 'run_script.sh', './my_binary'.
    Binary, on the other hand, refers to the actual binary or executable file that will be profiled
    and contains specified functions / static probes etc. It is expected that the binary will be
    invoked / called as part of the external command script or that external command and binary are
    the same.

    The interface for rules (functions, static probes) specification offers a way to specify
    profiled locations both with sampling or without it. Note that sampling can reduce the
    overhead imposed by the profiling. Static rules can be further paired - paired rules act
    as a start and end point for time measurement. Without a pair, the rule measures time
    between each two probe hits. The pairing is done automatically for static locations with
    convention <name> and <name>_end or <name>_END.
    Otherwise, it is possible to pair rules by the delimiter '#', such as <name1>#<name2>.

    Trace profiles are suitable for postprocessing by
    :ref:`postprocessors-regression-analysis` since they capture dependency of
    time consumption depending on the size of the structure. This allows one to
    model the estimation of trace of individual functions.

    Scatter plots are suitable visualization for profiles collected by
    `trace` collector, which plots individual points along with regression
    models (if the profile was postprocessed by regression analysis). Run
    ``perun show scatter --help`` or refer to :ref:`views-scatter` for more
    information about `scatter plots`.

    Refer to :ref:`collectors-trace` for more thorough description and
    examples of `trace` collector.
    """
    runner.run_collector_from_cli_context(ctx, 'trace', kwargs)
