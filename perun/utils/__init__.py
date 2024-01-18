"""Utils contains helper modules, that are not directly dependent on pcs.

Utils contains various helper modules and functions, that can be used in arbitrary projects, and
are not specific for perun pcs, like e.g. helper decorators, logs, etc.
"""
from __future__ import annotations

# Standard Imports
from typing import (
    Iterable,
    Optional,
    Any,
    Callable,
    IO,
    Iterator,
    TYPE_CHECKING,
)
import contextlib
import importlib
import os
import shlex
import shutil
import subprocess

# Third-Party Imports
import magic

# Perun Imports
from .log import error, cprint, cprintln, info
from .exceptions import UnsupportedModuleException, UnsupportedModuleFunctionException

if TYPE_CHECKING:
    import types

    from perun.utils.structs import CollectStatus, PostprocessStatus


def get_build_directories(root: str = ".", template: Optional[list[str]] = None) -> Iterable[str]:
    """Search for build directories in project tree. The build directories can be specified as an
    argument or default templates are used.

    :param str root: directory tree root
    :param list template: list of directory names to search for
    :return: generator object of build directories
    """
    if template is None:
        template = ["build", "_build", "__build"]
    # Find all build directories in directory tree
    root = os.path.join(root, "")
    for current, subdirs, _ in os.walk(root):
        # current directory without root section
        # (to prevent nesting detection if root contains template directory)
        relative = current[len(root) :]
        # Do not traverse hidden directories
        subdirs[:] = [d for d in subdirs if not d[0] == "."]
        for build_dir in template:
            # find directories conforming to the templates without nested ones
            if build_dir in subdirs and not _is_nested(relative, template):
                yield current + build_dir


def _is_nested(path: str, templates: Iterable[str]) -> bool:
    """Check if any element from template is contained within the path - resolve nested template
    directories

    :param str path: path to be resolved
    :param list templates: list of directory names to search for
    :return: bool value representing result
    """
    for template in templates:
        if template in path:
            return True
    return False


def get_directory_elf_executables(
    root: str = ".", only_not_stripped: bool = False
) -> Iterable[str]:
    """Get all ELF executable (stripped or not) from directory tree recursively.

    :param str root: directory tree root
    :param bool only_not_stripped: flag indicating whether collect only binaries not stripped
    :return: generator object of executable binaries as file paths
    """
    root = os.path.join(root, "")
    for current, subdirs, files in os.walk(root):
        # Ignore hidden directories and files
        subdirs[:] = [d for d in subdirs if not d[0] == "."]
        files = [f for f in files if f[0] != "."]
        for file in files:
            # Check if file is executable binary
            filepath = os.path.join(current, file)
            if is_executable_elf(filepath, only_not_stripped):
                yield filepath


def is_executable_elf(file: str, only_not_stripped: bool = False) -> bool:
    """Check if file is executable ELF binary.

    :param str file: the file path
    :param bool only_not_stripped: flag indicating whether also check stripped binaries or not
    :return: bool value representing check result
    """
    # Determine file magic code, we are looking out for ELF files
    f_magic = magic.from_file(file)
    is_elf = f_magic.startswith("ELF") and ("executable" in f_magic or "shared object" in f_magic)
    if is_elf and only_not_stripped:
        return "not stripped" in f_magic
    return is_elf


def get_project_elf_executables(root: str = ".", only_not_stripped: bool = False) -> list[str]:
    """Get all ELF executable files stripped or not from project specified by root
    The function searches for executable files in build directories - if there are any, otherwise
    the whole project directory tree is traversed.

    :param str root: directory tree root
    :param bool only_not_stripped: flag indicating whether collect only binaries not stripped
    :return: list of project executable binaries as file paths
    """
    # Get possible binaries in build directories
    root = os.path.join(root, "")
    build = list(get_build_directories(root))

    # No build directories, find all binaries instead
    if not build:
        build = [root]

    # Gather binaries
    binaries = []
    for build_dir in build:
        binaries += list(get_directory_elf_executables(build_dir, only_not_stripped))

    return binaries


def find_executable(cmd: Optional[str]) -> Optional[str]:
    """Check if the supplied cmd is executable and find its real path
    (i.e. absolute path with resolved symlinks)

    :param str cmd: the command to check

    :return str: resolved command path
    """
    # Ignore invalid paths
    if cmd is None:
        return None

    # shutil.which checks:
    # 1) files with relative / absolute paths specified
    # 2) files accessible through the user PATH environment variable
    # 3) that the file is indeed accessible and executable
    cmd = shutil.which(cmd)
    if cmd is None:
        return None
    # However, we still want to resolve the real path of the file
    return os.path.realpath(cmd)


def run_external_command(cmd_args: list[str], **subprocess_kwargs: Any) -> int:
    """Runs external command with parameters.

    :param list cmd_args: list of external command and its arguments to be run
    :param subprocess_kwargs: additional parameters to the subprocess object
    :return: return value of the external command that was run
    """
    process = subprocess.Popen(cmd_args, **subprocess_kwargs)
    process.wait()
    return process.returncode


@contextlib.contextmanager
def nonblocking_subprocess(
    command: str,
    subprocess_kwargs: dict[str, Any],
    termination: Optional[Callable[..., Any]] = None,
    termination_kwargs: Optional[dict[str, Any]] = None,
) -> Iterator[subprocess.Popen[bytes]]:
    """Runs a non-blocking process in the background using subprocess without shell.

    The process handle is available by using the context manager approach. It is possible to
    supply custom process termination function (and its arguments) that will be used instead of
    the subprocess.terminate().

    :param str command: the command to run in the background
    :param dict subprocess_kwargs: additional arguments for the subprocess Popen
    :param function termination: the custom termination function or None
    :param dict termination_kwargs: the arguments for the termination function
    """
    # Split process and arguments
    parsed_cmd = shlex.split(command)

    # Do not allow shell=True
    if "shell" in subprocess_kwargs:
        del subprocess_kwargs["shell"]

    # Start the process and do not block it (user can tho)
    with subprocess.Popen(parsed_cmd, shell=False, **subprocess_kwargs) as proc:
        try:
            yield proc
        except Exception:
            # Re-raise the encountered exception
            raise
        finally:
            # Don't terminate the process if it has already finished
            if proc.poll() is None:
                # Use the default termination if the termination handler is not set
                if termination is None:
                    proc.terminate()
                else:
                    # Otherwise use the supplied termination function
                    if termination_kwargs is None:
                        termination_kwargs = {}
                    termination(**termination_kwargs)


def run_safely_external_command(
    cmd: str,
    check_results: bool = True,
    quiet: bool = True,
    timeout: Optional[float | int] = None,
    **kwargs: Any,
) -> tuple[bytes, bytes]:
    """Safely runs the piped command, without executing of the shell

    Courtesy of: https://blog.avinetworks.com/tech/python-best-practices

    :param str cmd: string with command that we are executing
    :param bool check_results: check correct command exit code and raise exception in case of fail
    :param bool quiet: if set to False, then it will print the output of the command
    :param int timeout: timeout of the command
    :param dict kwargs: additional args to subprocess call
    :return: returned standard output and error
    :raises subprocess.CalledProcessError: when any of the piped commands fails
    """
    # Split
    unpiped_commands = list(map(str.strip, cmd.split(" | ")))
    cmd_no = len(unpiped_commands)

    # Run the command through pipes
    objects: list[subprocess.Popen[bytes]] = []
    for i in range(cmd_no):
        executed_command = shlex.split(unpiped_commands[i])

        # set streams
        stdin = None if i == 0 else objects[i - 1].stdout
        stderr = subprocess.STDOUT if i < (cmd_no - 1) else subprocess.PIPE

        # run the piped command and close the previous one
        piped_command = subprocess.Popen(
            executed_command,
            shell=False,
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=stderr,
            **kwargs,
        )
        if i != 0:
            # Fixme: we ignore this, as it is tricky to handle
            objects[i - 1].stdout.close()  # type: ignore
        objects.append(piped_command)

    try:
        # communicate with the last piped object
        cmdout, cmderr = objects[-1].communicate(timeout=timeout)

        for i in range(len(objects) - 1):
            objects[i].wait(timeout=timeout)

    except subprocess.TimeoutExpired:
        for p in objects:
            p.terminate()
        raise

    # collect the return codes
    if check_results:
        for i in range(cmd_no):
            if objects[i].returncode:
                if not quiet and (cmdout or cmderr):
                    cprintln(f"captured stdout: {cmdout.decode('utf-8')}", "red")
                    cprintln(f"captured stderr: {cmderr.decode('utf-8')}", "red")
                raise subprocess.CalledProcessError(objects[i].returncode, unpiped_commands[i])

    return cmdout, cmderr


def run_safely_list_of_commands(cmd_list: list[str]) -> None:
    """Runs safely list of commands

    :param list cmd_list: list of external commands
    :raise subprocess.CalledProcessError: when there is an error in any of the commands
    """
    for cmd in cmd_list:
        info(">", cmd)
        out, err = run_safely_external_command(cmd)
        if out:
            info(out.decode("utf-8"), end="")
        if err:
            cprint(err.decode("utf-8"), "red")


def get_stdout_from_external_command(command: list[str], stdin: Optional[IO[bytes]] = None) -> str:
    """Runs external command with parameters, checks its output and provides its output.

    :param list command: list of arguments for command
    :param handle stdin: the command input as a file handle
    :return: string representation of output of command
    """
    output = subprocess.check_output(
        [c for c in command if c != ""], stderr=subprocess.STDOUT, stdin=stdin
    )
    return output.decode("utf-8")


def dynamic_module_function_call(
    package_name: str, module_name: str, fun_name: str, *args: Any, **kwargs: Any
) -> Any:
    """Dynamically calls the function from other package with given arguments

    Looks up dynamically the module of the @p module_name inside the @p package_name
    package and calls its function @p fun_name with positional *args and keyword
    **kwargs.

    In case the module or function is missing, error is returned and program ends
    TODO: Add dynamic checking for the possible malicious code

    :param str package_name: name of the package, where the function we are calling is
    :param str module_name: name of the module, to which the function corresponds
    :param str fun_name: name of the function we are dynamically calling
    :param list args: list of non-keyword arguments
    :param dict kwargs: dictionary of keyword arguments
    :return: whatever the wrapped function returns
    """
    function_location_path = ".".join([package_name, module_name])
    try:
        module = get_module(function_location_path)
        module_function = getattr(module, fun_name)
        return module_function(*args, **kwargs)
    # Simply pass these exceptions higher however with different flavours:
    # 1) When Import Error happens, this means, that some module is not found in Perun hierarchy,
    #   hence, we are trying to call some collector/visualizer/postprocessor/vcs, which is not
    #   implemented in Perun.
    #
    # 2) When Attribute Error happens, this means, that we have found supported module, but, there
    #   is some functionality, that is missing in the module.
    #
    # Why reraise the exceptions? Because it is up to the higher levels to catch these exceptions
    # and handle the errors their way. It should be different in CLI and in GUI, and they should
    # be caught in right places.
    except ImportError:
        raise UnsupportedModuleException(module_name)
    except AttributeError:
        raise UnsupportedModuleFunctionException(fun_name, function_location_path)


def get_module(module_name: str) -> types.ModuleType:
    """Finds module by its name.

    :param str module_name: dynamically load a module (but first check the cache)
    :return: loaded module
    """
    if module_name not in MODULE_CACHE.keys():
        MODULE_CACHE[module_name] = importlib.import_module(module_name)
    return MODULE_CACHE[module_name]


MODULE_CACHE: dict[str, types.ModuleType] = {}


def get_supported_module_names(package: str) -> list[str]:
    """Obtains list of supported modules supported by the package.

    Contains the hard-coded dictionary of packages and their supported values. This simply does
    a key lookup and returns the list of supported values.

    This was originally dynamic collection of all the modules through beautiful module iteration,
    which was shown to be completely uselessly slower than this hardcoded table. Since I assume, that
    new modules will be registered very rarely, I think it is ok to have it implemented like this.

    Note: This is used in CLI, and as of Click 7.0 all subcommands have underscores (_)
    replaced by (-). While this is useful in CLI, Perun needs the underscore,
    so use Unit.sanitize_module_name to replace the dash back.

    :param str package: name of the package for which we want to obtain the supported modules
                        one of ('vcs', 'collect', 'postprocess')
    :return: list of names of supported modules for the given package
    """
    if package not in ("vcs", "collect", "postprocess", "view"):
        error(f"trying to call get_supported_module_names with incorrect package '{package}'")
    return {
        "vcs": ["git"],
        "collect": ["trace", "memory", "time", "complexity", "bounds"],
        "postprocess": [
            "regression-analysis",
            "regressogram",
            "moving-average",
            "kernel-regression",
        ],
        "view": ["bars", "flamegraph", "flow", "heapmap", "scatter", "tableof"],
    }[package]


def merge_dictionaries(*args: dict[Any, Any]) -> dict[Any, Any]:
    """Helper function for merging range (list, ...) of dictionaries to one to be used as oneliner.

    :param list args: list of dictionaries
    :return: one merged dictionary
    """
    res = {}
    for dictionary in args:
        res.update(dictionary)
    return res


def partition_list(
    input_list: Iterable[Any], condition: Callable[[Any], bool]
) -> tuple[list[Any], list[Any]]:
    """Utility function for list partitioning on a condition so that the list is not iterated
    twice and the condition is evaluated only once.

    Based on a SO answer featuring multiple methods and their performance comparison:
    'https://stackoverflow.com/a/31448772'

    :param iterator input_list: the input list to be partitioned
    :param function condition: the condition that should be evaluated on every list item
    :return tuple: (list of items evaluated to True, list of items evaluated to False)
    """
    good, bad = [], []
    for item in input_list:
        if condition(item):
            good.append(item)
        else:
            bad.append(item)
    return good, bad


def abs_in_relative_range(value: float, range_val: float, range_rate: float) -> bool:
    """Tests if value is in relative range as follows:

    (1 - range_rate) * range_val <= value <= (1 + range_rate) * range_val

    :param numeric value: value we are testing if it is in the range
    :param numeric range_val: value which gives the range
    :param float range_rate: the rate in percents which specifies the range
    :return: true if the value is in relative range
    """
    range_rate = range_rate if 0.0 <= range_rate <= 1.0 else 0.0
    return abs((1.0 - range_rate) * range_val) <= abs(value) <= abs((1.0 + range_rate) * range_val)


def abs_in_absolute_range(value: float, border: float) -> bool:
    """Tests if value is in absolute range as follows:

    -border <= value <= border

    :param numeric value: tests if the
    :param numeric border:
    :return: true if the value is in absolute range
    """
    return -abs(border) <= value <= abs(border)
