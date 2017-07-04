"""Shared fixtures for the testing of functionality of Perun commands."""

import curses
import os
import shutil
import subprocess
import tempfile

import git
import pytest

import perun.core.logic.commands as commands
import perun.core.logic.pcs as pcs
import perun.core.logic.store as store
import perun.core.profile.factory as perun_profile
import perun.core.vcs as vcs
import perun.utils.streams as streams

__author__ = 'Tomas Fiedor'


class Helpers(object):
    """
    Helper class with various static functions for helping with profiles
    """
    @staticmethod
    def list_contents_on_path(path):
        """Helper function for listing the contents of the path

        Arguments:
            path(str): path to the director which we will list
        """
        for root, dirs, files in os.walk(path):
            for file_on_path in files:
                print("file: ", os.path.join(root, file_on_path))
            for dir_on_path in dirs:
                print("dirs: ", os.path.join(root, dir_on_path))

    @staticmethod
    def count_contents_on_path(path):
        """Helper function for counting the contents of the path

        Arguments:
            path(str): path to the director which we will list

        Returns:
            (int, int): (file number, dir number) on path
        """
        file_number = 0
        dir_number = 0
        for _, dirs, files in os.walk(path):
            for _ in files:
                file_number += 1
            for _ in dirs:
                dir_number += 1
        return file_number, dir_number

    @staticmethod
    def open_index(pcs_path, minor_version):
        """Helper function for opening handle of the index

        This encapsulates obtaining the full path to the given index

        Arguments:
            pcs_path(str): path to the pcs
            minor_version(str): sha minor version representation
        """
        assert store.is_sha1(minor_version)
        object_dir_path = os.path.join(pcs_path, 'objects')

        _, minor_version_index = store.split_object_name(object_dir_path, minor_version)
        return open(minor_version_index, 'rb+')

    @staticmethod
    def exists_profile_in_index_such_that(index_handle, pred):
        """Helper assert to check, if there exists any profile in index such that pred holds.

        Arguments:
            index_handle(file): handle for the index
            pred(lambda): predicate over the index entry
        """
        for entry in store.walk_index(index_handle):
            if pred(entry):
                return True
        return False

    @staticmethod
    def prepare_profile(perun, profile, origin):
        """
        Arguments:
            pcs(PCS): perun control system wrapper
            profile(str): name of the profile that is going to be stored in pending jobs
            origin(str): origin minor version for the given profile
        """
        # Copy to jobs and prepare origin for the current version
        dest_dir = perun.get_job_directory()
        shutil.copy2(profile, dest_dir)

        # Prepare origin for the current version
        copied_filename = os.path.join(dest_dir, os.path.split(profile)[-1])
        copied_profile = perun_profile.load_profile_from_file(copied_filename, is_raw_profile=True)
        copied_profile['origin'] = origin
        perun_profile.store_profile_at(copied_profile, copied_filename)
        shutil.copystat(profile, copied_filename)
        return copied_filename

    @staticmethod
    def assert_invalid_cli_choice(cli_result, choice, file=None):
        """Checks, that click correctly ended as invalid choice

        Arguments:
            cli_result(click.Result): result of the commandline interface
            choice(str): choice that we tried
            file(str): name of the file that should not be created (optional)
        """
        assert cli_result.exit_code == 2
        assert "invalid choice: {}".format(choice) in cli_result.output
        if file:
            assert file not in os.listdir(os.getcwd())

    @staticmethod
    def assert_invalid_param_choice(cli_result, choice, file=None):
        """Checks that click correctly ended with invalid choice and 1 return code
        Arguments:
            cli_result(click.Result): result of the commandline interface
            choice(str): choice that we tried
            file(str): name of the file that should not be created (optional)
        """
        print(cli_result.output)
        assert cli_result.exit_code == 1
        assert "Invalid value '{}'".format(choice) in cli_result.output
        if file:
            assert file not in os.listdir(os.getcwd())


@pytest.fixture(scope="session")
def helpers():
    """
    Returns:
        Helpers: object with helpers functions
    """
    return Helpers()


@pytest.fixture(scope="session")
def memory_collect_job():
    """
    Returns:
        tuple: ('bin', '', [''], 'memory', [])
    """
    # First compile the stuff, so we know it will work
    script_dir = os.path.split(__file__)[0]
    target_dir = os.path.join(script_dir, 'collect_memory')
    target_src_path = os.path.join(target_dir, 'memory_collect_test.c')

    # Compile the testing stuff with debugging information set
    subprocess.check_output(
        ['gcc', '--std=c99', '-g', target_src_path, '-o', 'mct'], cwd=target_dir
    )
    target_bin_path = os.path.join(target_dir, 'mct')
    assert 'mct' in list(os.listdir(target_dir))

    return [target_bin_path], '', [''], ['memory'], []


@pytest.fixture(scope="session")
def memory_collect_no_debug_job():
    """
    Returns:
        tuple: ('bin', '', [''], 'memory', [])
    """
    # First compile the stuff, so we know it will work
    script_dir = os.path.split(__file__)[0]
    target_dir = os.path.join(script_dir, 'collect_memory')
    target_src_path = os.path.join(target_dir, 'memory_collect_test.c')

    # Compile the testing stuff with debugging information set
    subprocess.check_output(
        ['gcc', '--std=c99', target_src_path, '-o', 'mct-no-dbg'], cwd=target_dir
    )
    target_bin_path = os.path.join(target_dir, 'mct-no-dbg')
    assert 'mct-no-dbg' in list(os.listdir(target_dir))

    return [target_bin_path], '', [''], ['memory'], []


@pytest.fixture(scope="session")
def complexity_collect_job():
    """


    Returns:
        tuple: 'bin', '', [''], 'memory', [], {}
    """
    # Load the configuration from the job file
    script_dir = os.path.split(__file__)[0]
    source_dir = os.path.join(script_dir, 'collect_complexity')
    target_dir = os.path.join(source_dir, 'target')
    job_config_file = os.path.join(source_dir, 'job.yml')
    job_config = streams.safely_load_yaml_from_file(job_config_file)

    # Change the target dir to this location
    assert 'target_dir' in job_config.keys()
    job_config['target_dir'] = target_dir

    return [target_dir], '', [''], ['complexity'], [], {'collector_params': {
        'complexity': job_config
    }}


def get_all_profiles():
    """Helper generator for generating stream of profiles"""
    pool_path = os.path.join(os.path.split(__file__)[0], "to_add_profiles")
    profile_filenames = os.listdir(pool_path)
    profiles = [os.path.join(pool_path, filename) for filename in profile_filenames]
    profiles.sort()
    for profile in profiles:
        yield profile


@pytest.fixture(scope="session")
def valid_profile_pool():
    """
    Returns:
        list: dictionary with profiles that are not assigned and can be distributed
    """
    yield list(filter(lambda p: 'err' not in p, get_all_profiles()))


@pytest.fixture(scope="session")
def error_profile_pool():
    """
    Returns:
        list: list with profiles that contains some kind of error
    """
    yield list(filter(lambda p: 'err' in p, get_all_profiles()))


@pytest.fixture(scope="session")
def stored_profile_pool():
    """
    Returns:
        list: list of stored profiles in the pcs_full
    """
    prof_dirpath = os.path.join(os.path.split(__file__)[0], "full_profiles")
    profiles = [os.path.join(prof_dirpath, prof_file) for prof_file in os.listdir(prof_dirpath)]
    assert len(profiles) == 3
    return profiles


def get_loaded_profiles(profile_type):
    """
    Arguments:
        profile_type(str): type of the profile we are looking for

    Returns:
        generator: stream of profiles of the given type
    """
    for valid_profile in filter(lambda p: 'err' not in p, get_all_profiles()):
        loaded_profile = perun_profile.load_profile_from_file(valid_profile, is_raw_profile=True)
        if loaded_profile['header']['type'] == profile_type:
            yield loaded_profile


@pytest.fixture(scope="function")
def memory_profiles():
    """
    Returns:
        generator: generator of fully loaded memory profiles as dictionaries
    """
    yield get_loaded_profiles('memory')


@pytest.fixture(scope="function")
def pcs_full():
    """
    Returns:
        PCS: object with performance control system, initialized with some files and stuff
    """
    # Change working dir into the temporary directory
    profiles = stored_profile_pool()
    pcs_path = tempfile.mkdtemp()
    os.chdir(pcs_path)
    commands.init_perun_at(pcs_path, False, False, {'vcs': {'url': '../', 'type': 'git'}})

    # Construct the PCS object
    pcs_obj = pcs.PCS(pcs_path)

    # Initialize git
    vcs.init('git', pcs_path, {})

    # Populate repo with commits
    repo = git.Repo(pcs_path)

    # Create first commit
    file1 = os.path.join(pcs_path, "file1")
    store.touch_file(file1)
    repo.index.add([file1])
    root = repo.index.commit("root")

    # Create second commit
    file2 = os.path.join(pcs_path, "file2")
    store.touch_file(file2)
    repo.index.add([file2])
    current_head = repo.index.commit("second commit")

    # Populate PCS with profiles
    root_profile = Helpers.prepare_profile(pcs_obj, profiles[0], str(root))
    commands.add(root_profile, str(root))
    chead_profile1 = Helpers.prepare_profile(pcs_obj, profiles[1], str(current_head))
    chead_profile2 = Helpers.prepare_profile(pcs_obj, profiles[2], str(current_head))
    commands.add(chead_profile1, str(current_head))
    commands.add(chead_profile2, str(current_head))

    # Assert that we have five blobs: 2 for commits and 3 for profiles
    pcs_object_dir = os.path.join(pcs_path, ".perun", "objects")
    number_of_perun_objects = sum(
        len(os.listdir(os.path.join(pcs_object_dir, sub))) for sub in os.listdir(pcs_object_dir)
    )
    assert number_of_perun_objects == 5

    yield pcs_obj

    # clean up the directory
    shutil.rmtree(pcs_path)


@pytest.fixture(scope="function")
def pcs_with_empty_git():
    """
    Returns:
        PCS: object with performance control system initialized with empty git repository
    """
    # Change working dir into the temporary directory
    pcs_path = tempfile.mkdtemp()
    os.chdir(pcs_path)
    commands.init_perun_at(pcs_path, False, False, {'vcs': {'url': '../', 'type': 'git'}})

    # Construct the PCS object
    pcs_obj = pcs.PCS(pcs_path)

    # Initialize git
    vcs.init('git', pcs_path, {})

    yield pcs_obj

    # clean up the directory
    shutil.rmtree(pcs_path)


@pytest.fixture(scope="function")
def pcs_without_vcs():
    """
    Returns:
        PCS: object with performance control system initialized without vcs at all
    """
    # Change working dir into the temporary directory
    pcs_path = tempfile.mkdtemp()
    os.chdir(pcs_path)
    commands.init_perun_at(pcs_path, False, False, {'vcs': {'url': '../', 'type': 'pvcs'}})

    # Construct the PCS object
    pcs_obj = pcs.PCS(pcs_path)

    yield pcs_obj

    # clean up the directory
    shutil.rmtree(pcs_path)


@pytest.fixture(scope="function")
def pcs_with_git_in_separate_dir():
    """
    Returns:
        PCS: object with performance control system initialized with git at different directory
    """
    # Fixme: TODO Implement this
    assert False


@pytest.fixture(scope="function")
def cleandir():
    """Runs the test in the clean new dir, which is purged afterwards"""
    temp_path = tempfile.mkdtemp()
    os.chdir(temp_path)
    yield
    shutil.rmtree(temp_path)


class MockCursesWindow(object):
    """Mock object for testing window in the heap"""
    def __init__(self, lines, cols):
        """Initializes the mock object with line height and cols width"""
        self.lines = lines
        self.cols = cols

        # Top left corner
        self.cursor_x = 0
        self.cursor_y = 0

        self.matrix = [[' ']*cols for _ in range(1, lines+1)]

        self.character_stream = iter([
            curses.KEY_RIGHT, curses.KEY_LEFT, ord('4'), ord('6'), ord('8'), ord('5'), ord('h'),
            ord('q'), ord('q')
        ])

    def getch(self):
        """Returns character stream tuned for the testing of the logic"""
        return self.character_stream.__next__()

    def getyx(self):
        """Returns the current cursor position"""
        return self.cursor_y, self.cursor_x

    def getmaxyx(self):
        """Returns the size of the mocked window"""
        return self.lines, self.cols

    def addch(self, y_coord, x_coord, symbol, *_):
        """Displays character at (y, x) coord

        Arguments:
            y_coord(int): y coordinate
            x_coord(int): x coordinate
            symbol(char): symbol displayed at (y, x)
        """
        if 0 <= x_coord < self.cols and 0 <= y_coord < self.lines:
            self.matrix[y_coord][x_coord] = symbol

    def addstr(self, y_coord, x_coord, dstr, *_):
        """Displays string at (y, x) coord

        Arguments:
            y_coord(int): y coordinate
            x_coord(int): x coordinate
            dstr(str): string displayed at (y, x)
        """
        x_coord = x_coord or self.cursor_x
        y_coord = y_coord or self.cursor_y
        str_limit = self.cols - x_coord
        self.addnstr(y_coord, x_coord, dstr, str_limit)

    def addnstr(self, y_coord, x_coord, dstr, str_limit, *_):
        """Displays string at (y, x) coord limited to str_limit

        Arguments:
            y_coord(int): y coordinate
            x_coord(int): x coordinate
            dstr(str): string displayed at (y, x)
            str_limit(int): limit length for dstr to be displayed in matrix
        """
        chars = list(dstr)[:str_limit]
        self.matrix[y_coord][x_coord:(x_coord+len(chars))] = chars

    def hline(self, y_coord, x_coord, symbol, line_len=None, *_):
        """Wrapper for printing the line and massaging the parameters

        Arguments:
            y_coord(int): y coordinate
            x_coord(int): x coordinate
            symbol(char): symbol that is the body of the horizontal line
            line_len(int): length of the line
        """
        if not line_len:
            self._hline(self.cursor_y, self.cursor_x, y_coord, x_coord)
        else:
            self._hline(y_coord, x_coord, symbol, line_len)

    def _hline(self, y_coord, x_coord, symbol, line_len):
        """Core function for printing horizontal line at (y, x) out of symbols

        Arguments:
            y_coord(int): y coordinate
            x_coord(int): x coordinate
            symbol(char): symbol that is the body of the horizontal line
            line_len(int): length of the line
        """
        chstr = symbol*line_len
        self.addnstr(y_coord, x_coord, chstr, line_len)

    def move(self, y_coord, x_coord):
        """Move the cursor to (y, x)

        Arguments:
            y_coord(int): y coordinate
            x_coord(int): x coordinate
        """
        self.cursor_x = x_coord
        self.cursor_y = y_coord

    def clear(self):
        """Clears the matrix"""
        self.matrix = [[' ']*self.cols for _ in range(1, self.lines+1)]

    def clrtobot(self):
        """Clears window from cursor to the bottom right corner"""
        self.matrix[self.cursor_y][self.cursor_x:self.cols] = [' ']*(self.cols-self.cursor_x)
        for line in range(self.cursor_y+1, self.lines):
            self.matrix[line] = [' ']*self.cols

    def refresh(self):
        """Refreshes the window, not needed"""
        pass

    def __str__(self):
        """Returns string representation of the map"""
        top_bar = "="*(self.cols + 2) + "\n"
        return top_bar + "".join(
            "|" + "".join(line) + "|\n" for line in self.matrix
        ) + top_bar


@pytest.fixture(scope="function")
def mock_curses_window():
    """
    Returns:
        MockCursesWindow: mock window of 40 lines and 80 cols
    """
    lines, cols = 40, 80
    return MockCursesWindow(lines, cols)
