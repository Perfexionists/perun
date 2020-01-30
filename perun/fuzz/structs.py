"""Collection of helpers structures for fuzzing"""
__author__ = 'Tomas Fiedor'


class FuzzingProgress:
    """Collection of statistics and states used during fuzzing

    :ivar list faults: list of workloads leading to faults
    :ivar list hangs: list of workloads leading to hangs
    :ivar list interesting_workloads: list of potentially interesting workloads
    :ivar list parents_fitness_values: list of fitness values for parents
    :ivar list final_results: list of final results
    :ivar int timeout: timeout of the fuzzing
    :ivar dict stats: additional stats of fuzz testing
    """
    def __init__(self, timeout):
        """
        :param int timeout: timeout for the fuzzing
        """
        self.faults = []
        self.hangs = []
        self.interesting_workloads = []
        self.parents_fitness_values = []
        self.final_results = []
        self.timeout = timeout
        self.stats = {
            "start_time": 0.0,
            "end_time": 0.0,
            "cov_execs": 0,
            "perun_execs": 0,
            "degradations": 0,
            "max_cov": 1.0,
            "coverage_testing": False,
            "worst-case": None,
            "hangs": 0,
            "faults": 0
        }
        self.base_cov = 1
