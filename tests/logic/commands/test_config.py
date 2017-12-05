"""Basic tests for operating with the perun configuration through 'perun config'.

Tests adding and getting keys from local and global configurations.
"""

import pytest
import random
import os

import perun.logic.commands as commands
import perun.logic.config as config

from perun.utils.exceptions import NotPerunRepositoryException, MissingConfigSectionException, \
    ExternalEditorErrorException

__author__ = 'Tomas Fiedor'


@pytest.mark.usefixtures('cleandir')
def test_get_outside_of_pcs():
    """Test calling 'perun --get KEY' outside of the scope of the PCS"""
    with pytest.raises(NotPerunRepositoryException):
        commands.config_edit('local')


def test_get_exists(pcs_full, capsys):
    """Test calling 'perun --get KEY', such that the key exists"""
    # Get valid thing from local
    commands.config_get('local', 'vcs.type')
    out, err = capsys.readouterr()
    assert 'git' in out
    assert err == ''

    # Get valid thing from global
    commands.config_get('shared', 'general.editor')
    out_global, err = capsys.readouterr()
    assert 'general.editor: ' in out_global
    assert err == ''

    # First verify there is nothing in local
    with pytest.raises(MissingConfigSectionException):
        commands.config_get('local', 'general.editor')
        out, err = capsys.readouterr()
        assert out == err
        assert 'fatal' in err

    # Now try to recursively obtain the same thing
    commands.config_get('recursive', 'general.editor')
    out, err = capsys.readouterr()
    assert out == out_global
    assert err == ''

    # Try to recursively obtain nonexistant
    with pytest.raises(MissingConfigSectionException):
        commands.config_get('recursive', 'super.editor')


def test_set_exists(pcs_full, capsys):
    """Test calling 'perun --set KEY', such that the key was in config and is reset"""
    # Set valid thing in local
    commands.config_set('local', 'bogus.key', 'true')
    capsys.readouterr()
    commands.config_get('local', 'bogus.key')
    out, err = capsys.readouterr()
    assert 'bogus.key' in out and 'true' in out
    assert err == ''

    # Set valid thing in global
    random_value = str(random.randint(0, 10**6))
    commands.config_set('shared', 'testkey', random_value)
    capsys.readouterr()
    commands.config_get('shared', 'testkey')
    out, err = capsys.readouterr()
    assert 'testkey' in out and random_value in out
    assert err == ''

    # Set valid thing in nearest
    with pytest.raises(MissingConfigSectionException):
        commands.config_get('local', 'test2key')
    commands.config_set('recursive', 'test2key', 'testvalue')
    capsys.readouterr()
    commands.config_get('recursive', 'test2key')
    out, err = capsys.readouterr()
    assert 'test2key' in out and 'testvalue' in out
    assert err == ''


def test_edit(pcs_full, capsys):
    """Test 'editing' the configuration file

    Expecting no errors or exceptions
    """
    # First try to get the exception by calling bogus editor
    commands.config_set('local', 'general.editor', 'bogus')
    with pytest.raises(ExternalEditorErrorException):
        commands.config_edit('local')
    capsys.readouterr()

    # Use cat as a valid editor
    commands.config_set('local', 'general.editor', 'cat')
    commands.config_edit('local')
    capsys.readouterr()
    _, err = capsys.readouterr()
    assert err == ''


def test_append(capsys, tmpdir):
    """Test appending of keys in the configuration

    Expecting no errors or exceptions
    """
    # Create custom config object
    temp_dir = str(tmpdir.mkdir('.perun').join('local.yml'))
    temp_config = config.Config('local', temp_dir, {
        'existinglist': ['func1']
    })

    temp_config.append('existinglist', 'func2')
    # Assert that something actually was appended
    assert len(temp_config.data['existinglist']) == 2
    # Assert that it was appended to correct place
    assert temp_config.data['existinglist'][-1] == 'func2'

    temp_config.append('nonexistinglist', 'foo')
    assert len(temp_config.data['nonexistinglist']) == 1
    assert temp_config.data['nonexistinglist'][0] == 'foo'
