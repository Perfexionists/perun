"""Basic tests for running the currently supported collectors"""

import os
import glob
import re

from click.testing import CliRunner

import perun.vcs as vcs
import perun.cli as cli
import perun.logic.runner as run
import perun.profile.query as query
import perun.collect.trace.systemtap as stap
import perun.collect.trace.strategy as strategy
import perun.utils.decorators as decorators
import perun.logic.config as config
import perun.utils as utils
import perun.collect.complexity.makefiles as makefiles
import perun.collect.complexity.symbols as symbols
import perun.collect.complexity.run as complexity
import perun.utils.log as log

from perun.utils.helpers import Job
from perun.utils.structs import Unit
from perun.workload.integer_generator import IntegerGenerator
from perun.collect.trace.systemtap import _TraceRecord
from perun.collect.trace.systemtap_script import RecordType

__author__ = 'Tomas Fiedor'


_mocked_stap_code = 0
_mocked_stap_file = 'tst_stap_record.txt'


def _mocked_stap(**_):
    """System tap mock, provide OK code and pre-fabricated collection output"""
    code = _mocked_stap_code
    file = os.path.join(os.path.dirname(__file__), 'collect_trace', _mocked_stap_file)
    return code, file


def _mocked_stap_extraction(_):
    return ('process("/home/jirka/perun/tests/collect_trace/tst").mark("BEFORE_CYCLE")\n'
            'process("/home/jirka/perun/tests/collect_trace/tst").mark("BEFORE_CYCLE_end")\n'
            'process("/home/jirka/perun/tests/collect_trace/tst").mark("INSIDE_CYCLE")\n')


def _mocked_stap_extraction2(_):
    """Static probes in ruby code enhanced with some artificial one to trigger all pairing
       possibilities.
    """
    return ('process("/home/jirka/perun/experiments/ruby/ruby").mark("array__create")\n'
            'process("/home/jirka/perun/experiments/ruby/ruby").mark("array__end")\n'
            'process("/home/jirka/perun/experiments/ruby/ruby").mark("cmethod__entry")\n'
            'process("/home/jirka/perun/experiments/ruby/ruby").mark("cmethod__return")\n'
            'process("/home/jirka/perun/experiments/ruby/ruby").mark("cmethod__deconstruct")\n'
            'process("/home/jirka/perun/experiments/ruby/ruby").mark("find__require__entry")\n'
            'process("/home/jirka/perun/experiments/ruby/ruby").mark("find__require__return")\n'
            'process("/home/jirka/perun/experiments/ruby/ruby").mark("find__require__begin")\n'
            'process("/home/jirka/perun/experiments/ruby/ruby").mark("gc__mark__begin")\n'
            'process("/home/jirka/perun/experiments/ruby/ruby").mark("gc__mark__end")\n'
            'process("/home/jirka/perun/experiments/ruby/ruby").mark("gc__sweep__begin")\n'
            'process("/home/jirka/perun/experiments/ruby/ruby").mark("gc__sweep__end")\n'
            'process("/home/jirka/perun/experiments/ruby/ruby").mark("hash__create")\n'
            'process("/home/jirka/perun/experiments/ruby/ruby").mark("load__entry")\n'
            'process("/home/jirka/perun/experiments/ruby/ruby").mark("load__return")\n'
            'process("/home/jirka/perun/experiments/ruby/ruby").mark("method__cache__clear")\n'
            'process("/home/jirka/perun/experiments/ruby/ruby").mark("method__entry")\n'
            'process("/home/jirka/perun/experiments/ruby/ruby").mark("method__return")\n'
            'process("/home/jirka/perun/experiments/ruby/ruby").mark("object__create")\n'
            'process("/home/jirka/perun/experiments/ruby/ruby").mark("parse__begin")\n'
            'process("/home/jirka/perun/experiments/ruby/ruby").mark("parse__end")\n'
            'process("/home/jirka/perun/experiments/ruby/ruby").mark("raise")\n'
            'process("/home/jirka/perun/experiments/ruby/ruby").mark("require__entry")\n'
            'process("/home/jirka/perun/experiments/ruby/ruby").mark("require__return")\n'
            'process("/home/jirka/perun/experiments/ruby/ruby").mark("string__create")\n'
            'process("/home/jirka/perun/experiments/ruby/ruby").mark("symbol__create")\n'
            'process("/home/jirka/perun/experiments/ruby/ruby").mark("symbol__deconstruct")\n')


def _mocked_trace_stack(_, __):
    """Provides trace stack for exception output"""
    trace_stack = {'func': {5983:
        ([_TraceRecord(RecordType.FuncBegin, 0, 'ruby_init', 0, 5983, 0),
          _TraceRecord(RecordType.FuncBegin, 1, 'ruby_setup', 3, 5983, 0),
          _TraceRecord(RecordType.FuncBegin, 2, 'rb_define_global_function', 53036, 5983, 1),
          _TraceRecord(RecordType.FuncBegin, 3, 'rb_define_module_function', 53041, 5983, 1),
          _TraceRecord(RecordType.FuncBegin, 4, 'rb_define_private_method', 53045, 5983, 12),
          _TraceRecord(RecordType.FuncBegin, 5, 'rb_intern', 53049, 5983, 63),
          _TraceRecord(RecordType.FuncBegin, 6, 'rb_intern2', 53053, 5983, 70),
          _TraceRecord(RecordType.FuncBegin, 7, 'rb_intern3', 53062, 5983, 70)], [])},
                   'static': {5983: {
                       'array__create': [_TraceRecord(RecordType.StaticSingle, 3,
                                                      'array__create', 5023, 5983, 3)],
                       'string__create': [_TraceRecord(RecordType.StaticSingle, 9,
                                                       'string__create', 53135, 5983, 329)],
                       'symbol__create': [_TraceRecord(RecordType.StaticSingle, 8,
                                                       'symbol__create', 52637, 5983, 166)],
                       'method__cache__clear': [_TraceRecord(RecordType.StaticSingle, 7,
                                                             'method__cache__clear', 53006, 5983,
                                                             57)]
                   }}}
    return trace_stack, {}


def _mocked_parse_record(_):
    raise KeyError


def _mocked_stap_extraction_empty(_):
    return 'Tip: /usr/share/doc/systemtap/README.Debian should help you get started.'


def _mocked_external_command(_, **__):
    return 1


def _mocked_flag_support(_):
    return True


def _mocked_libs_existence_fails(_):
    return False


def _mocked_libs_existence_exception(_):
    raise NameError


def _mocked_record_processing(_, __, ___, ____):
    return 1


def _mocked_symbols_extraction(_):
    return ['_Z13SLList_insertP6SLListi', 'main', '_fini', '_init', '_Z13SLList_removeP6SLListi',
            '_ZN9SLListclsD1Ev', '_ZN9SLListclsD2Ev', '_ZN9SLListclsC1Ev', '_ZN9SLListclsC2Ev',
            '_ZN9SLListcls6InsertEi', '__libc_csu_fini', '_Z14SLList_destroyP6SLList', '_start',
            '_ZN9SLListcls10SLLelemclsC1Ei', '_Z13SLList_searchP6SLListi', '__libc_csu_init',
            '_Z11SLList_initP6SLList', '_ZN9SLListcls10SLLelemclsC2Ei', '_ZN9SLListcls6SearchEi',
            'deregister_tm_clones', 'register_tm_clones', '__do_global_dtors_aux', 'frame_dummy',
            '_dl_relocate_static_pie', '_Z14SLList_destroyP6SLList', '_ZN9SLListclsD1Ev', 'main',
            '_ZN9SLListclsD2Ev', '_fini', '_ZN9SLListcls6SearchEi', '_start',
            '_Z11SLList_initP6SLList', '_ZN9SLListcls10SLLelemclsC1Ei', '_init',
            '_ZN9SLListcls6InsertEi', '_ZN9SLListcls10SLLelemclsC2Ei', '_Z13SLList_insertP6SLListi',
            '_ZN9SLListclsC2Ev', '_Z13SLList_searchP6SLListi', '__libc_csu_init', '__libc_csu_fini',
            '_ZN9SLListclsC1Ev', '_Z13SLList_removeP6SLListi',
            '_ZNSt8__detail12_Insert_baseIiSt4pairIKiSt6vectorI5ColorSaIS4_EEESaIS7_ENS_10_'
            'Select1stESt8equal_toIiESt4hashIiENS_18_Mod_range_hashingENS_20_Default_ranged_hash'
            'ENS_20_Prime_rehash_policyENS_17_Hashtable_traitsILb0ELb0ELb1EEEEC1Ev']


def _get_latest_collect_script(script_dir):
    """Return name of the latest collect script from given script directory

    :param str script_dir: path to the directory where multiple (or single)
                           collect scripts are located
    :return str: path to the latest trace collector script
    """
    # Get all stap script in the directory and find the last one,
    # which will be then analyzed for correctness
    scripts = glob.glob(os.path.join(script_dir, 'collect_script_*.stp'))
    # Find the newest script in the directory
    latest = scripts[0]
    # Extract timestamp from the first script
    latest_timestamp = int(''.join(scripts[0][-23:-4].split('-')))
    for script in scripts:
        # Check every script file and find the biggest timestamp
        timestamp = int(''.join(script[-23:-4].split('-')))
        if timestamp >= latest_timestamp:
            latest_timestamp = timestamp
            latest = script
    return latest


def _compare_collect_scripts(new_script, reference_script):
    """Compares collect script with its reference scripts

    :param str new_script: path to the script to compare
    :param str reference_script: path to the reference script
    :return bool: True if scripts are the same (except machine specific values in the script),
                  False otherwise
    """
    # Replace the machine-specific path to the binary with some generic text to allow for comparison
    with open(new_script, 'r') as script:
        content = script.read()
    sub_content = re.sub(r'\(\".*?/tst(\\n)?\"\)', '("cmp")', content)
    with open(reference_script, 'r') as cmp:
        cmp_content = cmp.read()
    return sub_content == cmp_content


def test_collect_complexity(monkeypatch, helpers, pcs_full, complexity_collect_job):
    """Test collecting the profile using complexity collector"""
    before_object_count = helpers.count_contents_on_path(pcs_full.get_path())[0]

    cmd, args, work, collectors, posts, config = complexity_collect_job
    head = vcs.get_minor_version_info(vcs.get_minor_head())
    run.run_single_job(cmd, args, work, collectors, posts, [head], **config)

    # Assert that nothing was removed
    after_object_count = helpers.count_contents_on_path(pcs_full.get_path())[0]
    assert before_object_count + 1 == after_object_count
    profiles = os.listdir(os.path.join(pcs_full.get_path(), 'jobs'))

    new_profile = profiles[0]
    assert len(profiles) == 1
    assert new_profile.endswith(".perf")

    # Fixme: Add check that the profile was correctly generated

    script_dir = os.path.join(os.path.split(__file__)[0], 'collect_complexity', 'target')
    job_params = complexity_collect_job[5]['collector_params']['complexity']

    files = [
        '-f{}'.format(os.path.abspath(os.path.join(script_dir, file)))
        for file in job_params['files']
    ]
    rules = [
        '-r{}'.format(rule) for rule in job_params['rules']
    ]
    samplings = sum([
        ['-s {}'.format(sample['func']), sample['sample']] for sample in job_params['sampling']
    ], [])
    runner = CliRunner()
    result = runner.invoke(cli.collect, ['-c{}'.format(job_params['target_dir']),
                                         '-a test', '-w input', 'complexity',
                                         '-t{}'.format(job_params['target_dir']),
                                         ] + files + rules + samplings)
    assert result.exit_code == 0

    # Test running the job from the params using the job file
    # TODO: troubles with paths in job.yml, needs some proper solving
    # script_dir = os.path.split(__file__)[0]
    # source_dir = os.path.join(script_dir, 'collect_complexity')
    # job_config_file = os.path.join(source_dir, 'job.yml')
    # result = runner.invoke(cli.collect, ['-c{}'.format(job_params['target_dir']),
    #                                      '-p{}'.format(job_config_file), 'complexity'])
    # assert result.exit_code == 0

    # test some scoped and templatized prototypes taken from a more difficult project
    monkeypatch.setattr(symbols, 'extract_symbols', _mocked_symbols_extraction)
    more_rules = ['Gif::Ctable::Ctable(Gif::Ctable&&)',
                  'std::tuple<int&&>&& std::forward<std::tuple<int&&> >(std::remove_reference<std::tuple<int&&> >::type&)']
    rules.extend(['-r{}'.format(rule) for rule in more_rules])
    result = runner.invoke(cli.collect, ['-c{}'.format(job_params['target_dir']), 'complexity',
                                         '-t{}'.format(job_params['target_dir']),
                                         ] + files + rules + samplings)
    assert result.exit_code == 0
    assert 'stored profile' in result.output


def test_collect_complexity_errors(monkeypatch, pcs_full, complexity_collect_job):
    """Test various scenarios where something goes wrong during the collection process.
    """
    # Get the job.yml parameters
    script_dir = os.path.join(os.path.split(__file__)[0], 'collect_complexity', 'target')
    job_params = complexity_collect_job[5]['collector_params']['complexity']

    files = [
        '-f{}'.format(os.path.abspath(os.path.join(script_dir, file)))
        for file in job_params['files']
    ]
    rules = [
        '-r{}'.format(rule) for rule in job_params['rules']
    ]
    samplings = sum([
        ['-s {}'.format(sample['func']), sample['sample']] for sample in job_params['sampling']
    ], [])

    # prepare the runner
    runner = CliRunner()

    # Try missing parameters --target-dir and --files
    # TODO: the exit code is 0 even though an exception is raised or non-zero value returned
    result = runner.invoke(cli.collect, ['complexity'])
    assert result.exit_code == 0
    assert '--target-dir parameter must be supplied' in result.output

    result = runner.invoke(cli.collect, ['complexity', '-t{}'.format(job_params['target_dir'])])
    assert result.exit_code == 0
    assert '--files parameter must be supplied' in result.output

    # Try supplying invalid directory path, which is a file instead
    invalid_target = os.path.join(os.path.dirname(script_dir), 'job.yml')
    result = runner.invoke(cli.collect, ['complexity', '-t{}'.format(invalid_target)])
    assert result.exit_code == 0
    assert 'already exists' in result.output

    # Simulate the failure of 'cmake' utility
    old_run = utils.run_external_command
    monkeypatch.setattr(utils, 'run_external_command', _mocked_external_command)
    command = ['-c{}'.format(job_params['target_dir']), 'complexity',
               '-t{}'.format(job_params['target_dir'])] + files + rules + samplings
    result = runner.invoke(cli.collect, command)
    assert 'CalledProcessError(1, \'cmake\')' in result.output
    monkeypatch.setattr(utils, 'run_external_command', old_run)

    # Simulate that the flag is supported, which leads to failure in build process for older g++
    old_flag = makefiles._is_flag_support
    monkeypatch.setattr(makefiles, '_is_flag_support', _mocked_flag_support)
    result = runner.invoke(cli.collect, command)
    assert 'stored profile' in result.output or 'CalledProcessError(2, \'make\')' in result.output
    monkeypatch.setattr(makefiles, '_is_flag_support', old_flag)

    # Simulate that some required library is missing
    old_libs_existence = makefiles._libraries_exist
    monkeypatch.setattr(makefiles, '_libraries_exist', _mocked_libs_existence_fails)
    result = runner.invoke(cli.collect, command)
    assert 'libraries are missing' in result.output

    # Simulate that the libraries directory path cannot be found
    monkeypatch.setattr(makefiles, '_libraries_exist', _mocked_libs_existence_exception)
    result = runner.invoke(cli.collect, command)
    print(result.output)
    assert 'Unable to locate' in result.output
    monkeypatch.setattr(makefiles, '_libraries_exist', old_libs_existence)

    # Simulate the failure of output processing
    old_record_processing = complexity._process_file_record
    monkeypatch.setattr(complexity, '_process_file_record', _mocked_record_processing)
    result = runner.invoke(cli.collect, command)
    assert 'Call stack error' in result.output
    monkeypatch.setattr(complexity, '_process_file_record', old_record_processing)


def test_collect_trace(monkeypatch, pcs_full, trace_collect_job):
    """Test running the trace collector from the CLI with parameter handling

    Expecting no errors
    """
    monkeypatch.setattr(stap, 'systemtap_collect', _mocked_stap)
    runner = CliRunner()

    script_dir = os.path.join(os.path.split(__file__)[0], 'collect_trace')
    target = os.path.join(script_dir, 'tst')
    job_params = trace_collect_job[5]['collector_params']['trace']

    func = ['-f{}'.format(func) for func in job_params['func']]
    func_sampled = []
    for f in job_params['func_sampled']:
        func_sampled.append('-fs')
        func_sampled.append(f[0])
        func_sampled.append(f[1])
    static = ['-s{}'.format(rule) for rule in job_params['static']]
    binary = ['-b{}'.format(target)]

    result = runner.invoke(cli.collect, ['-c{}'.format(target),
                                         'trace'] + func + func_sampled + static + binary)

    assert result.exit_code == 0

    # Test running the job from the params using the job file
    # Fixme: yaml parameters applied after the cli, thus cli reports missing parameters
    # script_dir = os.path.split(__file__)[0]
    # source_dir = os.path.join(script_dir, 'collect_trace')
    # job_config_file = os.path.join(source_dir, 'job.yml')
    # result = runner.invoke(cli.collect, ['-c{}'.format(target), '-p{}'.format(job_config_file),
    #                                      'trace'])
    # assert result.exit_code == 0

    # Test running the job from the params using the yaml string
    result = runner.invoke(cli.collect, ['-c{}'.format(target),
                                         '-p\"global_sampling: 2\"',
                                         'trace'] + func + func_sampled + static + binary)
    assert result.exit_code == 0

    # Try different template
    result = runner.invoke(cli.collect, [
        '-ot', '%collector%-profile',
        '-c{}'.format(target),
        '-p\"method: custom\"',
        'trace',
    ] + func + func_sampled + static + binary)
    del config.runtime().data['format']
    decorators.remove_from_function_args_cache("lookup_key_recursively")
    assert result.exit_code == 0
    pending_profiles = os.listdir(os.path.join(os.getcwd(), ".perun", "jobs"))
    assert "trace-profile.perf" in pending_profiles

    # Test duplicity detection and pairing
    result = runner.invoke(cli.collect,
                           ['-c{}'.format(target), 'trace', '-f', 'main', '-f', 'main', '-fs',
                            'main', 2, '-fs', 'main', 2, '-s', 'BEFORE_CYCLE', '-ss',
                            'BEFORE_CYCLE', 3, '-s', 'BEFORE_CYCLE_end', '-s',
                            'BEFORE_CYCLE#BEFORE_CYCLE_end', '-ss', 'TEST_SINGLE', 4, '-s',
                            'TEST_SINGLE2', '-fs', 'test', -3] + binary)
    assert result.exit_code == 0
    # Compare the created script with the correct one
    assert _compare_collect_scripts(_get_latest_collect_script(script_dir),
                                    os.path.join(script_dir, 'cmp_script.txt'))

    # Test negative global sampling
    result = runner.invoke(cli.collect, ['-c{}'.format(target), 'trace', '-g -2'] + binary)
    assert result.exit_code == 1

    # Try missing parameter -c
    result = runner.invoke(cli.collect, ['trace'] + binary)
    assert result.exit_code == 1

    # Try invalid parameter --method
    result = runner.invoke(cli.collect, ['-c{}'.format(target), 'trace', '-minvalid'] + binary)
    assert result.exit_code == 2

    # Try binary parameter that is actually not executable ELF
    target = os.path.join(script_dir, 'cpp_sources', 'tst.cpp')
    result = runner.invoke(cli.collect, ['-c{}'.format(target), 'trace'])
    assert result.exit_code == 1
    assert 'is not an executable ELF file.' in result.output


def test_collect_trace_strategies(monkeypatch, pcs_full):
    """Test various trace collector strategies

    Expecting no errors and correctly generated scripts
    """
    monkeypatch.setattr(stap, 'systemtap_collect', _mocked_stap)
    monkeypatch.setattr(strategy, '_load_static_probes', _mocked_stap_extraction)
    runner = CliRunner()

    script_dir = os.path.join(os.path.split(__file__)[0], 'collect_trace')
    target = os.path.join(script_dir, 'tst')

    # Test simple userspace strategy without external modification or sampling
    result = runner.invoke(cli.collect, ['-c{}'.format(target), 'trace', '-m', 'userspace'])
    assert result.exit_code == 0
    assert _compare_collect_scripts(_get_latest_collect_script(script_dir),
                                    os.path.join(script_dir, 'strategy1_script.txt'))
    # Test simple u_sampled strategy without external modification
    result = runner.invoke(cli.collect, ['-c{}'.format(target), 'trace', '-m', 'u_sampled'])
    assert result.exit_code == 0
    assert _compare_collect_scripts(_get_latest_collect_script(script_dir),
                                    os.path.join(script_dir, 'strategy2_script.txt'))
    # Test simple all strategy without external modification or sampling
    result = runner.invoke(cli.collect, ['-c{}'.format(target), 'trace', '-m', 'all'])
    assert result.exit_code == 0
    assert _compare_collect_scripts(_get_latest_collect_script(script_dir),
                                    os.path.join(script_dir, 'strategy3_script.txt'))
    # Test simple a_sampled strategy with verbose trace and without external modification
    result = runner.invoke(cli.collect, ['-c{}'.format(target), 'trace', '-m', 'a_sampled', '-vt'])
    assert result.exit_code == 0
    assert _compare_collect_scripts(_get_latest_collect_script(script_dir),
                                    os.path.join(script_dir, 'strategy4_script.txt'))
    # Change the mocked static extractor to empty one
    monkeypatch.setattr(strategy, '_load_static_probes', _mocked_stap_extraction_empty)
    # Test userspace strategy without static probes and added global_sampling
    result = runner.invoke(cli.collect, ['-c{}'.format(target), 'trace', '-m', 'userspace',
                                         '--no-static', '-g', '10'])
    assert result.exit_code == 0
    assert _compare_collect_scripts(_get_latest_collect_script(script_dir),
                                    os.path.join(script_dir, 'strategy5_script.txt'))
    # Test u_sampled strategy without static probes and overriden global_sampling
    # The output should be exactly the same as the previous
    result = runner.invoke(cli.collect, ['-c{}'.format(target), 'trace', '-m', 'u_sampled',
                                         '--no-static', '-g', '10'])
    assert result.exit_code == 0
    assert _compare_collect_scripts(_get_latest_collect_script(script_dir),
                                    os.path.join(script_dir, 'strategy5_script.txt'))
    # Test userspace strategy with overridden function, respecified function and invalid function
    result = runner.invoke(cli.collect, ['-c{}'.format(target), 'trace', '-m', 'userspace', '-fs',
                                         'main', '4', '-f', '_Z12QuickSortBadPii', '-f', 'invalid'])
    assert result.exit_code == 0
    assert _compare_collect_scripts(_get_latest_collect_script(script_dir),
                                    os.path.join(script_dir, 'strategy6_script.txt'))
    # Test userspace strategy with invalid static probe (won't be detected as --no-static is used)
    result = runner.invoke(cli.collect, ['-c{}'.format(target), 'trace', '-m', 'userspace',
                                         '--no-static', '-s', 'INVALID'])
    assert result.exit_code == 0
    assert _compare_collect_scripts(_get_latest_collect_script(script_dir),
                                    os.path.join(script_dir, 'strategy7_script.txt'))
    # Test u_sampled strategy with more static probes to check correct pairing
    monkeypatch.setattr(strategy, '_load_static_probes', _mocked_stap_extraction2)
    result = runner.invoke(cli.collect, ['-c{}'.format(target), 'trace', '-m', 'u_sampled'])
    assert result.exit_code == 0
    assert _compare_collect_scripts(_get_latest_collect_script(script_dir),
                                    os.path.join(script_dir, 'strategy8_script.txt'))


def test_collect_trace_fail(monkeypatch, helpers, pcs_full, trace_collect_job):
    """Test failed collecting using trace collector"""
    global _mocked_stap_code
    global _mocked_stap_file

    monkeypatch.setattr(stap, 'systemtap_collect', _mocked_stap)
    monkeypatch.setattr(strategy, '_load_static_probes', _mocked_stap_extraction)

    head = vcs.get_minor_version_info(vcs.get_minor_head())
    before_object_count = helpers.count_contents_on_path(pcs_full.get_path())[0]

    runner = CliRunner()
    script_dir = os.path.join(os.path.split(__file__)[0], 'collect_trace')
    target = os.path.join(script_dir, 'tst')

    # Test malformed file that ends in unexpected way
    _mocked_stap_file = 'record_malformed.txt'
    result = runner.invoke(cli.collect, ['-c{}'.format(target), '-w 1', 'trace', '-m', 'userspace'])
    # However, the collector should still be able to correctly process it
    assert result.exit_code == 0
    after_object_count = helpers.count_contents_on_path(pcs_full.get_path())[0]
    assert before_object_count + 2 == after_object_count
    before_object_count = after_object_count

    # Test malformed file that ends in another unexpected way
    _mocked_stap_file = 'record_malformed2.txt'
    result = runner.invoke(cli.collect, ['-c{}'.format(target), '-w 2', 'trace', '-m', 'userspace'])
    # Check if the collector managed to process the file
    assert result.exit_code == 0
    after_object_count = helpers.count_contents_on_path(pcs_full.get_path())[0]
    assert before_object_count + 1 == after_object_count
    before_object_count = after_object_count

    # Test malformed file that has corrupted record
    _mocked_stap_file = 'record_malformed3.txt'
    result = runner.invoke(cli.collect, ['-c{}'.format(target), '-w 3', 'trace', '-m', 'userspace'])
    # Check if the collector managed to process the file
    assert result.exit_code == 0
    after_object_count = helpers.count_contents_on_path(pcs_full.get_path())[0]
    assert before_object_count + 1 == after_object_count
    before_object_count = after_object_count

    # Test malformed file that has misplaced data chunk
    _mocked_stap_file = 'record_malformed4.txt'
    result = runner.invoke(cli.collect, ['-c{}'.format(target), '-w 4', 'trace', '-m', 'userspace'])
    # Check if the collector managed to process the file
    assert result.exit_code == 0
    after_object_count = helpers.count_contents_on_path(pcs_full.get_path())[0]
    assert before_object_count + 1 == after_object_count
    before_object_count = after_object_count

    # Simulate the failure of the systemTap
    _mocked_stap_code = 1
    runner.invoke(cli.collect, ['-c{}'.format(target), 'trace', '-m', 'userspace'])
    # Assert that nothing was added
    after_object_count = helpers.count_contents_on_path(pcs_full.get_path())[0]
    assert before_object_count == after_object_count
    _mocked_stap_code = 0

    # Simulate the failure during trace processing and stacks output
    monkeypatch.setattr(stap, '_init_stack_and_map', _mocked_trace_stack)
    monkeypatch.setattr(stap, '_parse_record', _mocked_parse_record)
    result = runner.invoke(cli.collect, ['-c{}'.format(target), '-w 4', 'trace', '-m', 'userspace'])
    assert 'Error while parsing the raw trace record' in result.output


def test_collect_memory(capsys, helpers, pcs_full, memory_collect_job, memory_collect_no_debug_job):
    """Test collecting the profile using the memory collector"""
    # Fixme: Add check that the profile was correctly generated
    before_object_count = helpers.count_contents_on_path(pcs_full.get_path())[0]
    head = vcs.get_minor_version_info(vcs.get_minor_head())
    memory_collect_job += ([head], )

    run.run_single_job(*memory_collect_job)

    # Assert that nothing was removed
    after_object_count = helpers.count_contents_on_path(pcs_full.get_path())[0]
    assert before_object_count + 2 == after_object_count

    profiles = list(filter(helpers.index_filter, os.listdir(os.path.join(pcs_full.get_path(), 'jobs'))))
    new_profile = profiles[0]
    assert len(profiles) == 1
    assert new_profile.endswith(".perf")

    cmd, args, _, colls, posts, _ = memory_collect_job
    run.run_single_job(cmd, args, ["hello"], colls, posts, [head], **{'no_func': 'fun', 'sampling': 0.1})

    profiles = list(filter(helpers.index_filter, os.listdir(os.path.join(pcs_full.get_path(), 'jobs'))))
    new_smaller_profile = [p for p in profiles if p != new_profile][0]
    assert len(profiles) == 2
    assert new_smaller_profile.endswith(".perf")

    # Assert that nothing was removed
    after_second_object_count = helpers.count_contents_on_path(pcs_full.get_path())[0]
    assert after_object_count + 1 == after_second_object_count

    # Fixme: Add check that the profile was correctly generated

    log.VERBOSITY = log.VERBOSE_DEBUG
    memory_collect_no_debug_job += ([head], )
    run.run_single_job(*memory_collect_no_debug_job)
    last_object_count = helpers.count_contents_on_path(pcs_full.get_path())[0]
    _, err = capsys.readouterr()
    assert after_second_object_count == last_object_count
    assert 'debug info' in err
    assert 'File "' in err
    log.VERBOSITY = log.VERBOSE_RELEASE

    target_bin = memory_collect_job[0][0]
    collector_unit = Unit('memory', {
        'all': False,
        'no_func': 'main'
    })
    job = Job('memory', [], str(target_bin), '', '')
    _, prof = run.run_collector(collector_unit, job)

    assert len(list(query.all_resources_of(prof))) == 2

    collector_unit = Unit('memory', {
        'all': False,
        'no_source': 'memory_collect_test.c'
    })
    job = Job('memory', [], str(target_bin), '', '')
    _, prof = run.run_collector(collector_unit, job)

    assert len(list(query.all_resources_of(prof))) == 0


def test_collect_memory_with_generator(pcs_full, memory_collect_job):
    """Tries to collect the memory with integer generators"""
    cmd = memory_collect_job[0][0]
    collector = Unit('memory', {})
    integer_job = Job(collector, [], cmd, '', '')
    integer_generator = IntegerGenerator(integer_job, 1, 3, 1)
    memory_profiles = list(integer_generator.generate(run.run_collector))
    assert len(memory_profiles) == 1


def test_collect_time(monkeypatch, helpers, pcs_full, capsys):
    """Test collecting the profile using the time collector"""
    # Count the state before running the single job
    before_object_count = helpers.count_contents_on_path(pcs_full.get_path())[0]
    head = vcs.get_minor_version_info(vcs.get_minor_head())

    run.run_single_job(["echo"], "", ["hello"], ["time"], [], [head])

    # Assert outputs
    out, err = capsys.readouterr()
    assert err == ''
    assert 'Successfully collected data from echo' in out

    # Assert that just one profile was created
    # + 1 for index
    after_object_count = helpers.count_contents_on_path(pcs_full.get_path())[0]
    assert before_object_count + 2 == after_object_count

    profiles = list(filter(helpers.index_filter, os.listdir(os.path.join(pcs_full.get_path(), 'jobs'))))
    new_profile = profiles[0]
    assert len(profiles) == 1
    assert new_profile.endswith(".perf")

    # Test running time with error
    run.run_single_job(["echo"], "", ["hello"], ["time"], [], [head])

    def collect_raising_exception(**kwargs):
        raise Exception("Something happened lol!")

    monkeypatch.setattr("perun.collect.time.run.collect", collect_raising_exception)
    run.run_single_job(["echo"], "", ["hello"], ["time"], [], [head])
    _, err = capsys.readouterr()
    assert 'Something happened lol!' in err
