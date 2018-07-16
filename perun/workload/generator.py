"""Generic object to be inherited from. Contains the basic method and API"""

import perun.utils.log as log
import perun.profile.factory as profile

from perun.utils.helpers import CollectStatus

__author__ = 'Tomas Fiedor'


class Generator(object):
    """Base object for generation of the workloads

    :ivar Job job: job for which we are collecting the data
    :ivar str generator_name: name of the workload generator
    """
    def __init__(self, job, profile_for_each_workload=False, **_):
        """Initializes the job of the generator

        :param Job job: job for which we will initialize the generator
        :param bool profile_for_each_workload: if set to true, then we will generate one profile
            for each workload, otherwise the workload will be merged into one single profile
        :param dict _: additional keyword arguments
        """
        self.job = job
        self.generator_name = self.job.workload
        self.for_each = profile_for_each_workload

    def generate(self, collect_function):
        """Collects the data for the generated workload

        TODO: Merge the workload stuff

        :return: tuple of collection status and collected profile
        """
        collective_profile, collective_status = {}, CollectStatus.OK

        for workload in self._generate_next_workload():
            self.job.collector.params['workload'] = str(workload)
            self.job.workload = "{}_{}".format(self.generator_name, str(workload)) \
                if self.for_each else self.generator_name
            c_status, prof = collect_function(self.job.collector, self.job)
            if self.for_each:
                yield c_status, prof
            else:
                collective_status = \
                    CollectStatus.ERROR if collective_status == CollectStatus.ERROR else c_status
                collective_profile = profile.merge_resources_of(collective_profile, prof)

        if collective_profile:
            yield collective_status, collective_profile

    def _generate_next_workload(self):
        """Logs error, since each generator should generate the workloads in different ways"""
        log.error("using invalid generator: does not implement _generate_next_workload function!")
