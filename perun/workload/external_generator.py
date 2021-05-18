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

from typing import Dict, Tuple, List, Any, Iterable

import perun.utils as utils
import perun.utils.log as log
import perun.utils.helpers as helpers

from perun.workload.generator import WorkloadGenerator
from perun.utils.structs import Job

__author__ = 'Tomas Fiedor'


class ExternalGenerator(WorkloadGenerator):
    """Generator of random text files

    :ivar str generator: string that is executed and that generates into @p output_dir list of
        generated workloads
    :ivar str output_dir: path to the directory, where the externally generated workloads will
        be stored
    :ivar str file_format: format of the generated workloads, that contains short format string
        delimited by pair of opening and closing @p delimiters (e.g. {width}). The format strings
        are used to extract concrete values that are set for each resource in the measured program.
    :ivar str delimiters: pair of delimiters used to delimit the formatting strings/patters
    :ivar list splits: list of fixed patters of the generated filenames, that are used to extract
        collectable/persistent parts for the resources
    :ivar list key: list of keys for extracted resources
    """
    def __init__(self, job: Job, external_generator: str, output_dir: str, file_format: str,
                 delimiters: str = '{}', **kwargs: Any):
        """Initializes the generator of random text files

        :param Job job: job for which we are generating workloads
        :param str generator: string that is executed and that generates into @p output_dir list of
            generated workloads
        :param str output_dir: path to the directory, where the externally generated workloads will
            be stored
        :param str file_format: format of the generated workloads, that contains short format string
            delimited by pair of opening and closing @p delimiters (e.g. {width}). The format
            strings are used to extract concrete values that are set for each resource in the
            measured program.
        :param str delimiters: pair of delimiters used to delimit the formatting strings/patters
        :param dict kwargs: additional keyword arguments
        """
        super().__init__(job, **kwargs)

        self.generator = external_generator
        self.output_dir = output_dir
        self.file_format = file_format
        self.delimiters = delimiters
        self.splits, self.keys = self._parse_workload_keys()

    def _parse_workload_keys(self) -> Tuple[List[str], List[str]]:
        """Splits the workload format into fixed parts (splits) and format parts (keys)

        The format of the workload is specified using a set of delimited format keys. E.g.
        'generated_{w}_{h}.img' contains three fixed splits (['generated_', '_', '.img']) and
        two keys (['w', 'h']). The function splits the workload format into the parts above.

        :return: parsed workload format
        """
        split_format = [
            token for split in self.file_format.split(self.delimiters[0])
            for token in split.split(self.delimiters[1])
        ]
        return split_format[0::2], split_format[1::2]

    def _parse_workload_values(self, workload: str) -> List[Any]:
        """Parses the real workload into a set of concrete amounts of resources.

        Each generated workload can contain further resources coded in the filename based on
        the format string. This attempts to find concrete values to `self.keys` patters.
        The function tries to convert the values either to int or float (hence they will
        be considered as collectable resources), otherwise they are stored as string (hence they
        will be considered as persistent resources)

        :param str workload: real workload
        :return: parsed concrete values of the workload
        """
        values = []
        for split in self.splits:
            if split:
                try:
                    val, workload = workload.split(split, maxsplit=1)
                    if val:
                        values.append(helpers.try_convert(val, [int, float]))
                except ValueError:
                    return []
        # Handling the case when the pattern is at the end of the string and hence split is empty
        if workload:
            values.append(helpers.try_convert(workload, [int, float]))
        return values

    def _generate_next_workload(self) -> Iterable[Tuple[Any, Dict[str, Any]]]:
        """Generates next file workload

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
            values = self._parse_workload_values(workload)
            if len(values) == len(self.keys):
                yield path_to_workload, {key: value for (key, value) in zip(self.keys, values)}
            else:
                log.warn("Could not match format '{}' for workload file '{}'".format(
                    self.file_format, workload
                ))
                yield path_to_workload, {}

