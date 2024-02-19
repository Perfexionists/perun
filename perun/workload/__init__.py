"""From version 0.15.1, Perun supports the specification of workload generators, instead of raw
workload values specified in :munit:`workloads`. These generators continuously generates workloads
and internally Perun either merges the resources into one single profile or gradually generates
profile for each workload.

The generators are specified by :ckey:`generators.workload` section. These specifications are
collected through all configurations in the hierarchy.

You can use some basic generators specified in shared configurations called ``basic_strings``
(which generates strings of lengths from interval (8, 128) with increment of 8), ``basic_integers``
(which generates integers from interval (100, 10000), with increment of 200) or ``basic_files``
(which generates text files with number of lines from interval (10, 10000), with increment of
1000).
"""
from __future__ import annotations

from perun.logic import config
from perun.utils import log, decorators
from perun.utils.common import common_kit
from perun.utils.structs import GeneratorSpec


@decorators.resetable_always_singleton
def load_generator_specifications() -> dict[str, GeneratorSpec]:
    """Collects from configuration file all the workload specifications and constructs a mapping
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
    specifications_from_config = config.gather_key_recursively("generators.workload")
    spec_map = {}
    warnings = []
    log.minor_info("Loading workload generator specifications", end="")
    for spec in specifications_from_config:
        if "id" not in spec.keys() or "type" not in spec.keys():
            warnings.append((spec.get("id", "?"), "specification is missing 'id' or 'type' key"))
            log.tick("F")
            continue
        generator_module = f"perun.workload.{spec['type'].lower()}_generator"
        constructor_name = f"{spec['type'].title()}Generator"
        try:
            constructor = getattr(common_kit.get_module(generator_module), constructor_name)
            spec_map[spec["id"]] = GeneratorSpec(constructor, spec)
            log.tick()
        except (ImportError, AttributeError):
            warnings.append((spec["id"], f"{spec['type']} is not valid workload type"))
            log.tick("F")
    log.newline()

    # Print the warnings and badge
    if warnings:
        log.minor_fail("Workload generators")
        for workload_id, warning in warnings:
            log.minor_fail(f"workload {log.highlight(workload_id)}", warning)
    else:
        log.minor_success("Workload generators", "loaded")

    return spec_map
