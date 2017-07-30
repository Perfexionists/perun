import sys
import perun.cli as cli

from click.testing import CliRunner


__author__ = 'Tomas Fiedor'


def test_alloclist(monkeypatch, helpers, pcs_full, valid_profile_pool):
    """Test simple queries over memory profiles (alloclist)

    Expecting no errors and outputed stuff
    """
    helpers.populate_repo_with_untracked_profiles(pcs_full.path, valid_profile_pool)
    runner = CliRunner()

    result = runner.invoke(cli.show, ['1@p', 'alloclist', 'all'])
    assert result.exit_code == 0
    assert "warn" not in result.output
    assert "#20" in result.output

    result = runner.invoke(cli.show, ['1@p', 'alloclist', 'top'])
    assert result.exit_code == 0
    assert "warn" not in result.output
    assert "#10" in result.output

    result = runner.invoke(cli.show, ['1@p', 'alloclist', 'top', '--limit-to=15'])
    assert result.exit_code == 0
    assert "warn" not in result.output
    assert "#15" in result.output

    result = runner.invoke(cli.show, ['1@p', 'alloclist', 'most'])
    assert result.exit_code == 0
    assert "warn" not in result.output
    assert "20x" in result.output
    assert "#4" in result.output

    result = runner.invoke(cli.show, ['1@p', 'alloclist', 'sum'])
    assert result.exit_code == 0
    assert "warn" not in result.output
    assert "132B" in result.output
    assert "#4" in result.output

    args = ['1@p', 'alloclist', 'func', '--function=foo1']
    monkeypatch.setattr(sys, 'argv', args)
    result = runner.invoke(cli.show, args)
    assert result.exit_code == 0
    assert "warn" not in result.output
    assert "#5" in result.output

    args = ['1@p', 'alloclist', 'func']
    monkeypatch.setattr(sys, 'argv', args)
    result = runner.invoke(cli.show, args)
    assert "warn" not in result.output
    assert result.exit_code == 2

    args = ['1@p', 'alloclist', 'all', '--from-time=0.010', '--to-time=0.040']
    monkeypatch.setattr(sys, 'argv', args)
    result = runner.invoke(cli.show, args)
    assert result.exit_code == 0
    assert "warn" not in result.output
    assert "#2" in result.output

    args = ['1@p', 'alloclist', 'all', '--to-time=0.040']
    monkeypatch.setattr(sys, 'argv', args)
    result = runner.invoke(cli.show, args)
    assert "warn" not in result.output
    assert result.exit_code == 0

    args = ['1@p', 'alloclist', 'func', '--function=foo1', '-a']
    monkeypatch.setattr(sys, 'argv', args)
    result = runner.invoke(cli.show, args)
    assert result.exit_code == 0
    assert "warn" not in result.output
    assert "#10" in result.output


def test_alloclist_warns(monkeypatch, helpers, pcs_full, valid_profile_pool):
    """Test simple queries with superfluous arguments

    Expecting no errors, just writing warnings to the outptu
    """
    helpers.populate_repo_with_untracked_profiles(pcs_full.path, valid_profile_pool)
    runner = CliRunner()

    args = ['1@p', 'alloclist', 'top', '--from-time=0.5']
    monkeypatch.setattr(sys, 'argv', args)
    result = runner.invoke(cli.show, args)
    assert "warn" in result.output
    assert result.exit_code == 0
    assert "#10" in result.output

    args = ['1@p', 'alloclist', 'all', '--limit-to=10']
    monkeypatch.setattr(sys, 'argv', args)
    result = runner.invoke(cli.show, args)
    assert "warn" in result.output
    assert result.exit_code == 0
    assert "#20" in result.output

    args = ['1@p', 'alloclist', 'all', '--function=foo1']
    monkeypatch.setattr(sys, 'argv', args)
    result = runner.invoke(cli.show, args)
    assert "warn" in result.output
    assert result.exit_code == 0
    assert "#20" in result.output
