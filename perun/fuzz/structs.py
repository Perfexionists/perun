"""Collection of helpers structures for fuzzing"""
from __future__ import annotations

import os
from collections import namedtuple
from typing import Any, Optional

import perun.utils as utils
from perun.utils.decorators import always_singleton


TimeSeries = namedtuple("TimeSeries", "x_axis y_axis")
RuleSet = namedtuple("RuleSet", "rules hits")
GCOV_VERSION_W_INTER_FORMAT = 4.9
GCOV_VERSION_W_JSON_FORMAT = 9.0


class Mutation:
    """
    :ivar str path: path to the workload
    :ivar list history: list of predecessors
    :ivar Mutation predecessor: predecessor of the mutation (form which we mutated)
    :ivar int cov: achieved coverage
    :ivar float deg_ratio: achieved degradation ration
    :ivar float fitness: fitness of the mutation
    """

    def __init__(
        self,
        path: str,
        history: list[int],
        predecessor: Optional["Mutation"],
        cov: int = 0,
        deg_ratio: float = 0.0,
        fitness: float = 0.0,
    ):
        """
        :param str path: path to the workload
        :param list history: list of rules applied to get the mutation
        :param Optional["Mutation"] predecessor: predecessor of the mutation (from which we mutated)
        :param int cov: achieved coverage
        :param int deg_ratio: achieved degradation ration
        :param float fitness: fitness of the mutation
        """
        self.path: str = path
        self.history: list[int] = history
        self.predecessor: Optional["Mutation"] = predecessor
        self.cov: int = cov
        self.deg_ratio: float = deg_ratio
        self.fitness: float = fitness


@always_singleton
def get_gcov_version() -> int:
    """Checks the version of the gcov

    :return: version of the gcov
    """
    gcov_output, _ = utils.run_safely_external_command("gcov --version")
    return int((gcov_output.decode("utf-8").split("\n")[0]).split()[-1][0])


class CoverageConfiguration:
    """Configuration of the coverage testing

    :ivar str gcno_path: path to the directory, where .gcno files are stored
    :ivar str source_path: path to the directory, where source codes are stored
    :ivar int gcov_version: version of the gcov utility
    :ivar list gcov_files: list of gcov files
    :ivar list source_files: list of source files
    """

    def __init__(self, **kwargs: Any) -> None:
        """
        :param dict kwargs: set of keyword configurations
        """
        self.gcno_path: str = kwargs.get("gcno_path", ".")
        self.source_path: str = kwargs.get("source_path", ".")
        self.gcov_version: int = get_gcov_version()
        self.gcov_files: list[str] = []
        self.source_files: list[str] = []

    def has_intermediate_format(self) -> bool:
        """
        :return: true if the version of the gcov supports intermediate format
        """
        return GCOV_VERSION_W_INTER_FORMAT <= self.gcov_version < GCOV_VERSION_W_JSON_FORMAT

    def has_common_format(self) -> bool:
        """
        :return: true if the version of the gcov supports old format
        """
        return (
            self.gcov_version >= GCOV_VERSION_W_JSON_FORMAT
            or self.gcov_version < GCOV_VERSION_W_INTER_FORMAT
        )


class FuzzingConfiguration:
    """Collection of (mostly persistent) configuration of the fuzzing process

    This encapsulates all of the possibly used configurations to be passed around functions, in
    order to reduce the number of local variables and parameters.

    :ivar int timeout: specifies how long the fuzzing should be running
    :ivar int hang_timeout: specifies how long the tested program should run with the mutations
    :ivar str output_dir: directory, where resulting logs, workloads etc. are generated
    :ivar str workloads_filter: regular expression used to filter workloads
    :ivar list regex_rules: list of user defined rules (described by regular expressions)
    :ivar int max: maximal size of the generated workloads in B
    :ivar int max_size_ratio: maximal percentual increase in the size of the workloads
    :ivar int max_size_gain: the maximal increase in size of the mutated workload, in comparison
        with input seeds.
    :ivar int exec_limit: limit to number of execution of number of mutation per fuzzing loop
    :ivar int precollect_limit: limit for number of generated mutations per fuzzing loop
    :ivar int mutations_per_rule: strategy used for determining how many workloads will be generated
        per mutation rule.
    :ivar bool no_plotting: specifies if the result of the fuzzing should be plotted by graphs
    :ivar int cov_rate: threshold for the increase of the coverage
    :ivar bool coverage_testing: specifies if the mutations should be tested for coverage also,
        or only using perun
    """

    def __init__(self, **kwargs: Any) -> None:
        """
        :param dict kwargs: set of keyword configurations
        """
        self.timeout: float = kwargs.get("timeout", 0.0)
        self.hang_timeout: float = kwargs.get("hang_timeout", 0.0)
        self.output_dir: str = os.path.abspath(kwargs["output_dir"])
        self.workloads_filter: str = kwargs.get("workloads_filter", "")
        self.regex_rules: dict[str, str] = kwargs.get("regex_rules", {})
        self.max_size: Optional[int] = kwargs.get("max_size", None)
        self.max_size_ratio: Optional[int] = kwargs.get("max_size_ratio", None)
        self.max_size_gain: int = kwargs.get("max_size_gain", 0)
        self.exec_limit: int = kwargs.get("exec_limit", 0)
        self.precollect_limit: int = kwargs.get("interesting_files_limit", 0)
        self.mutations_per_rule: str = kwargs.get("mutations_per_rule", "mixed")
        self.no_plotting: bool = kwargs.get("no_plotting", False)
        self.cov_rate: float = kwargs.get("coverage_increase_rate", 1.5)
        self.coverage_testing: bool = not kwargs.get("skip_coverage_testing", False)
        self.coverage: CoverageConfiguration = CoverageConfiguration(**kwargs)

    RATIO_INCR_CONST = 0.05
    RATIO_DECR_CONST = 0.01

    def refine_coverage_rate(self, found_workloads: list[Mutation]) -> None:
        """Refines the coverage rate according to so far founded interesting workloads

        :param list found_workloads: list of interesting workloads
        """
        if found_workloads:
            self.cov_rate += FuzzingConfiguration.RATIO_INCR_CONST
        elif self.cov_rate > FuzzingConfiguration.RATIO_DECR_CONST:
            self.cov_rate -= FuzzingConfiguration.RATIO_DECR_CONST


class FuzzingProgress:
    """Collection of statistics and states used during fuzzing

    :ivar list faults: list of workloads leading to faults
    :ivar list hangs: list of workloads leading to hangs
    :ivar list interesting_workloads: list of potentially interesting workloads
    :ivar list parents: list of fitness values for parents
    :ivar list final_results: list of final results
    :ivar int timeout: timeout of the fuzzing
    :ivar dict stats: additional stats of fuzz testing
    """

    def __init__(self) -> None:
        """ """
        self.faults: list[Mutation] = []
        self.hangs: list[Mutation] = []
        self.interesting_workloads: list[Mutation] = []
        self.parents: list[Mutation] = []
        self.final_results: list[Mutation] = []

        # Time series plotting
        self.deg_time_series: TimeSeries = TimeSeries([0], [0])
        self.cov_time_series: TimeSeries = TimeSeries([0], [1.0])

        self.base_cov: int = 1

        self.stats: dict[str, Any] = {
            "start_time": 0.0,
            "end_time": 0.0,
            "cov_execs": 0,
            "perun_execs": 0,
            "degradations": 0,
            "max_cov": 1.0,
            "worst_case": None,
            "hangs": 0,
            "faults": 0,
        }

    def update_max_coverage(self) -> None:
        """Updates the maximal achieved coverage according to the parent fitness values"""
        self.stats["max_cov"] = self.parents[-1].cov / self.base_cov
