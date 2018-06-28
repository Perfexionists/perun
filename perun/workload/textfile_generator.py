"""Generator of random text files"""

import os
import tempfile
import random
import faker

from perun.workload.generator import Generator

__author__ = 'Tomas Fiedor'


class TextfileGenerator(Generator):
    """Generator of random text files

    :ivar int min_lines: minimal number of lines in generated text file
    :ivar int max_lines: maximal number of lines in generated text file
    :ivar int step: step for lines in generated text file
    :ivar int min_chars_in_row: minimal number of rows/chars on one line in the text file
    :ivar int max_chars_in_row: maximal number of rows/chars on one line in the text file
    :ivar bool randomize_rows: if set to true, then the lines in the file will be
        randomized. Otherwise they will always be maximal.
    :ivar Faker faker: faker of the data
    """
    def __init__(self, job, min_lines, max_lines, step=1, min_rows=5, max_rows=80,
                 randomize_rows=True):
        """Initializes the generator of random text files

        :param Job job: job for which we are generating workloads
        :param int min_lines: minimal number of lines in generated text file
        :param int max_lines: maximal number of lines in generated text file
        :param int step: step for lines in generated text file
        :param int min_rows: minimal number of rows/chars on one line in the text file
        :param int max_rows: maximal number of rows/chars on one line in the text file
        :param bool randomize_rows: if set to true, then the lines in the file will be
            randomized. Otherwise they will always be maximal.
        """
        super().__init__(job)

        # Line specific attributes
        self.min_lines = min_lines
        self.max_lines = max_lines
        self.step = step

        # Row / Character specific
        # Note that faker has a lower limit on generated text.
        self.min_chars_in_row = max(min_rows, 5)
        self.max_chars_in_row = max_rows
        self.randomize_rows = randomize_rows

        self.faker = faker.Faker()

    def _get_line(self):
        """Generates text of given length

        :return: one random line of lorem ipsum dolor text
        """
        line_len = random.randint(self.min_chars_in_row, self.max_chars_in_row + 1) \
            if self.randomize_rows else self.max_chars_in_row
        return self.faker.text(max_nb_chars=line_len).replace('\n', ' ')

    def _get_file_content(self, file_len):
        """Generates text file content for the file of given length

        :param int file_len: length of the generated file contents
        :return: content to be used in randomly generated file
        """
        return "\n".join(
            self._get_line() for _ in range(file_len)
        )

    def _generate_next_workload(self):
        """Generates next file workload

        :return: path to a file
        """
        for file_len in range(self.min_lines, self.max_lines + 1):
            fd, path = tempfile.mkstemp()
            try:
                print("Generating {}".format(path))
                with os.fdopen(fd, 'w') as tmpfile:
                    tmpfile.write(self._get_file_content(file_len))
                yield path
            finally:
                os.remove(path)
