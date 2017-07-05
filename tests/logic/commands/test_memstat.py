
import perun.cli as cli

from click.testing import CliRunner


__author__ = 'Tomas Fiedor'


def test_memstat(pcs_full):
    """Test simple queries over memory profiles (memstat)

    Expecting no errors and outputed stuff
    """
    runner = CliRunner()

    result = runner.invoke(cli.show, ['1@i', 'memstat', 'list'])
    assert result.exit_code == 0
    assert "#20" in result.output

    result = runner.invoke(cli.show, ['1@i', 'memstat', 'top'])
    assert result.exit_code == 0
    assert "#10" in result.output

    result = runner.invoke(cli.show, ['1@i', 'memstat', 'top', '--top=15'])
    assert result.exit_code == 0
    assert "#15" in result.output

    result = runner.invoke(cli.show, ['1@i', 'memstat', 'most'])
    assert result.exit_code == 0
    assert "20x" in result.output
    assert "#4" in result.output

    result = runner.invoke(cli.show, ['1@i', 'memstat', 'sum'])
    assert result.exit_code == 0
    assert "132B" in result.output
    assert "#4" in result.output

    result = runner.invoke(cli.show, ['1@i', 'memstat', 'func', '--function=foo1'])
    assert result.exit_code == 0
    assert "#5" in result.output

    result = runner.invoke(cli.show, ['1@i', 'memstat', 'func'])
    assert result.exit_code == 2

    result = runner.invoke(cli.show, ['1@i', 'memstat', 'list',
                                      '--from-time=0.010', '--to-time=0.040'])
    assert result.exit_code == 0
    assert "#3" in result.output

    result = runner.invoke(cli.show, ['1@i', 'memstat', 'list', '--to-time=0.040'])
    assert result.exit_code == 0

    result = runner.invoke(cli.show, ['1@i', 'memstat', 'func', '--function=foo1', '-a'])
    assert result.exit_code == 0
    assert "#10" in result.output
