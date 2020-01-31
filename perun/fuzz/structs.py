"""Collection of helpers structures for fuzzing"""

from collections import namedtuple

__author__ = 'Tomas Fiedor'


TimeSeries = namedtuple("TimeSeries", "x_axis y_axis")
RuleSet = namedtuple("RuleSet", "rules hits")


class Mutation:
    """
    :ivar str path: path to the workload
    :ivar list history: list of predecessors
    :ivar Mutation predecessor: predecessor of the mutation (form which we mutated)
    :ivar int cov: achieved coverage
    :ivar int deg_ratio: achieved degradation ration
    :ivar float fitness: fitness of the mutation
    """
    def __init__(self, path, history, predecessor, cov=0, deg_ratio=0, fitness=0):
        """
        :param str path: path to the workload
        :param list history: list of predecessors
        :param Mutation predecessor: predecessor of the mutation (form which we mutated)
        :param int cov: achieved coverage
        :param int deg_ratio: achieved degradation ration
        :param float fitness: fitness of the mutation
        """
        self.path = path
        self.history = history
        self.predecessor = predecessor
        self.cov = cov
        self.deg_ratio = deg_ratio
        self.fitness = fitness


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

        # Time series plotting
        self.deg_time_series = TimeSeries([0], [0])
        self.cov_time_series = TimeSeries([0], [1.0])

        self.base_cov = 1

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

    def update_max_coverage(self):
        """Updates the maximal achieved coverage according to the parent fitness values"""
        self.stats["max_cov"] = self.parents_fitness_values[-1].cov / self.base_cov
