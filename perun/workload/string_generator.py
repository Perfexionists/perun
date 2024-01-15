"""String Generator generates strings of changing length.

The String Generators starts generating random strings starting from the ``min_len``, and
continuously increments this length by ``step_len`` (by default equal to 1), until it reaches
the ``max_len`` (including).

The following shows the example of integer generator, which continuously generates workload strings
of length 1, 2, ..., 9, 10:

  .. code-block:: yaml

      generators:
        workload:
          - id: string_generator
            type: string
            min_len: 1
            max_len: 10
            step_len: 1

The String Generator can be configured by following options:

  * ``min_len``: the minimal length of the string that shall be generated.
  * ``max_len``: the maximal length of the string that shall be generated.
  * ``step_len``: the step (or increment) of the lengths.

"""
from __future__ import annotations

# Standard Imports
from typing import Any, Iterable
import random
import string

# Third-Party Imports

# Perun Imports
from perun.utils.structs import Job
from perun.workload.generator import WorkloadGenerator


class StringGenerator(WorkloadGenerator):
    """Generator of random strings

    :ivar int min_len: minimal length of generated strings
    :ivar int max_len: maximal length of generated strings
    :ivar int step_len: increment of the lengths
    """

    __slots__ = ["min_len", "max_len", "step_len"]

    def __init__(
        self, job: Job, min_len: int, max_len: int, step_len: int = 1, **kwargs: Any
    ) -> None:
        """Initializes the generator of string workloads

        :param Job job: job for which we are generating the workloads
        :param int min_len: minimal length of the generated string
        :param int max_len: maximal length of the generated string
        :param int step_len: step for generating the strings
        :param dict kwargs: additional keyword arguments
        """
        super().__init__(job, **kwargs)

        self.min_len = int(min_len)
        self.max_len = int(max_len)
        self.step_len = int(step_len)

    def _generate_next_workload(self) -> Iterable[tuple[Any, dict[str, Any]]]:
        """Generates the next random string with increased length

        :return: random string of length in interval (min, max)
        """
        for str_len in range(self.min_len, self.max_len + 1, self.step_len):
            yield "".join(
                random.choice(string.ascii_letters + string.digits) for _ in range(str_len)
            ), {}
