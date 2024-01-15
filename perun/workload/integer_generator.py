"""Integer Generator generates the range of the integers.

The Integer Generator starts from the ``min_range`` workload, and continuously increments this
value by ``step`` (by default equal to 1) until it reaches max_range (including).

The following shows the example of integer generator, which continuously generates workloads
10, 20, ..., 90, 100:

  .. code-block:: yaml

      generators:
        workload:
          - id: integer_generator
            type: integer
            min_range: 10
            max_range: 100
            step: 10

The Integer Generator can be configured by following options:

  * ``min_range``: the minimal integer value that shall be generated.
  * ``max_range``: the maximal integer value that shall be generated.
  * ``step``: the step (or increment) of the range.

"""
from __future__ import annotations

# Standard Imports
from typing import Any, Iterable

# Third-Party Imports

# Perun Imports
from perun.utils.structs import Job
from perun.workload.generator import WorkloadGenerator


class IntegerGenerator(WorkloadGenerator):
    """Generator of integer values

    :ivar int min_range: the minimal value that should be generated
    :ivar int max_range: the maximal value that should be generated
    :ivar int step: the step of the integer generation
    """

    __slots__ = ["min_range", "max_range", "step"]

    def __init__(self, job: Job, min_range: int, max_range: int, step: int = 1, **kwargs: Any):
        """Initializes the generator of integer workload

        :param Job job: job for which we are generating the workloads
        :param int min_range: the minimal value that should be generated
        :param int max_range: the maximal value that should be generated
        :param int step: step of the integer generator
        :param dict kwargs: additional keyword arguments
        """
        super().__init__(job, **kwargs)

        self.min_range = int(min_range)
        self.max_range = int(max_range)
        self.step = int(step)

    def _generate_next_workload(self) -> Iterable[tuple[Any, dict[str, Any]]]:
        """Generates the next integer as the workload

        :return: integer number from the given range and after given step
        """
        for integer in range(self.min_range, self.max_range + 1, self.step):
            yield integer, {}
