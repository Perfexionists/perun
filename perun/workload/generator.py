"""Generic object to be inherited from. Contains the basic method and API"""

import perun.utils.log as log

__author__ = 'Tomas Fiedor'


class Generator(object):
    """Base object for generation of the workloads

    :ivar Job job: job for which we are collecting the data
    :ivar str generator_name: name of the workload generator
    """
    def __init__(self, job, **_):
        """Initializes the job of the generator

        :param Job job: job for which we will initialize the generator
        :param dict _: additional keyword arguments
        """
        self.job = job
        self.generator_name = self.job.workload

    def generate(self, collect_function):
        """Collects the data for the generated workload

        TODO: Merge the workload stuff

        :return: tuple of collection status and collected profile
        """
        for workload in self._generate_next_workload():
            self.job.collector.params['workload'] = str(workload)
            self.job.workload = "{}_{}".format(self.generator_name, str(workload))
            c_status, prof = collect_function(self.job.collector, self.job)
            yield c_status, prof

    def _generate_next_workload(self):
        """Logs error, since each generator should generate the workloads in different ways"""
        log.error("using invalid generator: does not implement _generate_next_workload function!")
