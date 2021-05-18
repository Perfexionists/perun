"""All generators can be configured using the following generic settings:

  * ``profile_for_each_workload``: by default this option is set to false, and then when one uses
    the generator to generate the workload, the collected resources will be merged into one single
    profile. If otherwise this option is set to true value (true, 1, yes, etc.) then Perun will
    generate profile for each of the generated workload.

"""

import distutils.util as dutils

from typing import Dict, Tuple, Any, Union, Callable, Iterable

import perun.logic.config as config
import perun.utils.log as log
import perun.profile.helpers as profile
import perun.profile.factory as factory

from perun.utils.structs import CollectStatus, Job
from perun.profile.factory import Profile

__author__ = 'Tomas Fiedor'


class WorkloadGenerator:
    """Generator is a base object of all generators and contains generic options for all generators.

    :ivar bool profile_for_each_workload: if set to true, then we will generate one profile
        for each workload, otherwise the workload will be merged into one single profile
    """
    def __init__(self, job: Job, profile_for_each_workload: bool = False, **_):
        """Initializes the job of the generator

        :param Job job: job for which we will initialize the generator
        :param bool profile_for_each_workload: if set to true, then we will generate one profile
            for each workload, otherwise the workload will be merged into one single profile
        :param dict _: additional keyword arguments
        """
        self.job = job
        self.generator_name = self.job.executable.origin_workload
        self.for_each = dutils.strtobool(str(profile_for_each_workload))

    def generate(self,
                 collect_function: Callable[[str, Job], Tuple[CollectStatus, Union[dict, Profile]]]
                 ) -> Iterable[Tuple[CollectStatus, Union[dict, Profile]]]:
        """Collects the data for the generated workload

        :return: tuple of collection status and collected profile
        """
        collective_profile, collective_status = factory.Profile(), CollectStatus.OK

        for workload, workload_ctx in self._generate_next_workload():
            config.runtime().set('context.workload', workload_ctx)
            self.job.collector.params['workload'] = str(workload)
            # Update the workload: the executed one (workload) and config one (origin_workload)
            self.job.executable.workload = str(workload)
            self.job.executable.origin_workload = "{}_{}".format(
                self.generator_name, str(workload)
            ) if self.for_each else self.generator_name
            c_status, prof = collect_function(self.job.collector, self.job)
            if self.for_each:
                yield c_status, prof
            else:
                collective_status = \
                    CollectStatus.ERROR if collective_status == CollectStatus.ERROR else c_status
                collective_profile = profile.merge_resources_of(collective_profile, prof)

        if not self.for_each:
            yield collective_status, collective_profile

    def _generate_next_workload(self) -> Iterable[Tuple[Any, Dict[str, Any]]]:
        """Logs error, since each generator should generate the workloads in different ways

        :return: tuple of generated workload and deeper workload context (used when contructing
            resources that will be added to profile)
        """
        yield from ()
        log.error("using invalid generator: does not implement _generate_next_workload function!")
