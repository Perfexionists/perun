"""Collections of test for perun.select package"""
from __future__ import annotations

# Standard Imports
import git
import pytest

# Third-Party Imports

# Perun Imports
from perun.logic import pcs
from perun.profile import helpers as profile_helpers
from perun.select.abstract_base_selection import AbstractBaseSelection
from perun.select.whole_repository_selection import WholeRepositorySelection


def test_base_select():
    """Dummy test, that base selection is correctly installed and cannot be instantiated"""
    with pytest.raises(TypeError):
        _ = AbstractBaseSelection()


def test_whole_repository(pcs_with_degradations):
    git_repo = git.Repo(pcs_with_degradations.get_vcs_path())

    head = pcs.vcs().get_minor_version_info(str(git_repo.head.commit))
    parent = pcs.vcs().get_minor_version_info(head.parents[0])
    second_parent = pcs.vcs().get_minor_version_info(head.parents[1])
    root = pcs.vcs().get_minor_version_info(parent.parents[0])

    head_profile = profile_helpers.load_list_for_minor_version(head.checksum)[0].load()
    root_profile = profile_helpers.load_list_for_minor_version(root.checksum)[0].load()

    whole_select = WholeRepositorySelection()
    assert whole_select.should_check_version(head) == (True, 1)
    assert whole_select.should_check_version(parent) == (True, 1)
    assert whole_select.should_check_versions(head, parent) == (True, 1)
    assert whole_select.should_check_profiles(head_profile, root_profile) == (True, 1)

    assert whole_select.find_nearest(head) == head
    assert whole_select.find_nearest(parent) == parent
    assert whole_select.find_nearest(root) == root

    selected_parents = whole_select.get_parents(head)
    assert parent in selected_parents
    assert second_parent in selected_parents

    selected_profiles = whole_select.get_profiles(head, head_profile)
    assert len(selected_profiles) == 1
    assert selected_profiles[0][0] == second_parent

    skeleton = list(whole_select.get_skeleton(head))
    assert len(skeleton) == 4
    assert head in skeleton
    assert parent in skeleton
    assert second_parent in skeleton
    assert root in skeleton

    skeleton = list(whole_select.get_skeleton_for_profile(head, head_profile))
    assert len(skeleton) == 3
