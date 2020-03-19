"""External Generator calls the external file or script to generate input workloads

The External Generator generates workload as files using external executable generator.
The generator takes an executable as a parameter, that generates a set of workloads to
the `output_dir`. The generator then iterates through the directory with the generated
workloads. Note, that each workload has to conform to a file format specified by
`file_format`. The format contains delimited patters (e.g. `{width}`) that are extracted
to concrete values that are used in resources.

The following shows the example of an external generator, which continuously generates workloads
using external application called `genimg`, which generates images of different proportions:

  .. code-block:: yaml

      generators:
        workload:
          - id: external_generator
            type: external
            external_generator: ./genimg 10 20 2 ./data
            delimiters: {}
            file_format: genimg{width}_{height}.pgm
            output_dir: ./data

The External Generator can be configured by following options:

  * ``external_generator``: executable command, that generates workloads
  * ``file_format``: format of the generated file, that contains patterns wrapped fixed delimiter
    characters (by default corresponds to `{}`)
  * ``delimiters``: opening and closing delimiter that specifies the extracted workload parameters.
  * ``output_dir``: target directory, where generated workloads are stored

"""

import os
import subprocess

import perun.utils as utils
import perun.utils.log as log

from perun.workload.generator import Generator

__author__ = 'Tomas Fiedor'


class ExternalGenerator(Generator):
    """Generator of random text files

    :ivar int min_lines: minimal number of lines in generated text file
    """
    def __init__(self, job, external_generator, output_dir, file_format, delimiters='{}', **kwargs):
        """Initializes the generator of random text files

        :param Job job: job for which we are generating workloads
        :param dict kwargs: additional keyword arguments
        """
        super().__init__(job, **kwargs)

        self.generator = external_generator
        self.output_dir = output_dir
        self.file_format = file_format
        self.delimiters = delimiters

    def _generate_next_workload(self):
        """Generates next file workload

        TODO: Add parsing of generated files to real workload parameters

        :return: path to a file
        """
        try:
            utils.run_safely_external_command(self.generator, check_results=True)
        except subprocess.CalledProcessError as error:
            log.warn("External workload generator '{}' returned failed with: {}".format(
                self.generator, str(error)
            ))

        for workload in os.listdir(self.output_dir):
            path_to_workload = os.path.join(self.output_dir, workload)
            yield path_to_workload

