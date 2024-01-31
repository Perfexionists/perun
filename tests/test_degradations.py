"""Basic tests for checking degradation between versions and profiles."""
from __future__ import annotations

# Standard Imports
import os

# Third-Party Imports
import git
import pytest

# Perun Imports
from perun.check.methods.abstract_base_checker import AbstractBaseChecker
from perun.logic import config, store
from perun.utils import log
from perun.utils.exceptions import UnsupportedModuleException
import perun.check.factory as check


def test_degradation_precollect(monkeypatch, pcs_with_degradations, capsys):
    """Set of basic tests for testing degradation in concrete minor version point

    Expects correct behaviour
    """
    matrix = config.Config(
        "local",
        "",
        {
            "vcs": {"type": "git", "url": "../"},
            "cmds": ["ls -al"],
            "workloads": [".", ".."],
            "collectors": [{"name": "time", "params": {"warmup": 1, "repeat": 1}}],
            "postprocessors": [],
            "execute": {
                "pre_run": [
                    'ls | grep "."',
                ]
            },
            "degradation": {
                "collect_before_check": "true",
                "apply": "first",
                "strategies": [{"method": "aat"}],
            },
        },
    )
    monkeypatch.setattr("perun.logic.config.local", lambda _: matrix)
    git_repo = git.Repo(pcs_with_degradations.get_vcs_path())
    head = str(git_repo.head.commit)

    check.degradation_in_minor(head)
    _, err = capsys.readouterr()
    assert err == ""

    def raise_sysexit(*_):
        """Raises System Exit ;)"""
        raise SystemExit()

    check.pre_collect_profiles.minor_version_cache.clear()
    monkeypatch.setattr("perun.logic.runner.run_matrix_job", raise_sysexit)
    check.degradation_in_minor(head)
    out, err = capsys.readouterr()
    assert err == ""


def test_degradation_in_minor(pcs_with_degradations, capsys):
    """Set of basic tests for testing degradation in concrete minor version point

    Expects correct behaviour
    """
    git_repo = git.Repo(pcs_with_degradations.get_vcs_path())
    head = str(git_repo.head.commit)

    check.degradation_in_minor(head)
    out, err = capsys.readouterr()
    assert "Optimization" in out
    assert err == ""


def test_degradation_in_history(pcs_with_degradations):
    """Set of basic tests for testing degradation in while history

    Expects correct behaviour
    """
    git_repo = git.Repo(pcs_with_degradations.get_vcs_path())
    head = str(git_repo.head.commit)

    result = check.degradation_in_history(head)
    assert check.PerformanceChange.Degradation in [r[0].result for r in result]


def test_degradation_between_profiles(pcs_with_root, capsys):
    """Set of basic tests for testing degradation between profiles

    Expects correct behaviour
    """
    pool_path = os.path.join(os.path.split(__file__)[0], "profiles", "degradation_profiles")
    profiles = [
        store.load_profile_from_file(os.path.join(pool_path, "linear_base.perf"), True, True),
        store.load_profile_from_file(
            os.path.join(pool_path, "linear_base_degradated.perf"), True, True
        ),
        store.load_profile_from_file(os.path.join(pool_path, "quad_base.perf"), True, True),
        store.load_profile_from_file(os.path.join(pool_path, "zero.perf"), True, True),
    ]
    tracer_profiles = [
        store.load_profile_from_file(os.path.join(pool_path, "tracer_baseline.perf"), True, True),
        store.load_profile_from_file(os.path.join(pool_path, "tracer_target.perf"), True, True),
    ]

    # Test degradation detection using ETO
    result = list(
        check.run_degradation_check(
            "exclusive_time_outliers", tracer_profiles[0], tracer_profiles[1]
        )
    )
    expected_changes = {
        check.PerformanceChange.TotalDegradation,
        check.PerformanceChange.NoChange,
    }
    assert expected_changes & set(r.result for r in result)

    # Test degradation detection using ETO on the same profile - no Degradation should be found.
    result = list(
        check.run_degradation_check(
            "exclusive_time_outliers", tracer_profiles[0], tracer_profiles[0]
        )
    )
    # We allow TotalDegradation and TotalOptimization since one them is always reported
    allowed = {
        check.PerformanceChange.NoChange,
        check.PerformanceChange.TotalDegradation,
        check.PerformanceChange.TotalOptimization,
    }
    # No other result should be present here
    assert not set(r.result for r in result) - allowed

    # Cannot detect degradation using BMOE strategy betwen these pairs of profiles,
    # since the best models are same with good confidence
    result = list(
        check.run_degradation_check("best_model_order_equality", profiles[0], profiles[1])
    )
    assert check.PerformanceChange.NoChange in [r.result for r in result]

    # Can detect degradation using BMOE strategy betwen these pairs of profiles
    result = list(
        check.run_degradation_check("best_model_order_equality", profiles[1], profiles[2])
    )
    assert check.PerformanceChange.Degradation in [r.result for r in result]

    result = list(
        check.run_degradation_check("best_model_order_equality", profiles[0], profiles[2])
    )
    assert check.PerformanceChange.Degradation in [r.result for r in result]

    result = list(check.run_degradation_check("average_amount_threshold", profiles[1], profiles[2]))
    assert check.PerformanceChange.Degradation in [r.result for r in result]

    # Can detect optimizations both using BMOE and AAT and Fast
    result = list(check.run_degradation_check("average_amount_threshold", profiles[2], profiles[1]))
    assert check.PerformanceChange.Optimization in [r.result for r in result]

    result = list(check.run_degradation_check("fast_check", profiles[2], profiles[1]))
    assert check.PerformanceChange.MaybeOptimization in [r.result for r in result]

    result = list(
        check.run_degradation_check("best_model_order_equality", profiles[2], profiles[1])
    )
    assert check.PerformanceChange.Optimization in [r.result for r in result]

    # Try that we printed confidence
    deg_list = [(res, "", "") for res in result]
    log.print_list_of_degradations(deg_list)
    out, _ = capsys.readouterr()
    assert "with confidence" in out

    # Try that nothing is wrong when the average is 0.0
    result = list(check.run_degradation_check("average_amount_threshold", profiles[3], profiles[3]))
    # Assert that DegradationInfo was yield
    assert result
    # Assert there was no change
    assert check.PerformanceChange.NoChange in [r.result for r in result]

    # Test incompatible profiles
    pool_path = os.path.join(os.path.split(__file__)[0], "profiles", "full_profiles")
    lhs = store.load_profile_from_file(
        os.path.join(pool_path, "prof-1-time-2017-03-19-19-17-36.perf"), True, True
    )
    rhs = store.load_profile_from_file(
        os.path.join(pool_path, "prof-3-memory-2017-05-15-15-43-42.perf"), True, True
    )
    with pytest.raises(SystemExit):
        check.degradation_between_files(lhs, rhs, "HEAD", "all")
    _, err = capsys.readouterr()
    assert "incompatible configurations" in err

    # Try that unknown
    with pytest.raises(UnsupportedModuleException):
        _ = list(check.run_degradation_check("unknown", profiles[3], profiles[3]))


def test_strategies():
    """Set of basic tests for handling the strategies

    Expects correct behaviour
    """
    pool_path = os.path.join(os.path.split(__file__)[0], "profiles", "degradation_profiles")
    profile = store.load_profile_from_file(os.path.join(pool_path, "linear_base.perf"), True, True)
    rule = {
        "method": "average_amount_threshold",
        "collector": "complexity",
        "postprocessor": "regression_analysis",
    }
    assert check.is_rule_applicable_for(rule, profile)

    rule = {
        "method": "average_amount_threshold",
        "postprocessor": "regression_analysis",
        "collector": "complexity",
    }
    assert check.is_rule_applicable_for(rule, profile)

    rule = {
        "method": "average_amount_threshold",
        "postprocessor": "regression_analysis",
        "collector": "memory",
    }
    assert not check.is_rule_applicable_for(rule, profile)

    rule = {
        "method": "average_amount_threshold",
        "collector": "complexity",
        "postprocessor": "normalizer",
    }
    assert not check.is_rule_applicable_for(rule, profile)

    rule = {
        "method": "average_amount_threshold",
        "collector": "complexity",
        "cmd": "bogus",
    }
    assert not check.is_rule_applicable_for(rule, profile)


def test_base_check():
    """Dummy test, that base selection is correctly installed and cannot be instantiated"""
    with pytest.raises(TypeError):
        _ = AbstractBaseChecker()
