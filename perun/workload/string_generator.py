"""Generator of random strings"""

import random
import string

from perun.workload.generator import Generator

__author__ = 'Tomas Fiedor'


class StringGenerator(Generator):
    """Generator of random strings

    :ivar int min_len: minimal length of generated strings
    :ivar int max_len: maximal length of generated strings
    :ivar int step_len: increment of the lengths
    """
    def __init__(self, job, min_len, max_len, step=1):
        """Initializes the generator of string workloads

        :param job:
        :param min_len:
        :param max_len:
        :param step:
        """
        super().__init__(job)

        self.min_len = int(min_len)
        self.max_len = int(max_len)
        self.step_len = int(step)

    def _generate_next_workload(self):
        """Generates the next random string with increased length

        :return: random string of length in interval (min, max)
        """
        for str_len in range(self.min_len, self.max_len+1, self.step_len):
            yield "".join(
                random.choice(string.ascii_letters + string.digits + string.whitespace)
                for _ in range(str_len)
            )
