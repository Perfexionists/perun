"""Simple generator that generates integer values from given interval"""

from perun.workload.generator import Generator

__author__ = 'Tomas Fiedor'


class IntegerGenerator(Generator):
    """Generator of integer values

    :ivar int min_range: the minimal value that should be generated
    :ivar int max_range: the maximal value that should be generated
    :ivar int step: the step of the integer generation
    """
    def __init__(self, job, min_range, max_range, step=1, **_):
        """Initializes the generator of integer workload

        :param Job job: job for which we are generating the workloads
        :param int min_range: the minimal value that should be generated
        :param int max_range: the maximal value that should be generated
        :param int step: step of the integer generator
        :param dict _: additional keyword arguments
        """
        super().__init__(job)

        self.min_range = int(min_range)
        self.max_range = int(max_range)
        self.step = int(step)

    def _generate_next_workload(self):
        """Generates the next integer as the workload

        :return: integer number from the given range and after given step
        """
        for integer in range(self.min_range, self.max_range+1, self.step):
            yield integer
