"""Collection of tests for stats module"""

from __future__ import annotations

# Standard Imports
import os
import pathlib

# Third-Party Imports
import pytest

# Perun Imports
from perun.utils import exceptions
from perun.utils.common import common_kit
from perun.logic import index, pcs, stats, store


def test_stats_filenames(pcs_full):
    """Test the stats file name generator based on a profile name / sha checksum.

    This also tests the various profile identifiers used for profile lookup, such as:
     - tag
     - source name
     - profile SHA
     - profile SHA path (directory/profile)
    """
    # Test stats name generation based on profile source and identified by a tag
    generated_name = stats.build_stats_filename_as_profile_source("0@i", False)
    assert generated_name == "prof-2-complexity-2017-03-20-21-40-42"

    # Test stats name generation with removed timestamps and identified by the source name
    generated_name = stats.build_stats_filename_as_profile_source(
        "prof-3-memory-2017-05-15-15-43-42.perf", True
    )
    assert generated_name == "prof-3-memory"

    # Prepare the git-related values
    _, minor_root = _get_vcs_versions()
    profile_sha = index.get_profile_list_for_minor(pcs.get_object_directory(), minor_root)[
        0
    ].checksum

    # Test sha-based stats name on the root minor version profile identified by the profile-sha
    generated_name = stats.build_stats_filename_as_profile_sha(profile_sha, minor_root)
    assert generated_name == profile_sha

    # Test sha-based stats name on the root minor version profile identified by the sha-path
    sha_path = os.path.join(profile_sha[:2], profile_sha[2:])
    generated_name = stats.build_stats_filename_as_profile_sha(sha_path, minor_root)
    assert generated_name == profile_sha


def test_stats_filename_on_missing_index(pcs_with_root):
    """Test the file name generator when profile index is missing.

    This should not work as the profile index is required to find the profile.
    """
    with pytest.raises(exceptions.IndexNotFoundException) as exc:
        stats.build_stats_filename_as_profile_source("0@i", False)
    assert "was not found" in str(exc.value)


def test_basic_stats_operations(pcs_with_root):
    """Test some basic operations for manipulating the stats file.

    Tested operations are: adding new stat records to a file (and creating it if necessary),
    updating the stats file, obtaining the complete content of a file (or its subset identified by
    an ID) and deletion of specific records in a stats file.
    """
    # Prepare two stats entries
    stats_entry_1 = {
        "some_value": 10,
        "some_list": [1, 2, 3, 4],
        "inner_dict": {"func": 0x20202, "sampling": 12},
    }
    stats_entry_2 = {"value_a": "aaaa", "value_b": "bbbb", "value_c": "cccc"}

    stats_entry_3 = {"simple": "value"}
    entry_2_new = {"value_d": "dddd"}
    entry_3_new = {"simple": "values"}

    # Prepare git values
    minor_head = pcs.vcs().get_minor_head()
    minor_path = os.path.join(minor_head[:2], minor_head[2:])
    expected_stats_file = os.path.join(pcs.get_stats_directory(), minor_path, "custom_stats")

    # Try adding some stats to the file
    stats_file = stats.add_stats("custom_stats", ["entry_1"], [stats_entry_1])
    assert stats_file == expected_stats_file
    _check_objects([(minor_head, ["custom_stats"])], [], [])

    # Try adding another stats to the file
    stats_file = stats.add_stats(
        "custom_stats", ["entry_2", "entry_3"], [stats_entry_2, stats_entry_3]
    )
    assert stats_file == expected_stats_file
    _check_objects([(minor_head, ["custom_stats"])], [], [])

    # Test that the stats file contains the entries
    stats_content = stats.get_stats_of("custom_stats")
    assert (
        stats_content["entry_1"] == stats_entry_1
        and stats_content["entry_2"] == stats_entry_2
        and stats_content["entry_3"]
    ) == stats_entry_3
    stats_content = stats.get_latest("custom_stats")
    assert (
        stats_content["entry_1"] == stats_entry_1
        and stats_content["entry_2"] == stats_entry_2
        and stats_content["entry_3"]
    ) == stats_entry_3

    # Try updating entries 2 and 3 and test that the change has been made
    stats.update_stats("custom_stats", ["entry_2", "entry_3"], [entry_2_new, entry_3_new])
    stats_content = stats.get_stats_of("custom_stats")
    stats_entry_2.update(entry_2_new)
    stats_entry_3.update(entry_3_new)
    assert (
        stats_content["entry_1"] == stats_entry_1
        and stats_content["entry_2"] == stats_entry_2
        and stats_content["entry_3"]
    ) == stats_entry_3
    _check_objects([(minor_head, ["custom_stats"])], [], [])

    # Try extracting some specific ids from the stats file
    stats_content = stats.get_stats_of("custom_stats", ["entry_2"])
    stats_content_2 = stats.get_stats_of("custom_stats", ["entry_1", "entry_3"])
    assert (
        stats_content["entry_2"] == stats_entry_2
        and stats_content_2["entry_1"] == stats_entry_1
        and stats_content_2["entry_3"]
    ) == stats_entry_3

    # Try deleting some specific entries
    stats.delete_stats("custom_stats", ["entry_1"])
    stats_content = stats.get_stats_of("custom_stats")
    assert (
        "entry_1" not in stats_content
        and stats_content["entry_2"] == stats_entry_2
        and stats_content["entry_3"]
    ) == stats_entry_3
    stats.delete_stats("custom_stats", ["entry_2", "entry_3"])
    stats_content = stats.get_stats_of("custom_stats")
    assert not stats_content
    _check_objects([(minor_head, ["custom_stats"])], [], [])

    # Try deleting id that is not in the stats file
    stats.delete_stats("custom_stats", ["made_up_id"])
    stats_content = stats.get_stats_of("custom_stats")
    assert not stats_content
    _check_objects([(minor_head, ["custom_stats"])], [], [])

    # Try update operation on empty stats file
    stats.update_stats("custom_stats", ["entry_new"], [stats_entry_2])
    stats_content = stats.get_stats_of("custom_stats")
    assert stats_content["entry_new"] == stats_entry_2
    _check_objects([(minor_head, ["custom_stats"])], [], [])


def test_stats_lists(pcs_full_no_prof):
    """Tests the list functions (lists of stat versions or stat files).

    The files list is tested first, mainly valid and invalid inputs for the minor version parameter.

    The versions list is tested with various combinations of the parameters that cause the list
    to be filtered or sliced based on the starting point and the number of records.
    """
    # Prepare the git-related values
    minor_head, minor_root, _ = _get_vcs_versions()

    # Create stats files in the root version
    stats.add_stats("root_stats", ["id_1"], [{"value": 10}], minor_root)
    stats.add_stats("root_stats_2", ["id_1"], [{"value": 10}], minor_root)

    # Test that files and version lists work correctly
    root_files = [file_name for file_name, _ in stats.list_stats_for_minor(minor_root)]
    assert len(root_files) == 2 and "root_stats" in root_files and "root_stats_2" in root_files
    head_files = stats.list_stats_for_minor(minor_head)
    assert not head_files
    # Check the actual content of the stats directory
    _check_objects([(minor_root, ["root_stats", "root_stats_2"])], [], [])

    # Add a new stats file to the HEAD and test that it's listed
    stats.add_stats("head_stats", ["id_1"], [{"value": 20}])
    head_files = [file_name for file_name, _ in stats.list_stats_for_minor()]
    assert len(head_files) == 1 and "head_stats" in head_files
    _check_objects(
        [(minor_root, ["root_stats", "root_stats_2"]), (minor_head, ["head_stats"])],
        [],
        [],
    )

    # Test an invalid query for files in a non-existent stats version
    with pytest.raises(exceptions.VersionControlSystemException) as exc:
        stats.list_stats_for_minor("ac34af56")
    assert "minor version 'ac34af56' could not be found" in str(exc.value)

    # Test the different parameters in version list
    stats_versions = stats.list_stat_versions()
    assert [v for v, _ in stats_versions] == [minor_head, minor_root]
    # Test single record queries from specific versions
    stats_versions = stats.list_stat_versions(minor_root, 1)
    assert [v for v, _ in stats_versions] == [minor_root]
    stats_versions = stats.list_stat_versions(minor_head, 1)
    assert [v for v, _ in stats_versions] == [minor_head]
    # Invalid version should start iterating from the newest version in stats
    stats_versions = stats.list_stat_versions("ac34af56", 1)
    assert [v for v, _ in stats_versions] == [minor_head]

    # Test multiple record queries that exceed the number of stats versions
    stats_versions = stats.list_stat_versions(top=10)
    assert [version for version, _ in stats_versions] == [minor_head, minor_root]
    # Test negative top value
    stats_versions = stats.list_stat_versions(top=-1)
    assert [v for v, _ in stats_versions] == [minor_head]

    # Test that the content of the stats directory hasn't changed
    _check_objects(
        [(minor_root, ["root_stats", "root_stats_2"]), (minor_head, ["head_stats"])],
        [],
        [],
    )

    # Test a version query with missing index file, this produce empty result list
    os.remove(pcs.get_stats_index())
    assert len(stats.list_stat_versions()) == 0


def test_stats_files_delete(pcs_full_no_prof):
    """Tests the stats file deletion either in a specific minor version or across all the indexed
    versions while.
    """
    minor_head, minor_middle, minor_root = _get_vcs_versions()

    # Create the stats file and then try to delete it while keeping the directory
    stats.add_stats("head_stats", ["1"], [{"value": 1}])
    _check_objects([(minor_head, ["head_stats"])], [], [])
    stats.delete_stats_file("head_stats", keep_directory=True)
    # Check that the version directory still exists and the file doesn't
    _check_objects([(minor_head, [])], [], [])
    # Try to delete the file again
    with pytest.raises(exceptions.StatsFileNotFoundException) as exc:
        stats.delete_stats_file("head_stats")
    assert "does not exist" in str(exc.value)
    _check_objects([(minor_head, [])], [], [])

    # Test if disabled 'keep_directory' works with multiple files and empty version directory
    stats.add_stats("middle_stats", ["1"], [{"value": 1}], minor_middle)
    stats.add_stats("middle_stats_2", ["2"], [{"value": 2}], minor_middle)
    _check_objects([(minor_head, []), (minor_middle, ["middle_stats", "middle_stats_2"])], [], [])
    stats.delete_stats_file("middle_stats", minor_middle)
    _check_objects([(minor_head, []), (minor_middle, ["middle_stats_2"])], [], [])
    stats.delete_stats_file("middle_stats_2", minor_middle)
    _check_objects([(minor_head, [])], [], [])

    # Test the stats file deletion across multiple versions
    stats.add_stats("custom_stats", ["1"], [{"value": 1}], minor_middle)
    stats.add_stats("middle_stats", ["1"], [{"value": 10}], minor_middle)
    stats.add_stats("custom_stats", ["1"], [{"value": 1}], minor_root)
    _check_objects(
        [
            (minor_head, []),
            (minor_middle, ["custom_stats", "middle_stats"]),
            (minor_root, ["custom_stats"]),
        ],
        [],
        [],
    )
    # The empty minor_head directory should still exist since the file was not present there
    stats.delete_stats_file_across_versions("custom_stats")
    _check_objects([(minor_head, []), (minor_middle, ["middle_stats"])], [], [])

    # Test the same thing just without deleting the empty directories
    stats.add_stats("custom_stats", ["1"], [{"value": 1}], minor_middle)
    stats.add_stats("middle_stats", ["1"], [{"value": 10}], minor_middle)
    stats.add_stats("custom_stats", ["1"], [{"value": 1}], minor_root)
    _check_objects(
        [
            (minor_head, []),
            (minor_middle, ["custom_stats", "middle_stats"]),
            (minor_root, ["custom_stats"]),
        ],
        [],
        [],
    )
    # All the minor version directories should still be there
    stats.delete_stats_file_across_versions("custom_stats", keep_directory=True)
    _check_objects([(minor_head, []), (minor_middle, ["middle_stats"]), (minor_root, [])], [], [])

    # Try to delete a custom file
    custom_f = os.path.join(pcs.get_stats_directory(), minor_head[:2], minor_head[2:], "file.txt")
    common_kit.touch_file(custom_f)
    _check_objects(
        [(minor_head, []), (minor_middle, ["middle_stats"]), (minor_root, [])],
        [],
        [os.path.join(minor_head[:2], minor_head[2:], "file.txt")],
    )
    stats.delete_stats_file(custom_f, minor_head, keep_directory=True)
    _check_objects([(minor_head, []), (minor_middle, ["middle_stats"]), (minor_root, [])], [], [])

    # Try to delete directory instead of a file in a various possible ways
    # Create one new custom directory
    stats_dir = pcs.get_stats_directory()
    custom_dir = os.path.join(minor_middle[:2], minor_middle[2:], "tst")
    os.mkdir(os.path.join(stats_dir, custom_dir))
    _check_objects(
        [(minor_head, []), (minor_middle, ["middle_stats"]), (minor_root, [])],
        [custom_dir],
        [],
    )
    # This should fail since the stats directory will be searched for in the head minor version
    with pytest.raises(exceptions.StatsFileNotFoundException) as exc:
        stats.delete_stats_file(stats_dir)
    assert "does not exist" in str(exc.value)
    # Again, it should not be possible to delete a specific minor version directory
    with pytest.raises(exceptions.StatsFileNotFoundException) as exc:
        stats.delete_stats_file(os.path.join(stats_dir, minor_head[:2], minor_head[2:]))
    assert "does not exist" in str(exc.value)
    # It's possible to specify the correct path to the custom directory, but the delete should fail
    with pytest.raises(OSError) as exc:
        stats.delete_stats_file(custom_dir, minor_middle)
    assert "Is a directory" in str(exc.value) or "Operation not permitted" in str(exc.value)
    # The directory should still be in the file system
    _check_objects(
        [(minor_head, []), (minor_middle, ["middle_stats"]), (minor_root, [])],
        [custom_dir],
        [],
    )


def test_stats_directories_delete(pcs_full_no_prof):
    """Tests the version directories deletion.

    The deletion function parameters allow to delete only contents of the directory and keep the
    resulting empty directory in a stats directory, or attempt to delete only empty directories
    within the supplied directory list.

    Also deletion of a custom files or directories is tested
    """
    minor_head, minor_middle, minor_root = _get_vcs_versions()

    # Prepare some path values
    stats_dir = pcs.get_stats_directory()
    custom_dir = os.path.join(minor_middle[:2], minor_middle[2:], "abcdir")
    custom_root_dir = "root_dir"
    custom_file = os.path.join(minor_root[:2], minor_root[2:], "custom_file")
    custom_root_file = "some_file"

    # Create two empty and one nonempty version directories
    stats.add_stats("custom_stats", ["1"], [{"value": 1}])
    stats.add_stats("middle_stats", ["1"], [{"value": 10}], minor_middle)
    stats.add_stats("custom_stats", ["1"], [{"value": 1}], minor_root)
    stats.delete_stats_file_across_versions("custom_stats", keep_directory=True)
    _check_objects([(minor_head, []), (minor_middle, ["middle_stats"]), (minor_root, [])], [], [])

    # Test the object deletion edge case
    stats._delete_stats_objects(
        [os.path.join(stats_dir, "invalid_dir")],
        [os.path.join(stats_dir, "invalid_file")],
    )

    # Test the directories deletion
    # Both 'only_empty' and 'keep_directories' set to True should do nothing
    stats.delete_version_dirs([minor_head, minor_middle, minor_root], True, True)
    _check_objects([(minor_head, []), (minor_middle, ["middle_stats"]), (minor_root, [])], [], [])
    # Delete only empty directories
    stats.delete_version_dirs([minor_head, minor_middle, minor_root], only_empty=True)
    _check_objects([(minor_middle, ["middle_stats"])], [], [])

    # Keep the version directories now, create empty version directory and custom directory first
    stats.add_stats("custom_stats", ["1"], [{"value": 1}], minor_root)
    stats.delete_stats_file("custom_stats", minor_root, True)
    os.mkdir(os.path.join(stats_dir, custom_dir))
    _check_objects([(minor_middle, ["middle_stats"]), (minor_root, [])], [custom_dir], [])
    # Delete the content of all the version directories
    stats.delete_version_dirs([minor_middle, minor_root], False, keep_directories=True)
    _check_objects([(minor_middle, []), (minor_root, [])], [], [])

    # Test the complete deletion of directories
    # Create two custom empty directories, two custom files and one more version directory
    os.mkdir(os.path.join(stats_dir, custom_dir))
    os.mkdir(os.path.join(stats_dir, custom_root_dir))
    common_kit.touch_file(os.path.join(stats_dir, custom_file))
    common_kit.touch_file(os.path.join(stats_dir, custom_root_file))
    stats.add_stats("custom_stats", ["1"], [{"value": 1}], minor_head)
    stats.add_stats("middle_stats", ["1"], [{"value": 10}], minor_middle)
    _check_objects(
        [
            (minor_head, ["custom_stats"]),
            (minor_middle, ["middle_stats"]),
            (minor_root, []),
        ],
        [custom_dir, custom_root_dir],
        [custom_file, custom_root_file],
    )
    # Fully delete all the version directories, only some custom objects  should be there
    stats.delete_version_dirs([minor_head, minor_middle, minor_root], False)
    _check_objects([], [custom_root_dir], [custom_root_file])

    # Try to delete a file with version directory delete function, nothing should happen
    stats.delete_version_dirs([custom_root_file], False)
    _check_objects([], [custom_root_dir], [custom_root_file])
    # Try to delete another custom file within version directory
    stats.add_stats("custom_stats", ["1"], [{"value": 1}], minor_root)
    stats.delete_stats_file("custom_stats", minor_root, keep_directory=True)
    common_kit.touch_file(os.path.join(stats_dir, custom_file))
    _check_objects([(minor_root, [])], [custom_root_dir], [custom_root_file, custom_file])
    stats.delete_version_dirs([custom_file], False)
    _check_objects([(minor_root, [])], [custom_root_dir], [custom_root_file, custom_file])

    # Try to delete a non-existent version directory, nothing should happen
    stats.delete_version_dirs([minor_head], False)
    _check_objects([(minor_root, [])], [custom_root_dir], [custom_root_file, custom_file])

    # Try to delete a custom directory
    stats.delete_version_dirs([custom_root_dir], False)
    _check_objects([(minor_root, [])], [custom_root_dir], [custom_root_file, custom_file])
    # Try some custom directory in a version directory, nothing should happen
    stats.add_stats("custom_stats", ["1"], [{"value": 1}], minor_middle)
    stats.delete_stats_file("custom_stats", minor_middle, keep_directory=True)
    os.mkdir(os.path.join(stats_dir, custom_dir))
    _check_objects(
        [(minor_root, []), (minor_middle, [])],
        [custom_root_dir, custom_dir],
        [custom_root_file, custom_file],
    )
    stats.delete_version_dirs([custom_dir], False)
    _check_objects(
        [(minor_root, []), (minor_middle, [])],
        [custom_root_dir, custom_dir],
        [custom_root_file, custom_file],
    )

    # Check that the same prefix (first SHA byte) directories deletion works correctly
    # Create new custom version directory that behaves like a regular one
    fake_version_parts = (
        minor_root[:2],
        minor_head[2:] if minor_head[2:] != minor_root[2:] else minor_middle[2:],
    )
    fake_version = "".join(fake_version_parts)
    os.mkdir(os.path.join(stats_dir, fake_version_parts[0], fake_version_parts[1]))
    stats._add_versions_to_index([(fake_version, "1999-12-31 23:59:59")])
    _check_objects(
        [(minor_root, []), (minor_middle, []), (fake_version, [])],
        [custom_root_dir, custom_dir],
        [custom_root_file, custom_file],
    )
    # The lower level directory (SHA byte) should still be there with the second version
    stats.delete_version_dirs([fake_version], False)
    _check_objects(
        [(minor_root, []), (minor_middle, [])],
        [custom_root_dir, custom_dir],
        [custom_root_file, custom_file],
    )
    stats.delete_version_dirs([minor_root], False)
    # Now the lower level directory should be also deleted
    _check_objects([(minor_middle, [])], [custom_root_dir, custom_dir], [custom_root_file])


def test_stats_sync(pcs_full_no_prof):
    """Tests the stats synchronization, i.e. the synchronization of the internal state represented
    by the '.index' file.

    Test the behaviour on some custom directories (either manually made version directories or
    completely custom ones) and fake index records.
    """
    minor_head, minor_middle, minor_root = _get_vcs_versions()
    stats_dir = pcs.get_stats_directory()

    head_custom = os.path.join(minor_head[:2], minor_head[2:], "custom_file")
    root_custom = os.path.join(minor_root[:2], minor_root[2:], "custom_file_2")
    stats_custom_dir = os.path.join("lower_custom", "upper_custom")

    # HEAD: head_stats, custom_file
    # MIDDLE: 'empty'
    # ROOT: created manually, custom_file_2
    # lower_custom/upper_custom
    stats.add_stats("head_stats", ["1"], [{"value": 1}])
    stats.add_stats("middle_stats", ["1"], [{"custom": 2}], minor_middle)
    stats.delete_stats_file("middle_stats", minor_middle, True)
    os.makedirs(os.path.join(stats_dir, minor_root[:2], minor_root[2:]))
    os.makedirs(os.path.join(stats_dir, stats_custom_dir))
    common_kit.touch_file(os.path.join(stats_dir, root_custom))
    common_kit.touch_file(os.path.join(stats_dir, head_custom))
    # Add some custom versions that don't have a corresponding directory to the index file
    fake_minor1, fake_minor2 = _fake_checksums(minor_head, 2, [minor_head, minor_root])
    stats._add_versions_to_index(
        [(fake_minor1, "1999-12-31 23:59:59"), (fake_minor2, "2009-01-01 00:00:00")]
    )
    # Check that the directory structure is correct
    _check_objects(
        [(minor_head, ["head_stats", "custom_file"]), (minor_middle, [])],
        [stats_custom_dir],
        [root_custom],
        check_index=False,
    )
    # Check the index content separately because of the fake minor versions
    assert set([v for v, _ in stats.list_stat_versions()]) == {
        minor_head,
        minor_middle,
        fake_minor1,
        fake_minor2,
    }
    # Synchronize the index, now the fake minor versions should be removed and minor root indexed
    stats.synchronize_index()
    _check_objects(
        [
            (minor_head, ["head_stats", "custom_file"]),
            (minor_middle, []),
            (minor_root, ["custom_file_2"]),
        ],
        [stats_custom_dir],
        [],
    )


def test_stats_clean(pcs_full_no_prof):
    """Tests the stats cleaning functions. The function should synchronize the internal state and
    remove all the distinguishable custom files and directories, as well as empty version
    directories, within the stats directory (based on the supplied parameters).
    """
    minor_head, minor_middle, minor_root = _get_vcs_versions()
    stats_dir = pcs.get_stats_directory()

    head_custom_file = os.path.join(minor_head[:2], minor_head[2:], "custom_file")
    root_custom_file = os.path.join(minor_root[:2], minor_root[2:], "custom_file_2")
    root_custom_dir = os.path.join(minor_root[:2], minor_root[2:], "custom_dir")
    root_tricky = os.path.join(minor_root[:2], "tricky_custom")
    custom_stats_dir_file = os.path.join("custom_stats_dir", "custom_file_3")
    nested_custom_dir = os.path.join("lower", "upper")

    # The stats directory structure is similar to the sync testing
    # HEAD: head_stats, custom_file
    # MIDDLE: 'empty'
    # ROOT: created manually, custom_file_2, custom_dir
    # ROOT[:2]: tricky_custom
    # custom_stats_dir: custom_file_3
    # lower/upper/: 'empty'
    stats.add_stats("head_stats", ["1"], [{"value": 1}])
    stats.add_stats("middle_stats", ["1"], [{"custom": 2}], minor_middle)
    stats.delete_stats_file("middle_stats", minor_middle, True)
    os.makedirs(os.path.join(stats_dir, minor_root[:2], minor_root[2:], "custom_dir"))
    os.makedirs(os.path.join(stats_dir, nested_custom_dir))
    os.mkdir(os.path.join(stats_dir, "custom_stats_dir"))
    common_kit.touch_file(os.path.join(stats_dir, root_custom_file))
    common_kit.touch_file(os.path.join(stats_dir, head_custom_file))
    common_kit.touch_file(os.path.join(stats_dir, custom_stats_dir_file))
    common_kit.touch_file(os.path.join(stats_dir, root_tricky))
    # Add some custom versions that don't have a corresponding directory to the index file
    fake_minor1, fake_minor2 = _fake_checksums(minor_head, 2, [minor_head, minor_root])
    stats._add_versions_to_index(
        [(fake_minor1, "1999-12-31 23:59:59"), (fake_minor2, "2009-01-01 00:00:00")]
    )
    # Check that the directory structure is correct
    _check_objects(
        [(minor_head, ["head_stats", "custom_file"]), (minor_middle, [])],
        [root_custom_dir, nested_custom_dir],
        [root_custom_file, custom_stats_dir_file, root_tricky],
        check_index=False,
    )
    # Check the index content separately because of the fake minor versions
    assert set([v for v, _ in stats.list_stat_versions()]) == {
        minor_head,
        minor_middle,
        fake_minor1,
        fake_minor2,
    }
    # This combination of parameters should just synchronize the index file
    stats.clean_stats(True, True)
    _check_objects(
        [
            (minor_head, ["head_stats", "custom_file"]),
            (minor_middle, []),
            (minor_root, ["custom_file_2"]),
        ],
        [root_custom_dir, nested_custom_dir],
        [custom_stats_dir_file, root_tricky],
    )
    # Now try to clean the stats directory properly
    stats.clean_stats()
    _check_objects(
        [(minor_head, ["head_stats", "custom_file"]), (minor_root, ["custom_file_2"])],
        [],
        [],
    )

    # Remove the index file and try that again, everything should stay the same
    os.remove(pcs.get_stats_index())
    stats.clean_stats()
    _check_objects(
        [(minor_head, ["head_stats", "custom_file"]), (minor_root, ["custom_file_2"])],
        [],
        [],
    )


def test_stats_clear(pcs_full_no_prof):
    """Tests the stats clear function that attempts to completely clear the contents of the
    stats directory (while either keeping the empty version directories or not).
    """
    minor_head, minor_middle, minor_root = _get_vcs_versions()
    stats_dir = pcs.get_stats_directory()

    head_custom_file = os.path.join(minor_head[:2], minor_head[2:], "custom_file")
    root_custom_file = os.path.join(minor_root[:2], minor_root[2:], "custom_file_2")
    root_custom_dir = os.path.join(minor_root[:2], minor_root[2:], "custom_dir")
    custom_stats_dir_file = os.path.join("custom_stats_dir", "custom_file_3")

    # The same directory structure as in the clean test
    # HEAD: head_stats, custom_file
    # MIDDLE: 'empty'
    # ROOT: created manually, custom_file_2, custom_dir
    # custom_stats_dir: custom_file_3
    stats.add_stats("head_stats", ["1"], [{"value": 1}])
    stats.add_stats("middle_stats", ["1"], [{"custom": 2}], minor_middle)
    stats.delete_stats_file("middle_stats", minor_middle, True)
    os.makedirs(os.path.join(stats_dir, minor_root[:2], minor_root[2:], "custom_dir"))
    os.mkdir(os.path.join(stats_dir, "custom_stats_dir"))
    common_kit.touch_file(os.path.join(stats_dir, root_custom_file))
    common_kit.touch_file(os.path.join(stats_dir, head_custom_file))
    common_kit.touch_file(os.path.join(stats_dir, custom_stats_dir_file))
    # Add some custom versions that don't have a corresponding directory to the index file
    fake_minor1, fake_minor2 = _fake_checksums(minor_head, 2, [minor_head, minor_root])
    stats._add_versions_to_index(
        [(fake_minor1, "1999-12-31 23:59:59"), (fake_minor2, "2009-01-01 00:00:00")]
    )
    # Check that the directory structure is correct
    _check_objects(
        [(minor_head, ["head_stats", "custom_file"]), (minor_middle, [])],
        [root_custom_dir],
        [root_custom_file, custom_stats_dir_file],
        check_index=False,
    )

    # Now try to clear the stats directory, only the version directories should be there
    stats.reset_stats(True)
    _check_objects([(minor_head, []), (minor_middle, []), (minor_root, [])], [], [])
    # Clear the stats completely
    stats.reset_stats()
    _check_objects([], [], [])


def _get_vcs_versions():
    """Obtains the VCS minor versions.

    :return: list of minor version checksums sorted as in the VCS.
    """
    return [v.checksum for v in pcs.vcs().walk_minor_versions(pcs.vcs().get_minor_head())]


def _fake_checksums(source, count, collisions):
    """Generates SHA-1 checksums that represent fake perun objects.

    :param source: a seed value for the generator
    :param count: number of requested checksums
    :param collisions: list of forbidden values for the generated results
    :return: the requested number of SHA-1 checksums
    """
    results = []
    for _ in range(count):
        attempt = store.compute_checksum(source.encode())
        while attempt in collisions or attempt in results:
            attempt = store.compute_checksum(attempt.encode())
        results.append(attempt)
        source = attempt
    return results


def _check_objects(
    versions_with_files,
    custom_empty_dirs,
    custom_files,
    with_index=True,
    check_index=True,
):
    """Checks the directory structure and its contents with the expected one. The actual
    directory contents must be exactly the same as specified by the parameters - no missing or
    excess files or directories.

    :param versions_with_files: list of tuples (version, [files within the version])
    :param custom_empty_dirs: custom empty directories that don't have a record in the index
    :param custom_files: custom files within the stats directory
    :param with_index: flag indicating whether the checked directory has the index file
    :param check_index: checks the supplied versions with the versions listed in the index
    """
    stats_dir = pcs.get_stats_directory() + os.sep
    indexed_versions = [v for v, _ in stats.list_stat_versions()]
    # Test that the versions are actually found in the index
    if check_index:
        assert set(indexed_versions) == set(v for v, _ in versions_with_files)
    stats_objects = _transform_paths(
        versions_with_files, custom_empty_dirs, custom_files, with_index
    )
    stats_iter = os.walk(stats_dir)
    locations_count = 0
    for current, dirs, files in stats_iter:
        current_base = current[len(stats_dir) :]
        locations_count += 1
        assert current_base in stats_objects
        assert set(stats_objects[current_base]["dirs"]) == set(dirs)
        assert set(stats_objects[current_base]["files"]) == set(files)
    assert locations_count == len(stats_objects.keys())


def _transform_paths(versions_with_files, custom_empty_dirs, custom_files, with_index=True):
    """Transforms the supplied versions with files, custom directories and files to a format that
    is suitable for comparison, i.e. dictionary of directories and their contents:

    {'': {'files': [files in the stats directory], 'dirs': [directories in the stats directory]},
    'a4': {'files': [], 'dirs': ['rest_of_the_SHA']},
    'dir1/dir2': {...}}

    :param versions_with_files: list of tuples (version, [files within the version])
    :param custom_empty_dirs: custom empty directories that don't have a record in the index
    :param custom_files: custom files within the stats directory
    :param with_index: flag indicating whether the checked directory has the index file
    :return: the resulting dictionary
    """

    def _process_dir(dir_path, dir_files):
        """Transforms one directory with its files into the requested format and stores it in the
        objects dictionary.

        :param dir_path: relative path (starting from the stats) to the directory
        :param dir_files: list of file names within the directory
        """
        # Split the path into all the components
        path_parts = pathlib.Path(dir_path).parts
        base = ""
        # Add records for each of the component
        for path_dir in path_parts:
            record_dirs = stats_objects.setdefault(base, {"dirs": [], "files": []})["dirs"]
            # Add the new subdirectory as a successor of the previous one
            if path_dir not in record_dirs:
                record_dirs.append(path_dir)
            # Add the new subdirectory as a new base directory
            base = os.path.join(base, path_dir)
            stats_objects.setdefault(base, {"dirs": [], "files": []})
        # Add the files to the last level directory
        stats_objects[dir_path]["files"].extend(dir_files)

    stats_objects = {}

    # Create the initial record representing the base stats directory
    base_record = stats_objects.setdefault("", {"dirs": [], "files": []})
    if with_index:
        base_record["files"].append(".index")

    # Iterate all the versions and create records for directories and files
    for version_dir, files in [(os.path.join(v[:2], v[2:]), fs) for v, fs in versions_with_files]:
        _process_dir(version_dir, files)

    # Iterate all the custom empty directories
    for empty_dir in custom_empty_dirs:
        _process_dir(empty_dir, [])

    for file_path in custom_files:
        file_dir, file_name = os.path.split(file_path)
        _process_dir(file_dir, [file_name])

    return stats_objects
