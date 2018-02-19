"""Basic tests for checking degradation between versions and profiles."""

import os
import git

import perun.profile.factory as factory
import perun.check as check

__author__ = 'Tomas Fiedor'


def test_degradation_in_minor(pcs_with_degradations):
    """Set of basic tests for testing degradation in concrete minor version point

    Expects correct behaviour
    """
    git_repo = git.Repo(pcs_with_degradations.vcs_path)
    head = str(git_repo.head.commit)

    check.degradation_in_minor(head)


def test_degradation_in_history(pcs_with_degradations):
    """Set of basic tests for testing degradation in while history

    Expects correct behaviour
    """
    git_repo = git.Repo(pcs_with_degradations.vcs_path)
    head = str(git_repo.head.commit)

    check.degradation_in_history(head)


def test_degradation_between_profiles(pcs_with_degradations):
    """Set of basic tests for testing degradation between profiles

    Expects correct behaviour
    """
    pool_path = os.path.join(os.path.split(__file__)[0], 'degradation_profiles')
    profiles = [
        factory.load_profile_from_file(os.path.join(pool_path, 'linear_base.perf'), True),
        factory.load_profile_from_file(os.path.join(pool_path, 'linear_base_degradated.perf'), True),
        factory.load_profile_from_file(os.path.join(pool_path, 'quad_base.perf'), True)
    ]
    check.degradation_between_profiles(profiles[0], profiles[1])
    check.degradation_between_profiles(profiles[1], profiles[2])
    check.degradation_between_profiles(profiles[0], profiles[2])
