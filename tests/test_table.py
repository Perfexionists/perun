""" Basic tests for table plot visualization """

import os
from click.testing import CliRunner

import perun.cli as cli

TABLE_TEST_DIR = os.path.join(os.path.split(__file__)[0], "table_files")
__author__ = 'Tomas Fiedor'


def test_table_cli(pcs_full):
    """Test outputing profiles as tables"""
    runner = CliRunner()
    result = runner.invoke(cli.show, [
        '0@i', 'table'
    ])
    assert result.exit_code == 0
    with open(os.path.join(TABLE_TEST_DIR, 'table_ref_basic'), 'r') as trb:
        assert sorted(result.output) == sorted("".join(trb.readlines()))

