"""Internally local configuration files are specified w.r.t a Jinja2 template.

This template can further be augmented by named sets of predefined configuration as follows:

  1. **user** configuration is meant for beginner users, that have no experience with Perun and
  have not read the documentation thoroughly. This contains a basic preconfiguration that should be
  applicable for most of the projects---data are collected by :ref:`collectors-time` and are
  automatically registered in the Perun after successful run. The performance is checked using
  the :ref:`degradation-method-aat`. Missing profiling info will be looked up automatically.

  2. **developer** configuration is meant for advanced users, that have some understanding of
  profiling and/or Perun. Fair amount of options are up to the user, such as the collection of
  the data and the commands that will be profiled.

  3. **master** configuration is meant for experienced users. The configuration will be mostly
  empty.

The actually set options are specified in the following table. When the option is not set
(signaled by ``-`` symbol) we output in the configuration table only a commented-out hint.

+-------------------------------------------+----------------------------------------+-------------------------------+------------+
|                                           | **user**                               | **developer**                 | **master** |
+-------------------------------------------+----------------------------------------+-------------------------------+------------+
| :cunit:`cmds`                             |               auto lookup              |               --              |     --     |
+-------------------------------------------+----------------------------------------+-------------------------------+------------+
| :cunit:`workloads`                        |               auto lookup              |               --              |     --     |
+-------------------------------------------+----------------------------------------+-------------------------------+------------+
| :cunit:`collectors`                       | :ref:`collectors-time`                 |               --              |     --     |
+-------------------------------------------+----------------------------------------+-------------------------------+------------+
| :ckey:`degradation.strategies`            | :ref:`degradation-method-aat`          | :ref:`degradation-method-aat` |     --     |
+-------------------------------------------+----------------------------------------+-------------------------------+------------+
| :ckey:`degradation.collect_before_check`  | true                                   | true                          |     --     |
+-------------------------------------------+----------------------------------------+-------------------------------+------------+
| :ckey:`degradation.log_collect`           | true                                   | true                          |     --     |
+-------------------------------------------+----------------------------------------+-------------------------------+------------+
| :ckey:`execute.pre_run`                   | make                                   | make                          |     --     |
+-------------------------------------------+----------------------------------------+-------------------------------+------------+
| :ckey:`profiles.register_after_run`       | true                                   |               --              |     --     |
+-------------------------------------------+----------------------------------------+-------------------------------+------------+
| :ckey:`format.output_profile_template`    | %collector%-of-%cmd%-%workload%-%date% |               --              |     --     |
+-------------------------------------------+----------------------------------------+-------------------------------+------------+

In **user** configuration, we try to lookup the actual commands and workloads for profiling purpose.
Currently for candidate executables we look within a subfolders named ``build``, ``_build`` or
``dist`` and check if we find any executables. Each found executable is then registered as profiled
command. For workloads we look for any file (without restrictions), and we restrict ourselves to
subfolders with names such as ``workload``, ``workloads``, ``examples`` or ``payloads``. Each
compatible file is then registered as workload.

Currently the templates are set by ``-t`` option of ``perun init`` command (see :ref:`cli-main-ref`
for details on ``perun init``). By default **master** configuration is used.
"""
from __future__ import annotations

# Standard Imports
from typing import Iterable, Any
import os
import subprocess

# Third-Party Imports
import jinja2

# Perun Imports
from perun.utils import log
from perun.utils.external import commands


CONFIG_FILE_STRING = """
vcs:
  type: {{ vcs.type }}
  url: {{ vcs.url }}

## The following sets the executables (binaries / scripts).
## These will be profiled by selected collectors.
{% if cmds is defined %}
## Extend the following region with more executable commands to be profiled:
cmds:
// for cmd in cmds:
  - {{ cmd }}
// endfor
{% else %}
## Uncomment and edit the following region:
# cmds:
#   - echo
{% endif %}

## The following sets the profiling workload for given commands
{% if workloads is defined %}
## Extend the following region to profile more different workloads:
workloads:
// for workload in workloads
  - {{ workload }}
// endfor
{% else %}
## Uncomment and edit the following region:
# workloads:
#   - hello
#   - world
{% endif %}

## The following contains the set of collectors (profilers) that will collect performance data.
{% if collectors is defined %}
## Extend the following region to use more profilers:
collectors:
  // for collector in collectors
    - name: {{ collector.name }}
    {% if collector.params is defined %}
      params:
    // for param, value in collector.params.items()
        {{ param }}: {{ value }}
    // endfor
    {% endif %}
  // endfor
{% else %}
## Uncomment and edit the following region:
# collectors:
#   - name: time
{% endif %}
## Try '$ perun collect --help' to obtain list of supported collectors!

## The following contains the ordered list of postprocess phases that are executed after collection.
{% if postprocessors is defined %}
postprocessors:
// for postprocessor in postprocessors:
    - name: {{ postprocessor.name }}
    {% if postprocessor.params is defined %}
      params:
    // for param, value in postprocessor.params.items()
        {{ param }}: {{ value }}
    // endfor
    {% endif %}
// endfor
{% else %}
## Uncomment and edit the following region (!order matters!):
# postprocessors:
#   - name: regression_analysis
#     params:
#       method: full
#   - name: filter
{% endif %}
## Try '$ perun postprocessby --help' to obtain list of supported collectors!

## The following option automatically registers newly collected profiles for current minor version
{% if profiles is defined %}
profiles:
  {% if profiles.register_after_run is defined %}
    register_after_run: {{ profiles.register_after_run }}
  {% endif %}
{% else %}
## Uncomment the following to enable this behaviour:
# profiles:
#   register_after_run: true
{% endif %}

## Be default, we sort the profiles by time
format:
  sort_profiles_by: time
{% if format is defined and format.output_profile_template is defined %}
## The following changes the automatically generated name of the profiles
  output_profile_template: "{{ format.output_profile_template }}"
{% endif %}

## The following options control the degradation checks in repository
{% if degradation is defined %}
degradation:
## Setting the following combination of option to true will make Perun collect new profiles,
## before checking for degradations and store them in logs at directory .perun/logs/
{% if degradation.collect_before_check is defined %}
  collect_before_check: {{ degradation.collect_before_check }}
{% else %}
#   collect_before_check: true
{% endif %}
{% if degradation.log_collect is defined %}
  log_collect: {{ degradation.log_collect }}
{% else %}
#   log_collect: true
{% endif %}
## Setting this to first (resp. all) will apply the first (resp. all) found check methods
## for corresponding configurations
{% if degradation.apply is defined %}
  apply: {{ degradation.apply }}
{% else %}
#   apply: first
{% endif %}
## Specification of list of rules for applying degradation checks
{% if degradation.strategy is defined %}
  strategy:
// for strategy in degradation.strategy
    - method: {{ strategy.method }}
// endfor
{% else %}
#   strategy:
#     - method: average_amount_threshold
{% endif %}
{% else %}
# degradation:
## Setting the following combination of option to true will make Perun collect new profiles,
## before checking for degradations and store them in logs at directory .perun/logs/
#   collect_before_check: true
#   log_collect: true
## Setting this to first (resp. all) will apply the first (resp. all) found check methods
## for corresponding configurations
#   apply: first
## Specification of list of rules for applying degradation checks
#   strategy:
#     - method: average_amount_threshold
{% endif %}

## To run your custom steps before any collection (un)comment the following region:
{% if execute is defined and execute.pre_run is defined %}
execute:
  pre_run:
// for pre_run_command in execute.pre_run
    - {{ pre_run_command }}
// endfor
{% else %}
# execute:
#   pre_run:
#     - make
{% endif %}
"""
CONFIG_FILE_TEMPLATE = None


def get_predefined_configuration(name: str, kwargs: dict[str, Any]) -> str:
    """Converts the given string to an appropriate predefined configuration.

    In case the specified configuration does not exist, then Master configuration is used as
    default.

    :param str name: name of the predefined configuration
    :param dict kwargs: additional keyword arguments
    :return: rendered template
    """
    # Lazy initialization of config template
    global CONFIG_FILE_TEMPLATE
    if not CONFIG_FILE_TEMPLATE:
        env = jinja2.Environment(
            lstrip_blocks=True,
            trim_blocks=True,
            line_statement_prefix="//",
            autoescape=True,
        )
        CONFIG_FILE_TEMPLATE = env.from_string(CONFIG_FILE_STRING)

    options = {
        "MasterConfiguration": MasterConfiguration,
        "DeveloperConfiguration": DeveloperConfiguration,
        "UserConfiguration": UserConfiguration,
    }.get(f"{name.title()}Configuration", MasterConfiguration)()
    return CONFIG_FILE_TEMPLATE.render(dict(vars(options), **kwargs))


class MasterConfiguration:
    """Basic configuration, that contains no set options at all, everything is hence commented out.

    Moreover, Master is sane default for most of the functions, except for CLI calling.
    """

    def __init__(self) -> None:
        """Initialization of keys used for jinja2 template"""


class DeveloperConfiguration(MasterConfiguration):
    """Configuration meant for advanced users (developers), which sets the basic degradation checks
    and automatic execution of the ``make`` before each collection.

    The following configurations options will be additionally set:

    +-------------------------------------------+-------------------------------+
    |                                           | **developer**                 |
    +-------------------------------------------+-------------------------------+
    | :ckey:`degradation.strategies`            | :ref:`degradation-method-aat` |
    +-------------------------------------------+-------------------------------+
    | :ckey:`degradation.collect_before_check`  | true                          |
    +-------------------------------------------+-------------------------------+
    | :ckey:`degradation.log_collect`           | true                          |
    +-------------------------------------------+-------------------------------+
    | :ckey:`execute.pre_run`                   | make                          |
    +-------------------------------------------+-------------------------------+
    """

    def __init__(self) -> None:
        """Initialization of keys used for jinja2 template"""
        super().__init__()
        self.execute = {"pre_run": ["make"]}
        self.degradation = {
            "strategy": [{"method": "average_amount_threshold"}],
            "collect_before_check": "true",
            "log_collect": "true",
        }


class UserConfiguration(DeveloperConfiguration):
    """Configuration meant for basic users, which extends the developer configuration.

    This additionally looks up the commands and workloads out of the project working directory,
    automatically sets the timing of project, registering and the template for generated profiles.

    The following configuration options will be additionally set:

    +-------------------------------------------+----------------------------------------+
    |                                           | **user**                               |
    +-------------------------------------------+----------------------------------------+
    | :cunit:`cmds`                             |               auto lookup              |
    +-------------------------------------------+----------------------------------------+
    | :cunit:`workloads`                        |               auto lookup              |
    +-------------------------------------------+----------------------------------------+
    | :cunit:`collectors`                       | :ref:`collectors-time`                 |
    +-------------------------------------------+----------------------------------------+
    | :ckey:`profiles.register_after_run`       | true                                   |
    +-------------------------------------------+----------------------------------------+
    | :ckey:`format.output_profile_template`    | %collector%-of-%cmd%-%workload%-%date% |
    +-------------------------------------------+----------------------------------------+
    """

    WORKLOAD_FOLDERS = {
        "workload",
        "workloads",
        "_workload",
        "_workloads",
        "examples",
        "payload",
        "payloads",
        "_payloads",
        "_payload",
        "_examples",
    }
    EXECUTABLE_FOLDERS = {"build", "_build", "dist"}

    @staticmethod
    def _all_candidate_files(include_list: set[str]) -> Iterable[str]:
        """Helper function that yield the stream of files contained in non-hidden directories

        :param set include_list: set of directory names that can contain looked-up files
        :return: iterable stream of files
        """
        for root, dirs, files in os.walk(os.getcwd(), topdown=True):
            # Skip all the directories starting with .
            # i.e. this will skip .git or .perun, etc.
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            if os.path.split(root)[1] in include_list:
                for file in files:
                    yield os.path.relpath(os.path.join(root, file), os.getcwd())

    @staticmethod
    def _locate_workload_candidates() -> list[str]:
        """Iterates through the filesystem tree under the current directory and tries to locate
        candidate workloads.

        The actual lookup is limited to subfolders such as 'workload', 'examples', 'payload' etc.

        :return: list of candidate workloads
        """
        log.minor_info("Looking for candidate workloads")
        workload_candidates = []
        for file in UserConfiguration._all_candidate_files(UserConfiguration.WORKLOAD_FOLDERS):
            workload_candidates.append(file)
        return workload_candidates

    @staticmethod
    def _locate_executable_candidates() -> list[str]:
        """Iterates through the filesystem tree under the current directory and tries to locate
        candidate executables.

        The actual lookup is limited to subfolders such as 'build', '_build', 'dist' etc.

        :return: list of candidate executables
        """
        # Execute make before, in case there is nothing to make, then beat it
        log.minor_info("Looking for candidate executables")
        log.increase_indent()
        try:
            commands.run_safely_list_of_commands(["make"])
            log.minor_success(f"{log.cmd_style('make')}")
        except subprocess.CalledProcessError:
            log.minor_fail(f"{log.cmd_style('make')}")
            log.minor_info("Nothing to make (probably)")
        log.decrease_indent()
        executable_candidates = []
        for file in UserConfiguration._all_candidate_files(UserConfiguration.EXECUTABLE_FOLDERS):
            if os.path.isfile(file) and os.access(file, os.X_OK):
                executable_candidates.append(file)
        return executable_candidates

    def __init__(self) -> None:
        """Initialization of keys used for jinja2 template"""
        super().__init__()
        self.collectors = [{"name": "time", "params": {"warmup": 3, "repeat": 10}}]
        self.format = {"output_profile_template": "%collector%-of-%cmd%-%workload%-%date%"}
        self.profiles = {"register_after_run": "true"}

        # Lookup executables and workloads
        executable_candidates = UserConfiguration._locate_executable_candidates()
        if executable_candidates:
            self.cmds = executable_candidates

        workload_candidates = UserConfiguration._locate_workload_candidates()
        if workload_candidates:
            self.workloads = workload_candidates
