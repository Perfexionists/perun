""" Basic tests for table plot visualization """

import os
from click.testing import CliRunner

import perun.cli as cli
import perun.vcs as vcs

TABLE_TEST_DIR = os.path.join(os.path.split(__file__)[0], "table_files")
__author__ = 'Tomas Fiedor'


def output_to_list(output):
    """
    :param list output: list of lines
    :return: sorted list of lines without newlines and filtered out empty lines
    """
    return sorted([l.rstrip() for l in output if l.rstrip()])


def assert_files_match(lhs, rhs):
    """Asserts that two files handles match

    :param handle lhs: left file handle
    :param handle rhs: right file handle
    """
    assert output_to_list(lhs.readlines()) == output_to_list(rhs.readlines())


def assert_files_match_output(result, rhs):
    """Asserts that file and stdout output match

    :param list result: left stdout
    :param handle rhs: right file handle
    """
    assert output_to_list(result.output.split('\n')) == output_to_list(rhs.readlines())


def profile_filter(generator, rule):
    """Finds concrete profile by the rule in profile generator.

    Arguments:
        generator(generator): stream of profiles as tuple: (name, dict)
        rule(str): string to search in the name

    Returns:
        Profile: first profile with name containing the rule
    """
    # Loop the generator and test the rule
    for profile in generator:
        if rule in profile[0]:
            return profile[0]


def test_table_cli(helpers, pcs_full, postprocess_profiles):
    """Test outputing profiles as tables"""
    runner = CliRunner()
    result = runner.invoke(cli.show, [
        '0@i', 'tableof', '--to-stdout', 'resources'
    ])
    assert result.exit_code == 0
    with open(os.path.join(TABLE_TEST_DIR, 'table_resources_ref_basic'), 'r') as trb:
        assert_files_match_output(result, trb)

    models_profile = profile_filter(postprocess_profiles, 'complexity-models.perf')
    added = helpers.prepare_profile(
        pcs_full.get_job_directory(), models_profile, vcs.get_minor_head()
    )
    result = runner.invoke(cli.add, ['--keep-profile', '{}'.format(added)])
    assert result.exit_code == 0

    result = runner.invoke(cli.show, [
        '0@p', 'tableof', '--to-stdout', 'models'
    ])
    assert result.exit_code == 0
    with open(os.path.join(TABLE_TEST_DIR, 'table_models_ref_basic'), 'r') as trb:
        assert_files_match_output(result, trb)

    result = runner.invoke(cli.show, [
        '0@p', 'tableof', '--to-stdout', 'models', '-h', 'uid', '-h', 'model', '-h', 'coeffs'
    ])
    assert result.exit_code == 0
    with open(os.path.join(TABLE_TEST_DIR, 'table_models_ref_pruned'), 'r') as trb:
        assert_files_match_output(result, trb)

    result = runner.invoke(cli.show, [
        '0@p', 'tableof', '--to-stdout', 'models', '-h', 'non-existant', '-h', 'model', '-h', 'coeffs'
    ])
    assert result.exit_code == 2
    assert "invalid choice for table header: non-existant" in result.output

    # Test different format
    result = runner.invoke(cli.show, [
        '0@p', 'tableof', '--to-stdout', '-f', 'latex', 'models', '-h', 'uid', '-h', 'model', '-h', 'coeffs'
    ])
    assert result.exit_code == 0
    with open(os.path.join(TABLE_TEST_DIR, 'table_models_ref_latex'), 'r') as trb:
        assert_files_match_output(result, trb)

    # Test output to file
    result = runner.invoke(cli.show, [
        '0@p', 'tableof', '--output-file', 'test_output', 'models', '-h', 'uid', '-h', 'model', '-h', 'coeffs'
    ])
    output_file = os.path.join(os.getcwd(), 'test_output')
    assert result.exit_code == 0
    assert os.path.exists(output_file)
    with open(os.path.join(TABLE_TEST_DIR, 'table_models_ref_pruned'), 'r') as trb:
        with open(output_file, 'r') as of:
            assert_files_match(trb, of)

    # Test sorts and filters
    result = runner.invoke(cli.show, [
        '0@p', 'tableof', '--to-stdout', 'models', '--sort-by', 'r_square', '--filter-by', 'model', 'linear', '--filter-by', 'model', 'quadratic'
    ])
    assert result.exit_code == 0
    with open(os.path.join(TABLE_TEST_DIR, 'table_models_ref_sorted_filtered'), 'r') as trb:
        assert_files_match_output(result, trb)

    result = runner.invoke(cli.show, [
        '0@p', 'tableof', '--to-stdout', 'models', '--sort-by', 'class'
    ])
    assert "Error: invalid key choice for sorting the table: class " in str(result.output)
    assert result.exit_code == 2

    result = runner.invoke(cli.show, [
        '0@p', 'tableof', '--to-stdout', 'models', '--filter-by', 'class', 'linear'
    ])
    assert "Error: invalid key choice for filtering: class" in str(result.output)
    assert result.exit_code == 2

    # Test sorts and filters
    result = runner.invoke(cli.show, [
        '0@p', 'tableof', '--to-stdout', 'models', '--filter-by', 'r_square', '0', '--filter-by', 'model', 'linear'
    ])
    assert result.exit_code == 0
    with open(os.path.join(TABLE_TEST_DIR, 'table_models_ref_empty'), 'r') as trb:
        assert_files_match_output(result, trb)
