""""""

from perun.workload.generator import Generator

__author__ = 'Tomas Fiedor'


class SingletonGenerator(Generator):
    """Generator of singleton values

    :ivar object value: singleton value used as workload
    """
    def __init__(self, job, value):
        """Initializes the generator of singleton workload

        :param Job job: job for which we are generating the workloads
        :param value: singleton value that is used as workload
        """
        super().__init__(job)

        self.value = value

    def _generate_next_workload(self):
        """Generates the next integer as the workload

        :return: single value
        """
        yield self.value
