"""Basic tests for operating with the perun configuration through 'perun config'.

Tests adding and getting keys from local and global configurations.
"""

import pytest
import random

import perun.logic.commands as commands

from perun.utils.exceptions import NotPerunRepositoryException, MissingConfigSectionException, \
    ExternalEditorErrorException, InvalidConfigOperationException

__author__ = 'Tomas Fiedor'


@pytest.mark.usefixtures('cleandir')
def test_get_outside_of_pcs():
    """Test calling 'perun --get KEY' outside of the scope of the PCS"""
    with pytest.raises(NotPerunRepositoryException):
        commands.config('local', 'edit')


def test_get_exists(pcs_full, capsys):
    """Test calling 'perun --get KEY', such that the key exists"""
    # Get valid thing from local
    commands.config('local', 'get', 'vcs.type')
    out, err = capsys.readouterr()
    assert 'git' in out
    assert err == ''

    # Get valid thing from global
    commands.config('shared', 'get', 'general.editor')
    out_global, err = capsys.readouterr()
    assert 'general.editor: ' in out_global
    assert err == ''

    # First verify there is nothing in local
    with pytest.raises(MissingConfigSectionException):
        commands.config('local', 'get', 'general.editor')
        out, err = capsys.readouterr()
        assert out == err
        assert 'fatal' in err

    # Now try to recursively obtain the same thing
    commands.config('recursive', 'get', 'general.editor')
    out, err = capsys.readouterr()
    assert out == out_global
    assert err == ''

    # Try to recursively obtain nonexistant
    with pytest.raises(MissingConfigSectionException):
        commands.config('recursive', 'get', 'super.editor')

    # Try get without key
    with pytest.raises(InvalidConfigOperationException):
        commands.config('shared', 'set')


def test_set_exists(pcs_full, capsys):
    """Test calling 'perun --set KEY', such that the key was in config and is reset"""
    # Set valid thing in local
    commands.config('local', 'set', 'bogus.key', 'true')
    capsys.readouterr()
    commands.config('local', 'get', 'bogus.key')
    out, err = capsys.readouterr()
    assert 'bogus.key' in out and 'true' in out
    assert err == ''

    # Set valid thing in global
    random_value = str(random.randint(0, 10**6))
    commands.config('shared', 'set', 'testkey', random_value)
    capsys.readouterr()
    commands.config('shared', 'get', 'testkey')
    out, err = capsys.readouterr()
    assert 'testkey' in out and random_value in out
    assert err == ''

    # Set valid thing in nearest
    with pytest.raises(MissingConfigSectionException):
        commands.config('local', 'get', 'test2key')
    commands.config('recursive', 'set', 'test2key', 'testvalue')
    capsys.readouterr()
    commands.config('recursive', 'get', 'test2key')
    out, err = capsys.readouterr()
    assert 'test2key' in out and 'testvalue' in out
    assert err == ''

    # Try set without key
    with pytest.raises(InvalidConfigOperationException):
        commands.config('shared', 'set', 'key')


def test_edit(pcs_full, capsys):
    """Test 'editing' the configuration file

    Expecting no errors or exceptions
    """
    # First try to get the exception by calling bogus editor
    commands.config('local', 'set', 'general.editor', 'bogus')
    with pytest.raises(ExternalEditorErrorException):
        commands.config('local', 'edit')
    capsys.readouterr()

    # Use cat as a valid editor
    commands.config('local', 'set', 'general.editor', 'cat')
    commands.config('local', 'edit')
    capsys.readouterr()
    _, err = capsys.readouterr()
    assert err == ''
