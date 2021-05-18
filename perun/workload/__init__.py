"""From version 0.15.1, Perun supports the specification of workload generators, instead of raw
workload values specified in :munit:`workloads`. These generators continuously generates workloads
and internally Perun either merges the resources into one single profile or gradually generates
profile for each workload.

The generators are specified by :ckey:`generators.workload` section. These specifications are
collected through all of the configurations in the hierarchy.

You can use some basic generators specified in shared configurations called ``basic_strings``
(which generates strings of lengths from interval (8, 128) with increment of 8), ``basic_integers``
(which generates integers from interval (100, 10000), with increment of 200) or ``basic_files``
(which generates text files with number of lines from interval (10, 10000), with increment of
1000).
"""

from typing import Dict

import perun.logic.config as config
import perun.utils.log as log
import perun.utils as utils

from perun.utils.structs import GeneratorSpec

__author__ = 'Tomas Fiedor'


def load_generator_specifications() -> Dict[str, GeneratorSpec]:
    """Collects from configuration file all of the workload specifications and constructs a mapping
    of 'id' -> GeneratorSpec, which contains the constructor and parameters used for construction.

    The specifications are specified by :ckey:`generators.workload` as follows:

    generators:
      workload:
        - id: name_of_generator
          type: integer
          min_range: 10
          max_range: 20

    :return: map of ids to generator specifications
    """
    specifications_from_config = config.gather_key_recursively('generators.workload')
    spec_map = {}
    warnings = []
    log.info("Loading workload generator specifications ", end='')
    for spec in specifications_from_config:
        if 'id' not in spec.keys() or 'type' not in spec.keys():
            warnings.append("incorrect workload specification: missing 'id' or 'type'")
            log.info("F", end='')
            continue
        generator_module = "perun.workload.{}_generator".format(spec['type'].lower())
        constructor_name = "{}Generator".format(spec['type'].title())
        try:
            constructor = getattr(utils.get_module(generator_module), constructor_name)
            spec_map[spec['id']] = GeneratorSpec(constructor, spec)
            log.info(".", end='')
        except (ImportError, AttributeError):
            warnings.append(
                "incorrect workload generator '{}': '{}' is not valid workload type".format(
                    spec['id'], spec['type']
                )
            )
            log.info("F", end='')

    # Print the warnings and badge
    if warnings:
        log.failed()
        log.info("\n".join(warnings))
    else:
        log.done()

    return spec_map
