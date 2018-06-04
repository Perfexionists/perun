"""Configuration is specified w.r.t a Jinja2 template.

The template can further be augmented by sets of predefined compound configuration as follows:

  1. **user** configuration is meant for beginner users, that have no experience with Perun and
  have not read the documentation thoroughly. This contains a basic preconfiguration that should be
  applicable for most of the projects---data are collected by :ref:`collectors-time` and are
  automatically registered in the Perun after successful run. The performance is checked using
  the :ref:`degradation-method-aat`. Missing information will be looked up automatically.

  2. **developer** configuration is meant for advanced users, that have some understanding of
  profiling and/or Perun. Fair amount of options are up to the user, such as the collection of
  the data and the commands that will be profiled.

  3. **master** configuration is meant for experienced users. The configuration will be mostly
  empty.
"""
import jinja2

__author__ = 'Tomas Fiedor'

CONFIG_FILE = jinja2.Template("""
vcs:
  type: {{ vcs.type }}
  url: {{ vcs.url }}

## Uncomment this to automatically register newly collected profiles for current minor version
# profiles:
#   register_after_run: true

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

## To run detection of degradation for this repository, uncomment the following:
# degradation:
## Setting this option to true value will make Perun collect new profiles,
## before checking for degradations and store them in logs at directory .perun/logs/
#   collect_before_check: true
#   log_collect: true
## Setting this to first (resp. all) will apply the first (resp. all) found check methods
## for corresponding configurations
#   apply: first
## Specification of list of rules for applying degradation checks
#   strategy:
#     - method: average_amount_threshold

## To run your custom steps before any collection uncomment the following region:
# execute:
#   pre_run:
#     - make
""")
