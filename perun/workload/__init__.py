"""From version 15.1, Perun supports the specification of workload generators, instead of raw
workload values specified in :munit:`workloads`. These generators continuously generates workloads
and internally Perun either merges the resources into one single profile or gradually generates
profile for each workload.

The generators are specified by :ckey:`generators.workload` section. These specifications are
collected through all of the configurations in the hierarchy.
"""

import perun.logic.config as config
import perun.utils.log as log
import perun.utils as utils

from perun.utils.structs import GeneratorSpec

__author__ = 'Tomas Fiedor'


def load_generator_specifications():
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
    print("Loading workload generator specifications ", end='')
    for spec in specifications_from_config:
        if 'id' not in spec.keys() or 'type' not in spec.keys():
            warnings.append("incorrect workload specification: missing 'id' or 'type'")
            print("F", end='')
            continue
        generator_module = "perun.workload.{}_generator".format(spec['type'].lower())
        constructor_name = "{}Generator".format(spec['type'].title())
        try:
            constructor = getattr(utils.get_module(generator_module), constructor_name)
            spec_map[spec['id']] = GeneratorSpec(constructor, spec)
            print(".", end='')
        except (ImportError, AttributeError):
            warnings.append("incorrect workload generator '{}': '{}' is not valid workload type".format(
                spec['id'], spec['type']
            ))
            print("F", end='')

    # Print the warnings and badge
    if len(warnings):
        log.failed()
        print("\n".join(warnings))
    else:
        log.done()

    return spec_map
