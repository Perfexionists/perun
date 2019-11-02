"""Wrapper for trace collector, which collects profiling data about
running times for each of the specified functions or static markers in the code.

Specifies before, collect, after and teardown functions to perform the initialization,
collection and postprocessing of collection data.
"""

import os
import shutil
import time
import click

import perun.collect.trace.strategy as strategy
import perun.collect.trace.systemtap as systemtap
import perun.collect.trace.systemtap_script as stap_script
import perun.collect.trace.parse as parse
from perun.collect.trace.locks import LockType, ResourceLock
from perun.collect.trace.watchdog import WD
from perun.collect.trace.values import Res, OutputHandling, Zipper, \
    DEPENDENCIES, MICRO_TO_SECONDS

import perun.logic.runner as runner
import perun.logic.temp as temp
import perun.utils as utils
import perun.utils.log as stdout
from perun.logic.pcs import get_log_directory
from perun.utils.structs import CollectStatus
from perun.utils.exceptions import InvalidBinaryException, MissingDependencyException


def before(executable, **kwargs):
    """ Validates and normalizes the collection configuration.

    This phase shouldn't contain anything more than this so that the teardown phase has all the
    options set if the collection ends prematurely, e.g. the 'zip-temps' wouldn't be updated in
    the kwargs (thus in the teardown phase) if a signal is raised in this phase.

    :param Executable executable: full collection command with arguments and workload
    :param kwargs: dictionary containing the normalized configuration settings for the collector
    :returns: tuple (CollectStatus enum code,
                    string as a status message, mainly for error states,
                    dict of kwargs (possibly with some new values))
    """
    WD.header('Pre-processing phase...')
    # Validate and normalize collection parameters
    kwargs = _normalize_config(executable, **kwargs)
    # Initialize the watchdog and log the kwargs dictionary after it's fully initialized
    WD.start_session(kwargs['watchdog'], kwargs['pid'], kwargs['timestamp'], kwargs['quiet'])
    WD.log_variable('before::kwargs', kwargs)

    stdout.done('\n\n')
    return CollectStatus.OK, "", dict(kwargs)


def collect(executable, **kwargs):
    """ Assembles the SystemTap script according to input parameters and collection strategy.
    Runs the created SystemTap script and the profiled command.

    :param Executable executable: full collection command with arguments and workload
    :param kwargs: dictionary containing the configuration settings for the collector
    :returns: tuple (CollectStatus enum code,
                    string as a status message, mainly for error states,
                    dict of kwargs (possibly with some new values))
    """
    WD.header('Collect phase...')

    # Check all the required dependencies
    _check_dependencies()
    # Try to lock the binary so that no other concurrent trace collector process can
    # profile the same binary and produce corrupted performance data
    ResourceLock(
        LockType.Binary, os.path.basename(executable.cmd), kwargs['pid'], kwargs['locks_dir']
    ).lock(kwargs['res'])
    # Create the collect files
    _create_collect_files(**kwargs)

    # Extract and / or post-process the collect configuration
    kwargs = strategy.extract_configuration(**kwargs)
    if not kwargs['func'] and not kwargs['static'] and not kwargs['dynamic']:
        msg = ('No profiling probes created (due to invalid specification, failed extraction or '
               'filtering)')
        return CollectStatus.ERROR, msg, dict(kwargs)

    # Assemble script according to the parameters
    stap_script.assemble_system_tap_script(kwargs['res'][Res.script()], **kwargs)

    # Run the SystemTap and profiled command
    systemtap.systemtap_collect(executable, **kwargs)

    stdout.done('\n\n')
    return CollectStatus.OK, "", dict(kwargs)


def after(res, **kwargs):
    """ Parses the trace collector output and transforms it into profile resources

    :param Res res: the resources object
    :param kwargs: the configuration settings for the collector
    :returns: tuple (CollectStatus enum code,
                    string as a status message, mainly for error states,
                    dict of kwargs (possibly with some new values))
    """
    WD.header('Post-processing phase... ')

    # TODO: change the output according to the new format so that it doesn't use as much memory?
    # Parse the records and create the profile
    records = list(parse.trace_to_profile(res[Res.data()], **kwargs))
    kwargs['profile'] = {
        'global': {
            'timestamp': sum(record['amount'] for record in records) / MICRO_TO_SECONDS,
            'resources': records
        }
    }

    stdout.done('\n\n')
    return CollectStatus.OK, "", dict(kwargs)


def teardown(**kwargs):
    """ Perform a cleanup of all the collection resources that need it, i.e. files, locks,
    processes, kernel modules etc.

    :param kwargs: the configuration settings for the collector
    :returns: tuple (CollectStatus enum code,
                    string as a status message, mainly for error states,
                    dict of kwargs (possibly with some new values))
    """
    WD.header('Teardown phase...')

    # Cleanup all the SystemTap related resources
    if 'res' in kwargs:
        systemtap.cleanup(**kwargs)
    # Zip and delete the temporary and watchdog files
    timestamp = kwargs.get('timestamp', time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime()))
    pid = kwargs.get('pid', os.getpid())
    keep_temps = kwargs.get('keep_temps', False)
    pack_name = os.path.join(
        get_log_directory(), 'trace', 'collect_files_{}_{}.zip.lzma'.format(timestamp, pid)
    )
    with Zipper(kwargs.get('zip_temps', False), pack_name) as temp_pack:
        if 'res' in kwargs:
            _cleanup_collect_files(kwargs['res'], temp_pack, keep_temps)
        WD.end_session(temp_pack)

    stdout.done('\n\n')
    return CollectStatus.OK, "", dict(kwargs)


def _normalize_config(executable, **kwargs):
    """ Normalizes the collector input configuration, i.e. validates the provided configuration
    arguments, transforms them into the expected format and adds some extra values.

    :param Executable executable: full collection command with arguments and workload
    :param kwargs: the collector input parameters
    :return dict: validated and transformed input parameters
    """
    # Normalize the collection probes types
    kwargs['func'] = list(kwargs.get('func', ''))
    kwargs['func_sampled'] = list(kwargs.get('func_sampled', ''))
    kwargs['static'] = list(kwargs.get('static', ''))
    kwargs['static_sampled'] = list(kwargs.get('static_sampled', ''))
    kwargs['dynamic'] = list(kwargs.get('dynamic', ''))
    kwargs['dynamic_sampled'] = list(kwargs.get('dynamic_sampled', ''))

    # Set the some default values if not provided
    kwargs.setdefault('with_static', True)
    kwargs.setdefault('zip_temps', False)
    kwargs.setdefault('keep_temps', False)
    kwargs.setdefault('verbose_trace', False)
    kwargs.setdefault('quiet', False)
    kwargs.setdefault('watchdog', False)
    kwargs.setdefault('output_handling', OutputHandling.Default.value)
    kwargs.setdefault('diagnostics', False)

    # Enable some additional flags if diagnostics is enabled
    if kwargs['diagnostics']:
        kwargs['zip_temps'] = True
        kwargs['verbose_trace'] = True
        kwargs['watchdog'] = True
        kwargs['output_handling'] = OutputHandling.Capture.value

    # Transform the output handling value to the enum element
    kwargs['output_handling'] = OutputHandling(kwargs['output_handling'])

    # Normalize global sampling
    if 'global_sampling' not in kwargs or kwargs['global_sampling'] < 1:
        kwargs['global_sampling'] = 1
    # Normalize timeout value
    if 'timeout' not in kwargs or kwargs['timeout'] <= 0:
        kwargs['timeout'] = None

    # No runnable command was given, terminate the collection
    if not kwargs['binary'] and not executable.cmd:
        raise InvalidBinaryException('')
    # Otherwise copy the cmd or binary parameter
    elif not executable.cmd:
        executable.cmd = kwargs['binary']
    elif not kwargs['binary']:
        kwargs['binary'] = executable.cmd

    # Check that the binary / executable file exists and is valid
    kwargs['binary'] = os.path.realpath(kwargs['binary'])
    if not os.path.exists(kwargs['binary']) or not utils.is_executable_elf(kwargs['binary']):
        raise InvalidBinaryException(kwargs['binary'])
    elif not os.path.exists(executable.cmd):
        raise InvalidBinaryException(executable.cmd)

    # Update the configuration dictionary with some additional values
    kwargs['executable'] = executable
    kwargs['timestamp'] = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())
    kwargs['pid'] = os.getpid()
    kwargs['files_dir'] = temp.temp_path(os.path.join('trace', 'files'))
    kwargs['locks_dir'] = temp.temp_path(os.path.join('trace', 'locks'))
    # Init the resources object that is used for a clean teardown and store it in the resources list
    # This makes the resources available even if 'before' fails and kwargs is not updated
    kwargs['opened_resources'].append(Res())
    kwargs['res'] = kwargs['opened_resources'][0]  # Alias for easier access to the resource object
    return kwargs


def _create_collect_files(timestamp, pid, res, output_handling, **kwargs):
    """ Creates the temporary files required for data collection. Namely:
      - the SystemTap script file
      - the SystemTap log file
      - the SystemTap data file (i.e. where the raw measured performance data are stored)
      - the output capture file (optional) used to store stdout / stderr of the profiled command

    :param str timestamp: the perun startup timestamp
    :param int pid: the PID of the running perun process
    :param Res res: the resources object
    :param OutputHandling output_handling: determines whether the output capture file is required
    :param kwargs: additional configuration values
    """
    files = [(Res.script(), '.stp'), (Res.log(), '.txt'), (Res.data(), '.txt')]
    if output_handling == OutputHandling.Capture:
        # Create also the capture file
        files.append((Res.capture(), '.txt'))
    for name, suffix in files:
        file_name = 'collect_{}_{}_{}{}'.format(name, timestamp, pid, suffix)
        res[name] = os.path.join(kwargs['files_dir'], file_name)
        temp.touch_temp_file(res[name], protect=True)
        WD.debug("Temporary file '{}' successfully created".format(file_name))


def _cleanup_collect_files(res, pack, keep):
    """ Zips (optionally) and deletes (optionally) the temporary collection files.

    :param Res res: the resources object
    :param Zipper pack: the zipper object responsible for zipping the files
    :param bool keep: keeps the temporary files in the file system
    """
    for collect_file in [Res.script(), Res.log(), Res.data(), Res.capture()]:
        if res[collect_file] is not None:
            # If zipping the files is disabled in the configuration, the pack.write does nothing
            pack.write(res[collect_file], os.path.basename(res[collect_file]))
            if not keep:
                temp.delete_temp_file(res[collect_file], force=True)
                WD.debug("Temporary file '{}' deleted".format(res[collect_file]))
            res[collect_file] = None


def _check_dependencies():
    """ Checks that all the required dependencies are present on the system.
    Otherwise an exception is raised.
    """
    # Check that all the dependencies are present
    WD.debug("Checking that all the dependencies '{}' are present".format(DEPENDENCIES))
    for dependency in DEPENDENCIES:
        if not shutil.which(dependency):
            WD.debug("Missing dependency command '{}' detected".format(dependency))
            raise MissingDependencyException(dependency)
    WD.debug("Dependencies check successfully completed, no missing dependency")


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
              help='Set time limit (in seconds) for the profiled command, i.e. the command will be '
                   'terminated after reaching the time limit. Useful for endless commands etc.')
@click.option('--zip-temps', '-z', is_flag=True, default=False,
              help='Zip and compress the temporary files (SystemTap log, raw performance data, '
                   'watchdog log ...) in the perun log directory before deleting them.')
@click.option('--keep-temps', '-k', is_flag=True, default=False,
              help='Do not delete the temporary files in the file system.')
@click.option('--verbose-trace', '-vt', is_flag=True, default=False,
              help='Set the trace file output to be more verbose, useful for debugging.')
@click.option('--quiet', '-q', is_flag=True, default=False,
              help='Reduces the verbosity of the collector info messages.')
@click.option('--watchdog', '-w', is_flag=True, default=False,
              help='Enable detailed logging of the whole collection process.')
@click.option('--output-handling', '-o', type=click.Choice(OutputHandling.to_list()),
              default=OutputHandling.Default.value,
              help='Sets the output handling of the profiled command:\n'
                   ' - default: the output is displayed in the terminal\n'
                   ' - capture: the output is being captured into a file as well as displayed'
                   ' in the terminal (note that buffering causes a delay in the terminal output)\n'
                   ' - suppress: redirects the output to the DEVNULL')
@click.option('--diagnostics', '-i', is_flag=True, default=False,
              help='Enable detailed surveillance mode of the collector. The collector turns on '
                   'detailed logging (watchdog), verbose trace, capturing output etc. and stores '
                   'the logs and files in an archive (zip-temps) in order to provide as much '
                   'diagnostic data as possible for further inspection.'
              )
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
