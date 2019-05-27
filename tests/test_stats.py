import os
import pytest

import perun.logic.stats as stats
import perun.vcs as vcs
import perun.logic.pcs as pcs
import perun.logic.index as index
import perun.utils.exceptions as exception


def test_stats_filenames(pcs_full):
    # Test stats name generation based on profile source and identified by a tag
    generated_name = stats.build_stats_filename_as_profile_source('0@i', False)
    assert generated_name == 'prof-2-2017-03-20-21-40-42'

    # Test stats name generation with removed timestamps and identified by the source name
    generated_name = stats.build_stats_filename_as_profile_source('prof-3-2017-05-15-15-43-42.perf',
                                                                  True)
    assert generated_name == 'prof-3'

    # Prepare the git-related values
    minor_head = vcs.get_minor_head()
    minor_root = list(vcs.walk_minor_versions(minor_head))[1].checksum
    profile_sha = index.get_profile_list_for_minor(pcs.get_object_directory(),
                                                   minor_root)[0].checksum

    # Test sha-based stats name on the root minor version profile identified by the profile-sha
    generated_name = stats.build_stats_filename_as_profile_sha(profile_sha, minor_root)
    assert generated_name == profile_sha

    # Test sha-based stats name on the root minor version profile identified by the sha-path
    sha_path = os.path.join(profile_sha[:2], profile_sha[2:])
    print(sha_path)
    generated_name = stats.build_stats_filename_as_profile_sha(sha_path, minor_root)
    assert generated_name == profile_sha


def test_stats_on_missing_index(pcs_with_git_root_commit):
    with pytest.raises(exception.IndexNotFoundException) as exc:
        stats.build_stats_filename_as_profile_source('0@i', False)
    assert "was not found" in str(exc.value)


def test_basic_stats_operations(pcs_full):
    # Prepare two stats entries
    stats_entry_1 = {'some_value': 10,
                     'some_list': [1, 2, 3, 4],
                     'inner_dict':
                         {'func': 0x20202,
                          'sampling': 12}
                     }
    stats_entry_2 = {'value_a': 'aaaa',
                     'value_b': 'bbbb',
                     'value_c': 'cccc'
                     }

    stats_entry_3 = {'simple': 'value'}
    entry_2_new = {'value_d': 'dddd'}
    entry_3_new = {'simple': 'values'}

    # Prepare git values
    minor_head = vcs.get_minor_head()
    minor_path = os.path.join(minor_head[:2], minor_head[2:])
    expected_stats_file = os.path.join(pcs.get_stats_directory(), minor_path, 'custom_stats')

    # Try adding some stats to the file
    stats_file = stats.add_stats('custom_stats', ['entry_1'], [stats_entry_1])
    assert stats_file == expected_stats_file

    # Try adding another stats to the file
    stats_file = stats.add_stats('custom_stats', ['entry_2', 'entry_3'],
                                 [stats_entry_2, stats_entry_3])
    assert stats_file == expected_stats_file

    # Test that the stats file contains the entries
    stats_content = stats.get_stats_of('custom_stats')
    assert (stats_content['entry_1'] == stats_entry_1 and stats_content['entry_2'] == stats_entry_2
            and stats_content['entry_3']) == stats_entry_3

    # Try updating entries 2 and 3 and test that the change has been made
    stats.update_stats('custom_stats', ['entry_2', 'entry_3'], [entry_2_new, entry_3_new])
    stats_content = stats.get_stats_of('custom_stats')
    stats_entry_2.update(entry_2_new)
    stats_entry_3.update(entry_3_new)
    assert (stats_content['entry_1'] == stats_entry_1
            and stats_content['entry_2'] == stats_entry_2
            and stats_content['entry_3']) == stats_entry_3

    # Try extracting some specific ids from the stats file
    stats_content = stats.get_stats_of('custom_stats', ['entry_2'])
    stats_content_2 = stats.get_stats_of('custom_stats', ['entry_1', 'entry_3'])
    assert (stats_content['entry_2'] == stats_entry_2
            and stats_content_2['entry_1'] == stats_entry_1
            and stats_content_2['entry_3']) == stats_entry_3

    # Try deleting some specific entries
    stats.delete_stats('custom_stats', ['entry_1'])
    stats_content = stats.get_stats_of('custom_stats')
    assert ('entry_1' not in stats_content
            and stats_content['entry_2'] == stats_entry_2
            and stats_content['entry_3']) == stats_entry_3
    stats.delete_stats('custom_stats', ['entry_2', 'entry_3'])
    stats_content = stats.get_stats_of('custom_stats')
    assert not stats_content

    # Try deleting id that is not in the stats file
    stats.delete_stats('custom_stats', ['made_up_id'])
    stats_content = stats.get_stats_of('custom_stats')
    assert not stats_content

    # Try update operation on empty stats file
    stats.update_stats('custom_stats', ['entry_new'], [stats_entry_2])
    stats_content = stats.get_stats_of('custom_stats')
    assert stats_content['entry_new'] == stats_entry_2

    # Try to delete the stats file
    stats.delete_stats_file('custom_stats')
    with pytest.raises(exception.StatsFileNotFoundException) as exc:
        stats.get_stats_of('custom_stats')
    assert 'does not exist' in str(exc.value)

    # Try to delete the stats file again
    with pytest.raises(exception.StatsFileNotFoundException) as exc:
        stats.delete_stats_file('custom_stats')
    assert 'does not exist' in str(exc.value)


def test_stats_in_minor_versions(pcs_full):
    # Prepare the git-related values
    minor_head = vcs.get_minor_head()
    minor_root = list(vcs.walk_minor_versions(minor_head))[1].checksum

    # Create stats files in the root version
    stats.add_stats('root_stats', ['id_1'], [{'value': 10}], minor_root)
    stats.add_stats('root_stats_2', ['id_1'], [{'value': 10}], minor_root)

    root_files = stats.list_stats_for_minor(minor_root)
    root_files = [file_name for file_name, _ in root_files]
    assert len(root_files) == 2 and 'root_stats' in root_files and 'root_stats_2' in root_files
    head_files = stats.list_stats_for_minor(minor_head)
    assert not head_files
