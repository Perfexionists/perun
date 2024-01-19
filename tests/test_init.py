"""Basic tests for 'perun init' command.

Tests whether basic initialization, and re-initializations work, whether exceptions are fired,
when working within wrong scopes, how does perun copes with existing perun directories, etc.
"""

import os

import distutils.spawn as spawn
import git
import pytest

import perun.logic.commands as commands
from perun.utils.common import common_kit
from perun.utils.exceptions import UnsupportedModuleException


def assert_perun_successfully_init_at(path):
    """Asserts that the perun was successfully initialized at the given path

    Arguments:
        path(str): path
    """
    perun_dir = os.path.join(path, ".perun")
    perun_content = os.listdir(perun_dir)
    assert "cache" in perun_content
    assert "objects" in perun_content
    assert "jobs" in perun_content
    assert "logs" in perun_content
    assert "stats" in perun_content
    assert "tmp" in perun_content
    assert os.path.exists(os.path.join(perun_dir, "local.yml"))
    assert len(perun_content) == 7


def assert_git_successfully_init_at(path, is_bare=False):
    """Asserts that the git was sucessfully initialized at the given path

    Arguments:
        path(str): path to the source of the git directory
    """
    git_dir = os.path.join(path, "" if is_bare else ".git")
    git_content = os.listdir(git_dir)
    assert len(git_content) == 8
    assert "branches" in git_content
    assert "hooks" in git_content
    assert "info" in git_content
    assert "objects" in git_content
    assert "refs" in git_content
    assert "config" in git_content
    assert "description" in git_content
    assert "HEAD" in git_content


@pytest.mark.usefixtures("cleandir")
def test_no_params():
    """Test calling 'perun init', which inits PCS without VCS

    Expects to correctly create a directory .perun with basic contents
    """
    pcs_path = os.getcwd()

    commands.init(pcs_path, **{"vcs_type": None, "vcs_path": None, "vcs_params": None})

    dir_content = os.listdir(pcs_path)

    # Assert that the directory was correctly initialized
    assert_perun_successfully_init_at(pcs_path)
    assert ".perun" in dir_content
    assert len(dir_content) == 1


@pytest.mark.usefixtures("cleandir")
def test_no_params_exists_pcs_in_same_dir(capsys):
    """Test calling 'perun init' in directory, where Perun already was initialized

    Expecting to "warn" the user, that there was already existing PCS and so the repo was
    reinitialized. In case there were some parts of perun deleted, they will be created again.
    """
    pcs_path = os.getcwd()

    commands.init(pcs_path, **{"vcs_type": None, "vcs_path": None, "vcs_params": None})

    # Assert that the directory was correctly initialized
    assert_perun_successfully_init_at(pcs_path)

    # Flush the current buffer
    capsys.readouterr()

    # Remove the jobs folder to simulate "malforming"
    os.rmdir(os.path.join(pcs_path, ".perun", "jobs"))

    commands.init(pcs_path, **{"vcs_type": None, "vcs_path": None, "vcs_params": None})

    # Asser that the directory is still correctly initialized even after the malfunction
    assert_perun_successfully_init_at(pcs_path)

    # Check if user was warned, that at the given path, the perun pcs was reinitialized
    out, _ = capsys.readouterr()
    assert f"Reinitialized existing Perun repository in {pcs_path}" in out


@pytest.mark.usefixtures("cleandir")
def test_no_params_exists_pcs_in_parent(capsys):
    """Test calling 'perun init' with initialied pcs in parent directory

    Expecting to "warn" the user, that there is some super perun, but will create the perun
    as expected, with everything initialized.
    """
    pcs_path = os.getcwd()

    commands.init(pcs_path, **{"vcs_type": None, "vcs_path": None, "vcs_params": None})
    capsys.readouterr()

    # Assert that the directory was correctly initialized
    assert_perun_successfully_init_at(pcs_path)
    sub_pcs_path = os.path.join(pcs_path, "subdir")
    os.mkdir(sub_pcs_path)

    # Create pcs in sub dir, assert that it was correctly initialized
    commands.init(sub_pcs_path, **{"vcs_type": None, "vcs_path": None, "vcs_params": None})
    assert_perun_successfully_init_at(sub_pcs_path)

    # Assert that user was warned, there is a super perun directory
    out, _ = capsys.readouterr()
    assert (
        out.split("\n")[0].strip() == f"warning: There exists super perun directory at {pcs_path}"
    )


@pytest.mark.usefixtures("cleandir")
def test_git():
    """Test calling 'perun init --vcs-type=git', which initializes empty git repository

    Expects creating both perun and git at the same given path.
    """
    pcs_path = os.getcwd()

    commands.init(pcs_path, **{"vcs_type": "git", "vcs_path": None, "vcs_params": None})

    dir_content = os.listdir(pcs_path)

    # Assert that the directories was correctly initialized
    assert_perun_successfully_init_at(pcs_path)
    assert_git_successfully_init_at(pcs_path)
    assert ".perun" in dir_content
    assert ".git" in dir_content
    assert len(dir_content) == 2


@pytest.mark.usefixtures("cleandir")
def test_git_exists_already(capsys):
    """Test calling 'perun init --vcs-type=git', which initializes git, with existing git already

    Expecting warning the user, that the git repository was reinitialized instead of just
    initialized by printing some message
    """
    pcs_path = os.getcwd()

    # Init empty repo at the current path and flush the output
    git.Repo.init(pcs_path, **{})
    capsys.readouterr()
    assert_git_successfully_init_at(pcs_path)

    # Init perun and moreover init the git as well
    commands.init(pcs_path, **{"vcs_type": "git", "vcs_path": None, "vcs_params": None})
    assert_git_successfully_init_at(pcs_path)
    assert_perun_successfully_init_at(pcs_path)

    # Capture the out and check if the message contained "Reinitialized"
    out, _ = capsys.readouterr()
    expected = out.split("\n")[1].strip()
    assert expected == f"Reinitialized existing Git repository in {pcs_path}"


@pytest.mark.usefixtures("cleandir")
def test_git_other_path():
    """Test calling 'perun init --vcs-type=git --vcs-path=path', which initializes in other path

    Fixme: 1) Subdir, 2) completely different dir

    Expecting creating perun at current dir and git at different dir"""
    pcs_path = os.getcwd()
    git_path = os.path.join(pcs_path, "repo")

    # Init perun together with git on different path
    commands.init(pcs_path, **{"vcs_type": "git", "vcs_path": git_path, "vcs_params": None})

    # Assert everything was correctly created
    assert_perun_successfully_init_at(pcs_path)
    assert_git_successfully_init_at(git_path)


@pytest.mark.usefixtures("cleandir")
def test_git_with_params():
    """Test calling 'perun init --vcs-type=git --vcs-params=--bare', which adds more parameters

    Expecting creating a bare repository in the given path and perun normally initialized.
    """
    pcs_path = os.getcwd()
    git_path = os.path.join(pcs_path, "repo")

    # Init perun together with git on different path
    commands.init(
        pcs_path,
        **{"vcs_type": "git", "vcs_path": git_path, "vcs_params": {"bare": True}},
    )

    # Assert everything was correctly created
    assert_perun_successfully_init_at(pcs_path)
    assert_git_successfully_init_at(git_path, is_bare=True)

    # Assert that the directory is bare
    assert git.Repo(git_path).bare


@pytest.mark.usefixtures("cleandir")
def test_git_with_bogus_params():
    """Test calling 'perun init --vcs-type=git --vcs-params=bogus', i.e. with wrong params

    Expecting an error while initializing the git directory. Nothing should be created.
    """
    pcs_path = os.getcwd()
    git_path = os.path.join(pcs_path, "repo")

    # Init perun together with git on different path
    with pytest.raises(SystemExit):
        commands.init(
            pcs_path,
            **{"vcs_type": "git", "vcs_path": git_path, "vcs_params": {"bare": "no"}},
        )


@pytest.mark.usefixtures("cleandir")
def test_unsupported_vcs():
    """Test calling 'perun init --vcs-type=unsupported', with some non-implemented vcs

    Expecting an exception while calling the init. Nothing should be created.
    """
    pcs_path = os.getcwd()

    # Try to call init with inexistent version control system type
    with pytest.raises(UnsupportedModuleException) as exc:
        commands.init(pcs_path, **{"vcs_type": "bogusvcs", "vcs_path": None, "vcs_params": None})
    assert "'bogusvcs' is not supported" in str(exc.value)

    dir_content = os.listdir(pcs_path)
    assert ".git" not in dir_content


@pytest.mark.usefixtures("cleandir")
def test_failed_init_vcs(monkeypatch, capsys):
    """Test calling the init, while the vcs.init fails

    Excepts error and system exit
    """
    pcs_path = os.getcwd()

    def failing_init(*_):
        """Errorous init, that returns false"""
        return False

    monkeypatch.setattr("perun.vcs.init", failing_init)

    # Try to call init, when patched init fails
    with pytest.raises(SystemExit):
        commands.init(pcs_path, **{"vcs_type": "git", "vcs_path": None, "vcs_params": None})

    _, err = capsys.readouterr()
    assert "Could not initialize empty git repository" in err


@pytest.mark.usefixtures("cleandir")
def test_developer_config():
    """Test initialization of developer configuration"""
    pcs_path = os.getcwd()
    git_path = os.path.join(pcs_path, "repo")

    # Init perun together with git on different path
    commands.init(
        pcs_path,
        configuration_template="developer",
        **{"vcs_type": "git", "vcs_path": git_path, "vcs_params": {"bare": True}},
    )

    # Assert everything was correctly created
    assert_perun_successfully_init_at(pcs_path)
    assert_git_successfully_init_at(git_path, is_bare=True)

    # Assert that the directory is bare
    assert git.Repo(git_path).bare

    with open(os.path.join(pcs_path, ".perun", "local.yml"), "r") as local_config:
        contents = "".join(local_config.readlines())
        assert "make" in contents
        assert "collect_before_check" in contents


@pytest.mark.usefixtures("cleandir")
def test_user_config():
    """Test initialization of user configuration"""
    pcs_path = os.getcwd()
    git_path = os.path.join(pcs_path, "repo")

    # Prepare the user config with some helper data
    main_build = os.path.join(pcs_path, "build")
    main_workload = os.path.join(pcs_path, "workload")
    common_kit.touch_dir(main_build)
    common_kit.touch_dir(main_workload)
    os.symlink(spawn.find_executable("cat"), os.path.join(main_build, "lecat"))
    common_kit.touch_file(os.path.join(main_workload, "file1"))

    subproject_path = os.path.join(pcs_path, "subproject")
    sub_build = os.path.join(subproject_path, "_build")
    sub_workload = os.path.join(subproject_path, "_workload")
    bogus_workload = os.path.join(subproject_path, "werklerd")
    common_kit.touch_dir(subproject_path)
    common_kit.touch_dir(sub_build)
    common_kit.touch_dir(sub_workload)
    common_kit.touch_dir(bogus_workload)
    os.symlink(spawn.find_executable("wc"), os.path.join(sub_build, "lewc"))
    common_kit.touch_file(os.path.join(sub_workload, "file2"))
    common_kit.touch_file(os.path.join(bogus_workload, "file3"))

    # Init perun together with git on different path
    commands.init(
        pcs_path,
        configuration_template="user",
        **{"vcs_type": "git", "vcs_path": git_path, "vcs_params": {"bare": True}},
    )

    # Assert everything was correctly created
    assert_perun_successfully_init_at(pcs_path)
    assert_git_successfully_init_at(git_path, is_bare=True)

    # Assert that the directory is bare
    assert git.Repo(git_path).bare

    with open(os.path.join(pcs_path, ".perun", "local.yml"), "r") as local_config:
        contents = "".join(local_config.readlines())
        assert "make" in contents
        assert "collect_before_check" in contents
        assert "time" in contents
        assert "cmds" in contents
        assert "lewc" in contents
        assert "lecat" in contents
        assert "workloads" in contents
        assert "file1" in contents
        assert "file2" in contents
        assert "file3" not in contents
