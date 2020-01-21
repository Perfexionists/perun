""" Basic tests for table plot visualization """

import os
from click.testing import CliRunner

import perun.cli as cli
import perun.vcs as vcs

TABLE_TEST_DIR = os.path.join(os.path.split(__file__)[0], "table_files")
__author__ = 'Tomas Fiedor'


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
        '0@i', 'tableof', 'resources'
    ])
    assert result.exit_code == 0
    with open(os.path.join(TABLE_TEST_DIR, 'table_resources_ref_basic'), 'r') as trb:
        assert sorted(result.output) == sorted("".join(trb.readlines()))

    models_profile = profile_filter(postprocess_profiles, 'complexity-models.perf')
    added = helpers.prepare_profile(
        pcs_full.get_job_directory(), models_profile, vcs.get_minor_head()
    )
    result = runner.invoke(cli.add, ['--keep-profile', '{}'.format(added)])
    assert result.exit_code == 0

    result = runner.invoke(cli.show, [
        '0@i', 'tableof', 'models'
    ])
    assert result.exit_code == 0
    print(result.output)
    with open(os.path.join(TABLE_TEST_DIR, 'table_models_ref_basic'), 'r') as trb:
        assert sorted(result.output) == sorted("".join(trb.readlines()))
