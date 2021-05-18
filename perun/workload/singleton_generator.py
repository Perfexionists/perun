"""Singleton Generator generates only one single value. This generator corresponds to the default
behaviour of Perun, i.e. when each specified workload in :munit:`workloads` was passed to profiled
program as string.

Currently be default, any string specified in :munit:`workloads`, that does not correspond to some
generator specified in :ckey:`generators.workload`, is converted to Singleton Generator.

The Singleton Generator can be configured by following options:

  * ``value``: singleton value that is passed as workload.

"""

from typing import Dict, Tuple, List, Any, Iterable

from perun.workload.generator import WorkloadGenerator
from perun.utils.structs import Job

__author__ = 'Tomas Fiedor'


class SingletonGenerator(WorkloadGenerator):
    """Generator of singleton values

    :ivar object value: singleton value used as workload
    """
    def __init__(self, job: Job, value: Any, **kwargs: Any):
        """Initializes the generator of singleton workload

        :param Job job: job for which we are generating the workloads
        :param object value: singleton value that is used as workload
        """
        super().__init__(job, **kwargs)

        self.value = value

    def _generate_next_workload(self) -> Iterable[Tuple[Any, Dict[str, Any]]]:
        """Generates the next integer as the workload

        :return: single value
        """
        yield self.value, {}
