"""Config is a module for storing and managing local, global and temporary configuration files.

Config provides instances of Configuration objects, for both temporary, global and local types.
Stored configurations are in YAML format, inspired e.g. by Travis.

There are three types of config: local, corresponding to concrete pcs, global, which contains
global information and configurations, like e.g. list of registered repositories, and temporary,
containing formats and options for one execution of perun command.
"""
import os
import re
import sys

from ruamel.yaml import YAML, scanner
import ruamel.yaml.comments as comments


import perun.logic.store as store
import perun.utils.decorators as decorators
import perun.utils.exceptions as exceptions
import perun.utils.log as perun_log
import perun.utils.streams as streams

__author__ = 'Tomas Fiedor'


def is_valid_key(key):
    """Validation function for key representing one option in config section.

    Validates that the given string key is in form of dot separated (.) strings. Each delimited
    string represents one subsection, with last string representing the option.

    :param str key: string we are validating
    :returns: true if the given key is in correct key format
    """
    valid_key_pattern = re.compile(r"^[a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)*$")
    return valid_key_pattern.match(key) is not None


class Config(object):
    """Config represents one instance of configuration of given type.

    Configurations are represented by their type and dictionary containing (possibly nested)
    section with concrete keys, such as the following::

        {
            'general': {
                'paging': 'only-log'
                'editor': 'vim'
            },
            'format': {
                'status': '%type% > %origin%',
                'log': '%checksum:6%: %desc%'
            }
        }

    If the path is set, then the config will be saved to the given path, if the config is modified
    during the run.
    """
    def __init__(self, config_type, path, config_initial_data):
        """
        :param str config_type: type of the configuration (one of 'local', 'global', 'temporary')
        :param str path: path leading to the configuration (if stored internally)
        :param dict config_initial_data: dictionary representation of the stored config, can either
            be empty for some configuration, or loaded from the filesystem
        """
        self.type = config_type
        self.path = path
        self.data = config_initial_data

    @decorators.validate_arguments(['key'], is_valid_key)
    def set(self, key, value):
        """Overrides the value of the key in the config.

        :param str key: list of sections separated by dots
        :param object value: value we are writing to the key at config
        """
        # Remove the key from the caching
        # ! Note that this is mainly used for the testing, but might be triggered during the future
        # as well.
        decorators.func_args_cache['lookup_key_recursively'].pop(tuple([key]), None)
        decorators.func_args_cache['gather_key_recursively'].pop(tuple([key]), None)

        *sections, last_section = key.split('.')
        _locate_section_from_query(self.data, sections)[last_section] = value
        if self.path:
            print(self.path)
            write_config_to(self.path, self.data)

    @decorators.validate_arguments(['key'], is_valid_key)
    def append(self, key, value):
        """Appends the value of the key to the given option in the config.

        This requires the key to point to a list option.

        :param str key: list of sections separated by dots
        :param object value: value we are appending to the key at config
        """
        *sections, last_section = key.split('.')
        section_location = _locate_section_from_query(self.data, sections)
        if last_section not in section_location.keys():
            section_location[last_section] = []
        section_location[last_section].append(value)
        if self.path:
            write_config_to(self.path, self.data)

    @decorators.validate_arguments(['key'], is_valid_key)
    def get(self, key):
        """Returns the value of the key stored in the config.

        :param str key: list of section separated by dots
        :returns value: retrieved value of the key at config
        :raises exceptions.MissingConfigSectionException: if the key is not present in the config
        """
        sections = key.split('.')

        section_iterator = self.data
        for section in sections:
            section_iterator = _ascend_by_section_safely(section_iterator, section)
        return section_iterator


def write_config_to(path, config_data):
    """Stores the config data on the path

    :param str path: path where the config will be stored to
    :param dict config_data: dictionary with contents of the configuration
    """
    perun_log.msg_to_stdout("Writing config '{}' at {}".format(
        config_data, path
    ), 2)
    with open(path, 'w') as yaml_file:
        YAML().dump(config_data, yaml_file)


def read_config_from(path):
    """Reads the config data from the path

    :param str path: source path of the config
    :returns: configuration data represented as dictionary of keys and their appropriate values
        (possibly nested)
    """
    try:
        return streams.safely_load_yaml_from_file(path)
    except scanner.ScannerError as scanner_error:
        perun_log.error("corrupted configuration file '{}': {}\n".format(path, str(scanner_error))
                        + "\nPerhaps you did not escape strings with special characters in quotes?")


def init_shared_config_at(path):
    """Creates the new configuration at given path with sane defaults of e.g. editor, paging of
    outputs or formats for status or log commands.

    :param str path: path where the empty global config will be initialized
    """
    if not path.endswith('shared.yml') and not path.endswith('shared.yaml'):
        path = os.path.join(path, 'shared.yml')
    store.touch_file(path)

    shared_config = streams.safely_load_yaml_from_stream("""
general:
    editor: vim
    paging: only-log

format:
    status: "\u2503 %type% \u2503 %collector%  \u2503 (%time%) \u2503 %origin% \u2503"
    shortlog: "%checksum:6% (%stats%) %desc%"
    output_profile_template: "%collector%-%cmd%-%args%-%workload%-%date%"
    output_show_template: "%collector%-%cmd%-%args%-%workload%-%date%"

degradation:
    apply: all
    strategies:
      - method: average_amount_threshold
    """)

    write_config_to(path, shared_config)


def init_local_config_at(path, wrapped_vcs):
    """Creates the new local configuration at given path with sane defaults and helper comments
    for use in order to initialize the config matrix.

    :param str path: path where the empty shared config will be initialized
    :param dict wrapped_vcs: dictionary with wrapped vcs of type {'vcs': {'type', 'url'}}
    """
    if not path.endswith('local.yml') and not path.endswith('local.yaml'):
        path = os.path.join(path, 'local.yml')
    store.touch_file(path)

    # Create a config for user to set up
    local_config = streams.safely_load_yaml_from_stream("""
vcs:
  type: {0}
  url: {1}

## To collect profiling data from the binary using the set of collectors,
## uncomment and edit the following region:
# cmds:
#   - echo

## To add set of parameters for the profiled command/binary,
## uncomment and edit the following region:
# args:
#   - -e

## To add workloads/inputs for the profiled command/binary,
## uncomment and edit the following region:
# workloads:
#   - hello
#   - world

## To register a collector for generating profiling data,
## uncomment and edit the following region:
# collectors:
#   - name: time
## Try '$ perun collect --help' to obtain list of supported collectors!

## To register a postprocessor for generated profiling data,
## uncomment and edit the following region (!order matters!):
# postprocessors:
#   - name: normalizer
#     params: --remove-zero
#   - name: filter
## Try '$ perun postprocessby --help' to obtain list of supported collectors!
    """.format(wrapped_vcs['vcs']['type'], wrapped_vcs['vcs']['url']))

    write_config_to(path, local_config)


def init_config_at(path, config_type):
    """Wrapping function for calling appropriate initialization function of local and global config.

    :param str path: path where the empty shared config will be initialized
    :param str config_type: type of the config (either shared or local)
    :returns: true if the config file was successfully created
    """
    init_function_name = "init_{}_config_at".format(config_type)
    return getattr(sys.modules[__name__], init_function_name)(path)


def _locate_section_from_query(config_data, sections):
    """Iterates through the config dictionary and queries the subsections from the list of the
    sections, returning the last one.

    :param dict config_data: dictionary representing yaml configuration
    :param list sections: list of sections in config
    :returns: dictionary representing the section that will be updated
    """

    section_iterator = config_data
    for section in sections:
        if section not in section_iterator.keys():
            section_iterator[section] = {}
        section_iterator = section_iterator[section]
    return section_iterator


def _ascend_by_section_safely(section_iterator, section_key):
    """Ascends by one level in the section_iterator.

    In case the section_key is not in the section_iterator, MissingConfigSectionException is raised.

    :param dict section_iterator: dictionary with sections
    :param str section_key: section in dictionary
    :returns: dictionary or the key after ascending by one section key
    :raises exceptions.MissingConfigSectionException: when the given section_key is not found in the
        configuration object.
    """
    if section_key not in section_iterator:
        raise exceptions.MissingConfigSectionException(
            "missing section '{}' in the config file".format(section_key)
        )
    return section_iterator[section_key]


def load_config(config_dir, config_type):
    """Loads the configuration of given type from the appropriate file (either local.yml or
    global.yml).

    :param str config_dir: directory, where the config is stored
    :param str config_type: type of the config (either shared or local)
    :returns: loaded Config object with populated data and set path and type
    """
    config_file = os.sep.join([config_dir, ".".join([config_type, 'yml'])])

    try:
        if not os.path.exists(config_file):
            init_config_at(config_file, config_type)

        return Config(config_type, config_file, read_config_from(config_file))
    except IOError as io_error:
        perun_log.error("error initializing {} config: {}".format(
            config_type, str(io_error)
        ))


def lookup_shared_config_dir():
    """Performs a lookup of the shared config dir on the given platform.

    First we check if PERUN_CONFIG_DIR environmental variable is set, otherwise, we try to expand
    the home directory of the user and according to the platform we return the sane location.

    On windows systems, we use the AppData\Local\perun directory in the user space, on linux
    system we use the ~/.config/perun. Other platforms are not supported, however can be initialized
    using the PERUN_CONFIG_DIR.

    :returns: dir, where the shared config will be stored
    """
    environment_dir = os.environ.get('PERUN_CONFIG_DIR')
    if environment_dir:
        return environment_dir

    home_directory = os.path.expanduser("~")

    if sys.platform == 'win32':
        perun_config_dir = os.path.join(home_directory, 'AppData', 'Local', 'perun')
    elif sys.platform == 'linux':
        perun_config_dir = os.path.join(home_directory, '.config', 'perun')
    else:
        perun_log.error("""{} platform is currently unsupported.

Set `PERUN_CONFIG_DIR` environment variable to a valid directory, where the global config will be stored and rerun the command.
        """.format(sys.platform))

    store.touch_dir_range(home_directory, perun_config_dir)
    return perun_config_dir


@decorators.singleton
def shared():
    """Returns the configuration corresponding to the shared configuration data, i.e. the config
    possibly shared by all perun instances.

    :returns: shared Config file
    """
    shared_config_dir = lookup_shared_config_dir()
    return load_config(shared_config_dir, 'shared')


@decorators.singleton_with_args
def local(path):
    """Returns the configuration corresponding to the one local configuration data, located at @p
    path.

    :param src path: path corresponding to the perun instance
    :returns config: local Config from the given path
    """
    if os.path.isdir(path):
        return load_config(path, 'local')
    else:
        perun_log.warn("""local configuration file at {} does not exist.

Creating an empty configuration. Run ``perun config --local --edit`` to initialized or modify the local configuration in text editor.
        """.format(path))
        return Config('local', path, {})


@decorators.singleton
def runtime():
    """
    Returns the configuration corresponding to the one runtime of perun command, not stored anywhere
    and serving as a temporary shared storage through various functions. Moreover this is also
    used to temporary rewrite some options looked-up in the recursive manner.

    runtime = {
        'output_filename_template': ''
        'perun_scope': PCS()
        'output_filename_queue': []
        'input_filename_queue': []
        'format': {
            'shortlog': ''
            'status': ''
        }
    }

    :returns: runtime temporary config
    """
    return Config('runtime', '', {
        'output_filename_queue': [],
        'input_filename_queue': []
    })


def get_hierarchy():
    """Iteratively yields the configurations of perun in order in which they should be looked
    up.

    First we check the runtime/temporary configuration, then we walk the local instances of
    configurations and last we check the global config.

    :returns: iterable stream of configurations in the priority order
    """
    yield runtime()
    try:
        yield local(os.path.join(store.locate_perun_dir_on(os.getcwd()), ".perun"))
    except exceptions.NotPerunRepositoryException:
        # We skip if we are not within any perun repository
        pass
    yield shared()


@decorators.singleton_with_args
def lookup_key_recursively(key):
    """Recursively looks up the key first in the local config and then in the global.

    This is used e.g. for formatting strings or editors, where first we have our local configs,
    that have higher priority. In case there is nothing set in the config, we will check the
    global config.

    :param str key: key we are looking up
    """
    # Fixme: this should contain recursive lookup for other instances and also the temporary config
    for config_instance in get_hierarchy():
        try:
            return config_instance.get(key)
        except exceptions.MissingConfigSectionException:
            continue
    raise exceptions.MissingConfigSectionException


@decorators.singleton_with_args
def gather_key_recursively(key):
    """Recursively gathers the key, first in the temporary config, etc. up to the global config.

    Gathered keys are ordered in list. If no key is found, an empty list is returned.

    :param str key: key we are looking up
    :returns: list of keys
    """
    gathered_values = []
    for config_instance in get_hierarchy():
        try:
            value = config_instance.get(key)
            if isinstance(value, list) or isinstance(value, comments.CommentedSeq):
                gathered_values.extend(value)
            else:
                gathered_values.append(value)
        except exceptions.MissingConfigSectionException:
            continue
    return gathered_values

