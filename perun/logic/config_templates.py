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
| :cunit:`args`                             |                    --                  |               --              |     --     |
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
This is, however, not implemented yet.

Currently the templates are set ``-t`` option of ``perun init`` command (see :ref:`cli-main-ref` for
details on ``perun init``). By default **user** configuration is used.
"""
import jinja2

__author__ = 'Tomas Fiedor'

CONFIG_FILE_STRING = """
vcs:
  type: {{ vcs.type }}
  url: {{ vcs.url }}

## The following sets the executables (binaries / scripts).
## These will be profiled by selected collectors.
{% if cmds is defined %}
## Extend the following region with more executables to be profiled:
cmds:
// for cmd in cmds:
  - {{ cmd }}}
// endfor
{% else %}
## Uncomment and edit the following region:
# cmds:
#   - echo
{% endif %}

## The following sets argument configurations for the profiled executables
{% if args is defined %}
## Extend the following region to profile more configuration:
args:
// for arg in args
  - {{ arg }}
// endfor
{% else %}
## Uncomment and edit the following region:
# args:
#   - -e
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
       - {{ param }}: {{ value }}
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
#   - name: normalizer
#     params: --remove-zero
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

{% if format is defined and format.output_profile_template is defined %}
## The following changes the automatically generated name of the profiles
format:
  output_profile_template: {{ format.output_profile_template }}
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


def get_predefined_configuration(name, kwargs):
    """Converts the given string to an appropriate predefined configuration.

    In case the specified configuration does not exist, then Master configuration is used as default.

    :param str name: name of the predefined configuration
    :param dict kwargs: additional keyword arguments
    :return: rendered template
    """
    env = jinja2.Environment(
        lstrip_blocks=True,
        trim_blocks=True,
        line_statement_prefix='//'
    )
    template = env.from_string(CONFIG_FILE_STRING)
    options = {
        'MasterConfiguration': MasterConfiguration(),
        'DeveloperConfiguration': DeveloperConfiguration(),
        'UserConfiguration': UserConfiguration()
    }.get("{}Configuration".format(name.title()), "MasterConfiguration")
    return template.render(dict(vars(options), **kwargs))


class MasterConfiguration(object):
    """Basic configuration, that contains no set options at all, everything is hence commented out.

    Moreover, Master is sane default for most of the functions, except for CLI calling.
    """
    def __init__(self):
        """Initialization of keys used for jinja2 template"""
        pass


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
    def __init__(self):
        """Initialization of keys used for jinja2 template"""
        super().__init__()
        self.execute = {
            'pre_run': ['make']
        }
        self.degradation = {
            'strategy': [{'method': 'average_amount_threshold'}],
            'collect_before_check': 'true',
            'log_collect': 'true',
        }


class UserConfiguration(DeveloperConfiguration):
    """Configuration meant for basic users, which extends the developer configuration.

    This additionally lookus up the commands and workloads out of the project working directory,
    automatically sets the timing of project, registering and the template for generated profiles.

    The following configuration options will be additionally set:

    +-------------------------------------------+----------------------------------------+
    |                                           | **user**                               |
    +-------------------------------------------+----------------------------------------+
    | :cunit:`cmds`                             |               auto lookup              |
    +-------------------------------------------+----------------------------------------+
    | :cunit:`args`                             |                    --                  |
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
    def __init__(self):
        """Initialization of keys used for jinja2 template"""
        super().__init__()
        # TODO: Lookup executables
        # TODO: Lookup workloads
        self.collectors = [
            {'name': 'time',
             'params': {
                 'warmup': 3,
                 'repeat': 10
             }}
        ]
        self.format = {
            'output_profile_template': '\"%collector%-of-%cmd%-%workload%-%date%\"'
        }
        self.profiles = {
            'register_after_run': 'true'
        }

