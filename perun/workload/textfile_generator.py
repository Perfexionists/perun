"""Text File Generator generates the range of random files.

The TextFile Generator generates files with random contents (lorem ipsum) starting from
``min_lines``, and continuously increments this value by ``step`` until the number of lines in
the generated file reaches ``max_lines``. Each row will then either have maximal length of
``max_chars`` (if ``randomize_rows`` is set to false value), otherwise the length is randomized
from the interval (``min_lines``, ``max_lines``).

The following shows the example of integer generator, which continuously generates workloads
10, 20, ..., 90, 100:

  .. code-block:: yaml

      generators:
        workload:
          - id: textfile_generator
            type: textfile
            min_lines: 10
            max_lines: 100
            step: 10

The TextFile Generator can be configured by following options:

  * ``min_lines``: the minimal number of lines in the file that shall be generated.
  * ``max_lines``: the maximal number of lines in the file that shall be generated.
  * ``step``: the step (or increment) of the range. By default set to 1.
  * ``min_chars``: the minimal number of characters on one line. By default set to 5.
  * ``max_chars``: the maximal number of characters on one line. By default set to 80.
  * ``randomize_rows``: by default set to True, the rows in the file have then randomized length
    from interval (``min_chars``, ``max_chars``). Otherwise (if set to false), the lines will always
    be of maximal length (``max_chars``).

"""
from __future__ import annotations

import distutils.util as dutils
import os
import tempfile
import random
import faker

from typing import Any, Iterable

from perun.workload.generator import WorkloadGenerator
from perun.utils.structs import Job


class TextfileGenerator(WorkloadGenerator):
    """Generator of random text files

    :ivar int min_lines: minimal number of lines in generated text file
    :ivar int max_lines: maximal number of lines in generated text file
    :ivar int step: step for lines in generated text file
    :ivar int min_chars: minimal number of rows/chars on one line in the text file
    :ivar int max_chars: maximal number of rows/chars on one line in the text file
    :ivar bool randomize_rows: if set to true, then the lines in the file will be
        randomized. Otherwise they will always be maximal.
    """

    def __init__(
        self,
        job: Job,
        min_lines: int,
        max_lines: int,
        step: int = 1,
        min_rows: int = 5,
        max_rows: int = 80,
        randomize_rows: bool = True,
        **kwargs: Any,
    ):
        """Initializes the generator of random text files

        :param Job job: job for which we are generating workloads
        :param int min_lines: minimal number of lines in generated text file
        :param int max_lines: maximal number of lines in generated text file
        :param int step: step for lines in generated text file
        :param int min_rows: minimal number of rows/chars on one line in the text file
        :param int max_rows: maximal number of rows/chars on one line in the text file
        :param bool randomize_rows: if set to true, then the lines in the file will be
            randomized. Otherwise they will always be maximal.
        :param dict kwargs: additional keyword arguments
        """
        super().__init__(job, **kwargs)

        # Line specific attributes
        self.min_lines = int(min_lines)
        self.max_lines = int(max_lines)
        self.step = int(step)

        # Row / Character specific
        # Note that faker has a lower limit on generated text.
        self.min_chars = max(int(min_rows), 5)
        self.max_chars = int(max_rows)
        self.randomize_rows = dutils.strtobool(str(randomize_rows))

        self.faker = faker.Faker()

    def _get_line(self) -> str:
        """Generates text of given length

        :return: one random line of lorem ipsum dolor text
        """
        line_len = (
            random.randint(self.min_chars, self.max_chars + 1)
            if self.randomize_rows
            else self.max_chars
        )
        return self.faker.text(max_nb_chars=line_len).replace("\n", " ")

    def _get_file_content(self, file_len: int) -> str:
        """Generates text file content for the file of given length

        :param int file_len: length of the generated file contents
        :return: content to be used in randomly generated file
        """
        return "\n".join(self._get_line() for _ in range(file_len))

    def _generate_next_workload(self) -> Iterable[tuple[str, dict[str, Any]]]:
        """Generates next file workload

        :return: path to a file
        """
        for file_len in range(self.min_lines, self.max_lines + 1, self.step):
            fd, path = tempfile.mkstemp()
            try:
                with os.fdopen(fd, "w") as tmpfile:
                    tmpfile.write(self._get_file_content(file_len))
                yield path, {}
            finally:
                os.remove(path)
