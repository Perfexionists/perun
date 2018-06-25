"""Utils contains helper modules, that are not directly dependent on pcs.

Utils contains various helper modules and functions, that can be used in arbitrary projects, and
are not specific for perun pcs, like e.g. helper decorators, logs, etc.
"""

import importlib
import shlex
import subprocess
import os
import magic

from .log import error, cprint
from .exceptions import UnsupportedModuleException, UnsupportedModuleFunctionException

__author__ = 'Tomas Fiedor'
__coauthor__ = 'Jiri Pavela'


def get_build_directories(root='.', template=None):
    """Search for build directories in project tree. The build directories can be specified as an
    argument or default templates are used.

    :param str root: directory tree root
    :param list template: list of directory names to search for
    :return: generator object of build directories
    """
    if template is None:
        template = ['build', '_build', '__build']
    # Find all build directories in directory tree
    root = os.path.join(root, '')
    for current, subdirs, _ in os.walk(root):
        # current directory without root section
        # (to prevent nesting detection if root contains template directory)
        relative = current[len(root):]
        # Do not traverse hidden directories
        subdirs[:] = [d for d in subdirs if not d[0] == '.']
        for build_dir in template:
            # find directories conforming to the templates without nested ones
            if build_dir in subdirs and not _is_nested(relative, template):
                yield current + build_dir


def _is_nested(path, templates):
    """Check if any element from template is contained within the path - resolve nested template
    directories

    :param str path: path to be resolved
    :param list templates: list of directory names to search for
    :return: bool value representing result
    """
    for template in templates:
        if template in path:
            return True


def get_directory_elf_executables(root='.', only_not_stripped=False):
    """Get all ELF executable (stripped or not) from directory tree recursively.

    :param str root: directory tree root
    :param bool only_not_stripped: flag indicating whether collect only binaries not stripped
    :return: generator object of executable binaries as file paths
    """
    root = os.path.join(root, '')
    for current, subdirs, files in os.walk(root):
        # Ignore hidden directories and files
        subdirs[:] = [d for d in subdirs if not d[0] == '.']
        files = [f for f in files if f[0] != '.']
        for file in files:
            # Check if file is executable binary
            filepath = os.path.join(current, file)
            if is_executable_elf(filepath, only_not_stripped):
                yield filepath


def is_executable_elf(file, only_not_stripped=False):
    """Check if file is executable ELF binary.

    :param str file: the file path
    :param bool only_not_stripped: flag indicating whether also check stripped binaries or not
    :return: bool value representing check result
    """
    # Determine file magic code, we are looking out for ELF files
    file_magic = magic.from_file(file)
    if file_magic.startswith('ELF') and \
            ('executable' in file_magic or 'shared object' in file_magic):
        if only_not_stripped:
            return 'not stripped' in file_magic
        return True


def get_project_elf_executables(root='.', only_not_stripped=False):
    """Get all ELF executable files stripped or not from project specified by root
    The function searches for executable files in build directories - if there are any, otherwise
    the whole project directory tree is traversed.

    :param str root: directory tree root
    :param bool only_not_stripped: flag indicating whether collect only binaries not stripped
    :return: list of project executable binaries as file paths
    """
    # Get possible binaries in build directories
    root = os.path.join(root, '')
    build = list(get_build_directories(root))

    # No build directories, find all binaries instead
    if not build:
        build = [root]

    # Gather binaries
    binaries = []
    for build_dir in build:
        binaries += list(get_directory_elf_executables(build_dir, only_not_stripped))

    return binaries


def run_external_command(cmd_args):
    """Runs external command with parameters.

    :param list cmd_args: list of external command and its arguments to be run
    :return: return value of the external command that was run
    """
    process = subprocess.Popen(cmd_args)
    process.wait()
    return process.returncode


def start_nonblocking_process(cmd, **kwargs):
    """Safely start non-blocking process using subprocess without shell

    :param str cmd: string with command that should be executed
    :param kwargs: additional arguments to the Popen subprocess
    :return: Popen object representing the process

    """
    # Split process and arguments
    parsed_cmd = shlex.split(cmd)

    # Do not allow shell=True
    if 'shell' in kwargs:
        del kwargs['shell']

    # Start the process and do not block it (user can tho)
    proc = subprocess.Popen(parsed_cmd, shell=False, **kwargs)
    return proc


def run_safely_external_command(cmd, check_results=True):
    """Safely runs the piped command, without executing of the shell

    Courtesy of: https://blog.avinetworks.com/tech/python-best-practices

    :param str cmd: string with command that we are executing
    :param bool check_results: check correct command exit code and raise exception in case of fail
    :return: returned standard output and error
    :raises subprocess.CalledProcessError: when any of the piped commands fails
    """
    # Split
    unpiped_commands = list(map(str.strip, cmd.split("|")))
    cmd_no = len(unpiped_commands)

    # Run the command through pipes
    objects = []
    for i in range(cmd_no):
        executed_command = shlex.split(unpiped_commands[i])

        # set streams
        stdin = None if i == 0 else objects[i-1].stdout
        stderr = subprocess.STDOUT if i < (cmd_no - 1) else subprocess.PIPE

        # run the piped command and close the previous one
        piped_command = subprocess.Popen(executed_command, shell=False,
                                         stdin=stdin, stdout=subprocess.PIPE, stderr=stderr)
        if i != 0:
            objects[i-1].stdout.close()
        objects.append(piped_command)

    # communicate with the last piped object
    cmdout, cmderr = objects[-1].communicate()

    for i in range(len(objects) - 1):
        objects[i].wait()

    # collect the return codes
    if check_results:
        for i in range(cmd_no):
            if objects[i].returncode:
                raise subprocess.CalledProcessError(
                    objects[i].returncode, unpiped_commands[i]
                )

    return cmdout, cmderr


def run_safely_list_of_commands(cmd_list):
    """Runs safely list of commands

    :param list cmd_list: list of external commands
    :raise subprocess.CalledProcessError: when there is an error in any of the commands
    """
    for cmd in cmd_list:
        print(">", cmd)
        out, err = run_safely_external_command(cmd)
        if out:
            print(out.decode('utf-8'), end='')
        if err:
            cprint(err.decode('utf-8'), 'red')


def get_stdout_from_external_command(command):
    """Runs external command with parameters, checks its output and provides its output.

    :param list command: list of arguments for command
    :return: string representation of output of command
    """
    output = subprocess.check_output([c for c in command if c is not ''], stderr=subprocess.STDOUT)
    return output.decode('utf-8')


def dynamic_module_function_call(package_name, module_name, fun_name, *args, **kwargs):
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


def get_module(module_name):
    """Finds module by its name.

    :param str module_name: dynamically load a module (but first check the cache)
    :return: loaded module
    """
    if module_name not in get_module.cache.keys():
        get_module.cache[module_name] = importlib.import_module(module_name)
    return get_module.cache[module_name]
get_module.cache = {}


def get_supported_module_names(package):
    """Obtains list of supported modules supported by the package.

    Contains the hard-coded dictionary of packages and their supported values. This simply does
    a key lookup and returns the list of supported values.

    This was originally dynamic collection of all the modules through beautiful module iteration,
    which was shown to be completely uselessly slow than this hardcoded table. Since I assume, that
    new modules will be registered very rarely, I think it is ok to have it implemented like this.

    :param str package: name of the package for which we want to obtain the supported modules
                        one of ('vcs', 'collect', 'postprocess')
    :return: list of names of supported modules for the given package
    """
    if package not in ('vcs', 'collect', 'postprocess', 'view'):
        error("trying to call get_supported_module_names with incorrect package '{}'".format(
            package
        ))
    return {
        'vcs': ['git'],
        'collect': ['complexity', 'memory', 'time'],
        'postprocess': ['clusterizer', 'filter', 'normalizer', 'regression_analysis'],
        'view': ['bars', 'flamegraph', 'flow', 'heapmap', 'raw', 'scatter']
    }[package]


def merge_dictionaries(lhs, rhs):
    """Helper function for merging two dictionaries to one to be used as oneliner.

    :param dict lhs: left operand of the dictionary merge
    :param dict rhs: right operand of the dictionary merge
    :return: merged dictionary of the lhs and rhs
    """
    res = lhs.copy()
    res.update(rhs)
    return res


def merge_dict_range(*args):
    """Helper function for merging range (list, ...) of dictionaries to one to be used as oneliner.

    :param list args: list of dictionaries
    :return: one merged dictionary
    """
    res = {}
    for dictionary in args:
        res.update(dictionary)
    return res


def identity(*args):
    """Identity function, that takes the arguments and return them as they are

    Note that this is used as default transformator for to be used in arguments for transforming
    the data.

    :param list args: list of input arguments
    :return: non-changed list of arguments
    """
    # Unpack the tuple if it is single
    return args if len(args) > 1 else args[0]


def abs_in_relative_range(value, range_val, range_rate):
    """Tests if value is in relative range as follows:

    (1 - range_rate) * range_val <= value <= (1 + range_rate) * range_val

    :param numeric value: value we are testing if it is in the range
    :param numeric range_val: value which gives the range
    :param float range_rate: the rate in percents which specifies the range
    :return: true if the value is in relative range
    """
    range_rate = range_rate if 0.0 <= range_rate <= 1.0 else 0.0
    return abs((1.0 - range_rate) * range_val) <= abs(value) <= abs((1.0 + range_rate) * range_val)


def abs_in_absolute_range(value, border):
    """Tests if value is in absolute range as follows:

    -border <= value <= border

    :param numeric value: tests if the
    :param numeric border:
    :return: true if the value is in absolute range
    """
    return -abs(border) <= value <= abs(border)
