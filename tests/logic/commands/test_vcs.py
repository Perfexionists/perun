"""Basic tests for checking the correctness of the VCS modules"""

import os
import operator

import perun.vcs as vcs
import perun.logic.store as store

__author__ = 'Tomas Fiedor'


def test_major_versions(pcs_full):
    """Test whether getting the major version for given VCS is correct

    Expecting correct behaviour and no error
    """
    vcs_type, vcs_path = pcs_full.vcs_type, pcs_full.vcs_path
    major_versions = list(vcs.walk_major_versions(vcs_type, vcs_path))

    assert len(major_versions) == 1
    major_version = major_versions[0]
    assert major_version.name == 'master'
    assert store.is_sha1(major_version.head)


def test_saved_states(pcs_full):
    """Tests saving states of the repository and check outs

    Expecting correct behaviour, without any raised exceptions
    """
    vcs_type, vcs_path = pcs_full.vcs_type, pcs_full.vcs_path

    # Is not dirty
    assert not vcs.is_dirty(vcs_type, vcs_path)

    with open("file2", "r+") as write_handle:
        previous_state = write_handle.readlines()
        write_handle.write("hello")

    # Should be dirty
    assert vcs.is_dirty(vcs_type, vcs_path)

    # The changes should be cleared
    with vcs.CleanState(vcs_type, vcs_path):
        assert not vcs.is_dirty(vcs_type, vcs_path)

        with open("file2", "r") as read_handle:
            new_state = read_handle.readlines()
        assert new_state == previous_state

    head = vcs.get_minor_head(vcs_type, vcs_path)
    minor_versions = list(
        map(operator.attrgetter('checksum'), vcs.walk_minor_versions(vcs_type, vcs_path, head))
    )

    with open("file2", "w") as write_handle:
        write_handle.write("".join(previous_state))

    with vcs.CleanState(vcs_type, vcs_path):
        # Now try checkout for all of the stuff
        vcs.checkout(vcs_type, vcs_path, minor_versions[1])
        tracked_files = os.listdir(os.getcwd())
        assert set(tracked_files) == {'.perun', '.git', 'file1'}

    # Test that the head was not changed and kept unchanged by CleanState
    assert vcs.get_minor_head(vcs_type, vcs_path) == head
    # Assert that save state is not used if the dir is not dirty:w
    assert not vcs.is_dirty(vcs_type, vcs_path) and not vcs.save_state(vcs_type, vcs_path)[0]

    # Test saving detached head state
    vcs.checkout(vcs_type, vcs_path, minor_versions[1])
    saved, _ = vcs.save_state(vcs_type, vcs_path)
    assert not saved
