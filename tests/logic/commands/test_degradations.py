"""Basic tests for checking degradation between versions and profiles."""

import os
import git

import perun.profile.factory as factory
import perun.check as check
import perun.check.average_amount_threshold as aat
import perun.check.best_model_order_equality as bmoe

__author__ = 'Tomas Fiedor'


def test_degradation_in_minor(pcs_with_degradations, capsys):
    """Set of basic tests for testing degradation in concrete minor version point

    Expects correct behaviour
    """
    git_repo = git.Repo(pcs_with_degradations.vcs_path)
    head = str(git_repo.head.commit)

    check.degradation_in_minor(head)
    out, err = capsys.readouterr()
    assert "Degradation" in out
    assert err == ""


def test_degradation_in_history(pcs_with_degradations, capsys):
    """Set of basic tests for testing degradation in while history

    Expects correct behaviour
    """
    git_repo = git.Repo(pcs_with_degradations.vcs_path)
    head = str(git_repo.head.commit)

    check.degradation_in_history(head)
    out, err = capsys.readouterr()
    assert "Degradation" in out
    assert err == ""


def test_degradation_between_profiles(pcs_with_degradations, capsys):
    """Set of basic tests for testing degradation between profiles

    Expects correct behaviour
    """
    pool_path = os.path.join(os.path.split(__file__)[0], 'degradation_profiles')
    profiles = [
        factory.load_profile_from_file(os.path.join(pool_path, 'linear_base.perf'), True),
        factory.load_profile_from_file(os.path.join(pool_path, 'linear_base_degradated.perf'), True),
        factory.load_profile_from_file(os.path.join(pool_path, 'quad_base.perf'), True)
    ]
    # Cannot detect degradation using BMOE strategy betwen these pairs of profiles,
    # since the best models are same with good confidence
    result = list(bmoe.best_model_order_equality(profiles[0], profiles[1]))
    assert check.PerformanceChange.NoChange in [r.result for r in result]

    # Can detect degradation using BMOE strategy betwen these pairs of profiles
    result = list(bmoe.best_model_order_equality(profiles[1], profiles[2]))
    assert check.PerformanceChange.Degradation in [r.result for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    result = list(bmoe.best_model_order_equality(profiles[0], profiles[2]))
    assert check.PerformanceChange.Degradation in [r.result for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    result = list(aat.average_amount_threshold(profiles[1], profiles[2]))
    assert check.PerformanceChange.Degradation in [r.result for r in result]
    for deg in result:
        check.print_degradation_results(deg)


def test_strategies():
    """Set of basic tests for handling the strategies

    Expects correct behaviour
    """
    pool_path = os.path.join(os.path.split(__file__)[0], 'degradation_profiles')
    profile = factory.load_profile_from_file(os.path.join(pool_path, 'linear_base.perf'), True)
    rule = {
        'method': 'average_amount_threshold',
        'collector': 'complexity',
        'postprocessor': 'regression_analysis'
    }
    assert check.is_rule_applicable_for(rule, profile)

    rule = {
        'method': 'average_amount_threshold',
        'postprocessor': 'regression_analysis',
        'collector': 'complexity'
    }
    assert check.is_rule_applicable_for(rule, profile)

    rule = {
        'method': 'average_amount_threshold',
        'postprocessor': 'regression_analysis',
        'collector': 'memory'
    }
    assert not check.is_rule_applicable_for(rule, profile)

    rule = {
        'method': 'average_amount_threshold',
        'collector': 'complexity',
        'postprocessor': 'filter'
    }
    assert not check.is_rule_applicable_for(rule, profile)

    rule = {
        'method': 'average_amount_threshold',
        'collector': 'complexity',
        'cmd': 'bogus'
    }
    assert not check.is_rule_applicable_for(rule, profile)
