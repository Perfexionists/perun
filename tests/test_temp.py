"""Basic tests for testing temporary storage of Perun"""
from __future__ import annotations

# Standard Imports
import json
import os

# Third-Party Imports
import pytest

# Perun Imports
from perun.logic import index, pcs, store, temp
from perun.utils import exceptions


def test_temp_invalid_paths(pcs_with_empty_git):
    """Test various invalid paths for temp operations.

    'temp_path' uses private function that is used in all the public functions thus testing this
    function should be enough as long as change is not made.
    """
    # Test paths that end up out of the tmp/ scope
    with pytest.raises(exceptions.InvalidTempPathException) as exc:
        temp.temp_path("../testtmp")
    assert "is not located in the perun tmp/ directory" in str(exc.value)

    with pytest.raises(exceptions.InvalidTempPathException) as exc:
        temp.temp_path("./inner/../../testtmp")
    assert "is not located in the perun tmp/ directory" in str(exc.value)

    with pytest.raises(exceptions.InvalidTempPathException) as exc:
        temp.temp_path("/tmp/testtmp")
    assert "is not located in the perun tmp/ directory" in str(exc.value)

    with pytest.raises(exceptions.InvalidTempPathException) as exc:
        temp.temp_path(os.path.join(pcs.get_tmp_directory(), "../testtmp"))
    assert "is not located in the perun tmp/ directory" in str(exc.value)


def test_temp_basics(pcs_with_empty_git):
    """Test some basic operations with the temp module such as touching files / dirs, existence
    checks, listing temporary files etc.
    """
    tmp_dir = pcs.get_tmp_directory()

    # Create a directory
    temp.touch_temp_dir("trace/trace_files")
    temp.touch_temp_dir("trace")
    # Check that only the two inner directories really exist
    tmp_content = os.listdir(tmp_dir)
    trace_content = os.listdir(os.path.join(tmp_dir, "trace"))
    assert len(tmp_content) == 1 and tmp_content[0] == "trace"
    assert len(trace_content) == 1 and trace_content[0] == "trace_files"
    assert not os.listdir(os.path.join(tmp_dir, "trace", "trace_files"))
    # Test the existence functions
    assert temp.exists_temp_dir("trace/trace_files")
    assert not temp.exists_temp_dir("trace/another_trace_files")

    # Check that no temporary file exists yet
    assert not temp.list_all_temps()
    # Add two files, one of them protected
    temp.touch_temp_file("trace/trace_files/collect_log")
    temp.touch_temp_file("trace/lock.txt", True)
    # Check that the files are there
    temps = temp.list_all_temps()
    file1 = os.path.join(tmp_dir, "trace/trace_files/collect_log")
    file2 = os.path.join(tmp_dir, "trace/lock.txt")
    assert len(temps) == 2 and file1 in temps and file2 in temps
    # Test the existence function
    assert temp.exists_temp_file("trace/lock.txt")
    assert not temp.exists_temp_file("trace/trace_files/lock2.txt")
    # Test the list with details
    temps = temp.list_all_temps_with_details()
    assert (
        len(temps) == 2
        and (file1, temp.UNPROTECTED, 0) in temps
        and (file2, temp.PROTECTED, 0) in temps
    )
    # Test the list functions with different root
    temps = temp.list_all_temps("trace/trace_files")
    assert len(temps) == 1 and file1 in temps
    temps = temp.list_all_temps_with_details("trace/trace_files")
    assert len(temps) == 1 and (file1, temp.UNPROTECTED, 0) in temps

    # Test the list function on nonexistent root
    with pytest.raises(exceptions.InvalidTempPathException) as exc:
        temp.list_all_temps("trace/invalid/dir")
    assert "does not exist" in str(exc.value)

    # Test the list function on file instead of directory
    with pytest.raises(exceptions.InvalidTempPathException) as exc:
        temp.list_all_temps("trace/lock.txt")
    assert "is not a directory" in str(exc.value)

    # Test the Context Manager
    with temp.TempFile("tmp.file"):
        assert os.path.exists(os.path.join(".", ".perun", "tmp", "tmp.file"))
    assert not os.path.exists(os.path.join(".", ".perun", "tmp", "tmp.file"))


def test_temp_file_operations(pcs_with_empty_git):
    """Test temporary file manipulation such as creating, reading, properties etc."""
    # Create a new temporary file and check it
    lock_file = "trace/lock.txt"
    temp.create_new_temp(lock_file, "Some test data in custom format")
    assert temp.exists_temp_file(lock_file)
    assert temp.get_temp_properties(lock_file) == (False, False, False)
    assert temp.read_temp(lock_file) == "Some test data in custom format"

    # new_temp should not allow overwriting
    with pytest.raises(exceptions.InvalidTempPathException) as exc:
        temp.create_new_temp(lock_file, "Another test data")
    assert "already exists" in str(exc.value)

    # Create new temporary file using store_temp
    collect_file = "trace/files/collect.log"
    temp.store_temp(collect_file, "Some log data")
    assert temp.exists_temp_file(collect_file)
    assert temp.read_temp(collect_file) == "Some log data"

    # store_temp should allow overwriting
    temp.store_temp(collect_file, "Some data for overwrite")
    assert temp.read_temp(collect_file) == "Some data for overwrite"

    # Test the file properties json and compressed
    temp_data = {"id": 0x11EF, "data": {"important": ["values"]}}
    temp.store_temp(collect_file, temp_data, True, False, True)
    # The index should take care of correct formatting and (de)compression
    assert temp.get_temp_properties(collect_file) == (True, False, True)
    assert temp.read_temp(collect_file) == temp_data
    # Test manually the content to ensure the formatting and compression happened
    expected_content = store.pack_content(json.dumps(temp_data, indent=2).encode("utf-8"))
    with open(temp.temp_path(collect_file), "rb") as tmp_handle:
        content = tmp_handle.read()
        assert isinstance(content, (bytes, bytearray))
        assert content == expected_content

    # Manually change the content so that corruption is simulated
    with open(temp.temp_path(collect_file), "w") as tmp_handle:
        # The file is still considered json-formatted and compressed, thus error occurs when reading
        tmp_handle.write("Some uncompressed and not formatted data")
    assert temp.read_temp(collect_file) == {}

    # Reset the corrupted file
    temp.reset_temp(collect_file)
    assert temp.read_temp(collect_file) == ""


def test_temp_file_deletion(pcs_with_empty_git):
    """Test temporary files / directories deletion."""
    # Create some temp files and directories
    temp_data = {"id": 0x11EF, "data": {"important": ["values"]}}
    file_lock = "trace/lock.txt"
    file_collect = "trace/trace_files/collect.log"
    file_records = "trace/trace_files/records.data"
    file_deg_info = "degradation/info.log"
    file_deg_records = "degradation/results/records.deg"
    file_deg_log = "degradation/results/details/degradation.log"
    temp.touch_temp_file(file_lock, protect=True)
    temp.touch_temp_file(file_collect)
    temp.touch_temp_file(file_records)
    temp.touch_temp_file(file_deg_info)
    temp.create_new_temp(file_deg_records, temp_data, json_format=True, protect=True, compress=True)
    temp.store_temp(file_deg_log, "Some log data", json_format=False, protect=False, compress=True)
    # Test correct properties
    assert temp.get_temp_properties(file_lock) == (False, True, False)
    assert temp.get_temp_properties(file_deg_records) == (True, True, True)
    assert temp.get_temp_properties(file_deg_log) == (False, False, True)
    # Test the index content
    _check_index([file_lock, file_deg_records, file_deg_log])

    # Current status:
    #   trace/
    #       lock.txt (P)
    #       trace_files/
    #           collect.log
    #           records.data
    #   degradation/
    #       info.log
    #       results/
    #           records.deg (P)
    #           details/
    #               degradation.log

    # Try to delete nonexistent file
    with pytest.raises(exceptions.InvalidTempPathException) as exc:
        temp.delete_temp_file("some/invalid/file")
    assert "does not exist" in str(exc.value)

    # Try to delete directory with file deletion function
    with pytest.raises(exceptions.InvalidTempPathException) as exc:
        temp.delete_temp_file("trace/trace_files/")
    assert "is not a file" in str(exc.value)

    # Try to delete protected file without force
    with pytest.raises(exceptions.ProtectedTempException) as exc:
        temp.delete_temp_file(file_lock)
    assert "Aborted" in str(exc.value)
    # Check if ignore_protected works
    temp.delete_temp_file(file_lock, ignore_protected=True)
    assert temp.exists_temp_file(file_lock)

    # Try to delete unprotected file
    temp.delete_temp_file(file_collect)
    assert not temp.exists_temp_file(file_collect)

    # Set protected status to a file and try to delete it with force
    temp.set_protected_status(file_records, True)
    assert temp.get_temp_properties(file_records) == (False, True, False)
    temp.delete_temp_file(file_records, force=True)
    assert not temp.exists_temp_file(file_records)

    # Disable protection status and try to delete a file
    temp.set_protected_status(file_lock, False)
    assert temp.get_temp_properties(file_lock) == (False, False, False)
    temp.delete_temp_file(file_lock)
    assert not temp.exists_temp_file(file_lock)

    # The index should have only two files by now
    _check_index([file_deg_records, file_deg_log])

    # Current status:
    #   trace/
    #       trace_files/
    #   degradation/
    #       info.log
    #       results/
    #           records.deg (P)
    #           details/
    #               degradation.log

    # Try to delete all files in nonexistent directory
    with pytest.raises(exceptions.InvalidTempPathException) as exc:
        temp.delete_all_temps("trace/trace/")
    assert "does not exist" in str(exc.value)
    # Try to delete all files in root that is a file
    with pytest.raises(exceptions.InvalidTempPathException) as exc:
        temp.delete_all_temps(file_deg_info)
    assert "not a directory" in str(exc.value)

    # Try to delete all files in empty directory
    temp.delete_all_temps("trace")
    _check_dirs_and_files(
        ["trace", "trace/trace_files"],
        [],
        [file_deg_info, file_deg_records, file_deg_log],
        [],
    )

    # Try to delete all files without ignore_protected and with protected files
    with pytest.raises(exceptions.ProtectedTempException) as exc:
        temp.delete_all_temps("degradation")
    assert "Aborted" in str(exc.value)
    _check_dirs_and_files(
        ["trace", "trace/trace_files"],
        [],
        [file_deg_info, file_deg_records, file_deg_log],
        [],
    )

    # Try to delete all files with ignore_protected and protected files
    temp.delete_all_temps("degradation", ignore_protected=True)
    _check_dirs_and_files(
        ["trace", "trace/trace_files", "degradation/results/details"],
        [],
        [file_deg_records],
        [file_deg_log, file_deg_info],
    )
    # Check the index
    _check_index([file_deg_records])

    # Restore the degradation directory
    temp.touch_temp_file(file_deg_info)
    temp.store_temp(file_deg_log, "Some log data", json_format=False, protect=False, compress=True)

    # Try to use force with ignore_protected
    temp.delete_all_temps("degradation", ignore_protected=True, force=True)
    _check_dirs_and_files(
        ["trace", "trace/trace_files", "degradation/results/details"],
        [],
        [],
        [file_deg_records, file_deg_log, file_deg_info],
    )
    _check_index([])

    # Update the hierarchy so that we can test the deletion of directories
    file_log = "trace/details/trace.log"
    temp.touch_temp_file(file_log, protect=True)
    temp.touch_temp_file(file_deg_info, protect=True)
    temp.store_temp(file_deg_log, "Some log data", json_format=False, protect=False, compress=True)

    # Current status:
    #   trace/
    #       trace_files/
    #       details/
    #           trace.log (P)
    #   degradation/
    #       info.log (P)
    #       results/
    #           details/
    #               degradation.log

    # Try to delete the trace without ignore_protected
    with pytest.raises(exceptions.ProtectedTempException) as exc:
        temp.delete_temp_dir("trace")
    assert "Aborted" in str(exc.value)
    _check_dirs_and_files(["trace/trace_files"], [], [file_log, file_deg_log], [])

    # Try to delete trace with ignore_protected
    temp.delete_temp_dir("trace", ignore_protected=True)
    _check_dirs_and_files([], ["trace/trace_files"], [file_log, file_deg_log], [])

    # Try to delete details with force
    temp.delete_temp_dir("trace/details", force=True)
    _check_dirs_and_files(["trace"], ["trace/details"], [file_deg_log, file_deg_info], [file_log])
    _check_index([file_deg_info, file_deg_log])

    # Try to delete the whole tmp/ with force
    temp.delete_temp_dir(".", force=True)
    tmp_content = os.listdir(pcs.get_tmp_directory())
    assert temp.exists_temp_dir(".") and len(tmp_content) == 1 and ".index" in tmp_content
    _check_index([])

    # Try to corrupt the index to force exception handling
    temp.touch_temp_file(file_lock, protect=True)
    _check_index([file_lock])
    with open(os.path.join(pcs.get_tmp_directory(), ".index"), "w") as index_handle:
        index_handle.write("Some invalid data")
    _check_index([])


def test_temp_sync(pcs_with_empty_git):
    """Test the index synchronization mechanism in the tmp/ directory."""
    # Create some dummy files
    file_lock, file_results = "trace/lock.txt", "degradation/results.data"
    temp.touch_temp_file(file_lock, protect=True)
    temp.create_new_temp(file_results, "Some degradations", True, True, True)
    # Check the index contents
    assert temp.get_temp_properties(file_lock) == (False, True, False)
    assert temp.get_temp_properties(file_results) == (True, True, True)
    _check_index([file_lock, file_results])

    # Now delete the file ignoring the temp module interface
    os.remove(temp.temp_path(file_results))
    assert not os.path.exists(temp.temp_path(file_results))

    # The index should now be in inconsistent state
    assert temp.get_temp_properties(file_results) == (True, True, True)
    _check_index([file_lock, file_results])

    # Perform synchronization, now the file_results record should be deleted
    temp.synchronize_index()
    assert temp.get_temp_properties(file_lock) == (False, True, False)
    assert temp.get_temp_properties(file_results) == (False, False, False)
    _check_index([file_lock])


def _check_index(expected_content):
    """Check if the index file contains exactly the entries in expected_content.

    :param list expected_content: the list of expected entries in the index
    """
    index_content = index.load_custom_index(pcs.get_tmp_index())
    index_keys = list(index_content.keys())
    assert len(index_keys) == len(expected_content)
    for record in expected_content:
        assert temp.temp_path(record) in index_keys


def _check_dirs_and_files(dirs, dirs_del, files, files_del):
    """Check the existence and nonexistence of files and directories.

    :param list dirs: the list of directories that should exist
    :param list dirs_del: the list of directories that should not exist
    :param list files: the list of files that should exist
    :param list files_del: the list of files that should not exist
    :return:
    """
    for d in dirs:
        assert temp.exists_temp_dir(d)
    for d in dirs_del:
        assert not temp.exists_temp_dir(d)
    for f in files:
        assert temp.exists_temp_file(f)
    for f in files_del:
        assert not temp.exists_temp_file(f)
