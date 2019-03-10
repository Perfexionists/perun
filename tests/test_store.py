import os
import pytest

import perun.logic.store as store
import perun.logic.index as index
import perun.utils.exceptions as exceptions
import perun.utils.timestamps as timestamps

__author__ = 'Tomas Fiedor'


@pytest.mark.usefixtures('cleandir')
def test_malformed_indexes(tmpdir, monkeypatch):
    """Tests malformed indexes"""
    index_file = os.path.join(str(tmpdir), "index")
    index.touch_index(index_file)

    monkeypatch.setattr('perun.logic.index.INDEX_VERSION', index.INDEX_VERSION + 1)
    with open(index_file, 'rb') as index_handle:
        with pytest.raises(exceptions.MalformedIndexFileException):
            index.print_index_from_handle(index_handle)

    index_file = os.path.join(str(tmpdir), "index2")
    index.touch_index(index_file)
    monkeypatch.setattr('perun.logic.index.INDEX_MAGIC_PREFIX', index.INDEX_MAGIC_PREFIX.upper())
    with open(index_file, 'rb') as index_handle:
        with pytest.raises(exceptions.MalformedIndexFileException):
            index.print_index_from_handle(index_handle)


@pytest.mark.usefixtures('cleandir')
def test_correct_index(tmpdir):
    """Test correct working with index"""
    index_file = os.path.join(str(tmpdir), "index")
    index.touch_index(index_file)
    index.print_index(index_file)

@pytest.mark.usefixtures('cleandir')
def test_versions(tmpdir, monkeypatch):
    """Test correct working with index"""
    monkeypatch.setattr('perun.logic.index.INDEX_VERSION', index.IndexVersion.SlowLorris.value)
    pool_path = os.path.join(os.path.split(__file__)[0], 'degradation_profiles')
    profile_name = os.path.join(pool_path, 'linear_base.perf')
    profile = store.load_profile_from_file(profile_name, True)

    index_file = os.path.join(str(tmpdir), "index")
    index.touch_index(index_file)

    st = timestamps.timestamp_to_str(os.stat(profile_name).st_mtime)
    sha = store.compute_checksum("Wow, such checksum".encode('utf-8'))
    basic_entry = index.BasicIndexEntry(st, sha, profile_name, index.INDEX_ENTRIES_START_OFFSET)
    index.write_entry_to_index(index_file, basic_entry)

    with pytest.raises(SystemExit):
        with open(index_file, 'rb+') as index_handle:
            index.BasicIndexEntry.read_from(index_handle, index.IndexVersion.FastSloth)

    with open(index_file, 'rb+') as index_handle:
        index_handle.seek(index.INDEX_ENTRIES_START_OFFSET)
        entry = index.BasicIndexEntry.read_from(index_handle, index.IndexVersion.SlowLorris)
        assert entry == basic_entry

    # Test version 2 index
    monkeypatch.setattr('perun.logic.index.INDEX_VERSION', index.IndexVersion.FastSloth.value)
    index_v2_file = os.path.join(str(tmpdir), "index_v2")
    index.touch_index(index_v2_file)
    extended_entry = index.ExtendedIndexEntry(st, sha, profile_name, index.INDEX_ENTRIES_START_OFFSET, profile)
    index.write_entry_to_index(index_v2_file, extended_entry)
    with open(index_v2_file, 'rb+') as index_handle:
        index_handle.seek(index.INDEX_ENTRIES_START_OFFSET)
        stored = index.ExtendedIndexEntry.read_from(index_handle, index.IndexVersion.FastSloth)
        assert stored == extended_entry
    index.print_index(index_v2_file)

    # Test FastSloth with SlowLorris
    monkeypatch.setattr('perun.logic.index.INDEX_VERSION', index.IndexVersion.FastSloth.value)
    monkeypatch.setattr('perun.logic.pcs.get_object_directory', lambda: '')
    monkeypatch.setattr('perun.logic.store.load_profile_from_file', lambda *_, **__: profile)
    index_v1_2_file = os.path.join(str(tmpdir), "index_v1_2")
    index.touch_index(index_v1_2_file)
    index.write_entry_to_index(index_v1_2_file, basic_entry)
    with open(index_v1_2_file, 'rb+') as index_handle:
        index_handle.seek(index.INDEX_ENTRIES_START_OFFSET)
        stored = index.ExtendedIndexEntry.read_from(index_handle, index.IndexVersion.SlowLorris)
        assert stored.__dict__ == extended_entry.__dict__


@pytest.mark.usefixtures('cleandir')
def test_helpers(tmpdir):
    index_file = os.path.join(str(tmpdir), "index")
    index.touch_index(index_file)

    with open(index_file, 'rb+') as index_handle:
        store.write_string_to_handle(index_handle, "Hello Dolly!")
        index_handle.seek(0)
        stored_string = store.read_string_from_handle(index_handle)
        assert stored_string == "Hello Dolly!"

        current_position = index_handle.tell()
        store.write_list_to_handle(index_handle, ['hello', 'dolly'])
        index_handle.seek(current_position)
        stored_list = store.read_list_from_handle(index_handle)
        assert stored_list == ['hello', 'dolly']
