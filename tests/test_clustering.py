import itertools
import operator
import os
import copy
import pytest
from click.testing import CliRunner

import perun.cli as cli
import perun.utils.log as log
import perun.postprocess.clusterizer.run as clusterizer
import perun.logic.store as store
import perun.testing.utils as test_utils

import perun.testing.asserts as asserts


def test_from_cli(pcs_single_prof):
    """Tests running the clusterization from CLI"""
    object_dir = pcs_single_prof.get_job_directory()
    object_no = len(os.listdir(object_dir))
    runner = CliRunner()
    result = runner.invoke(cli.postprocessby, ["0@i", "clusterizer"])
    asserts.predicate_from_cli(result, result.exit_code == 0)

    # Test that something was created
    object_no_after = len(os.listdir(object_dir))
    assert object_no_after == object_no + 2

    # Test verbosity of printing the groups
    log.VERBOSITY = log.VERBOSE_DEBUG
    result = runner.invoke(cli.postprocessby, ["0@i", "clusterizer"])
    asserts.predicate_from_cli(result, result.exit_code == 0)


def test_sort_order():
    """Test sort order method"""
    full_profile = test_utils.load_profile(
        "full_profiles", "prof-3-memory-2017-05-15-15-43-42.perf"
    )
    clusterizer.postprocess(full_profile, "sort_order")


def get_malloced_resources(profile):
    """Helper function for getting resources that were allocated by malloc

    :param Profile profile: dictionary with resources
    :return: list of resources allocated by malloc
    """
    resources = list(map(operator.itemgetter(1), profile.all_resources()))
    resources.sort(key=clusterizer.resource_sort_key)
    malloced = []
    for group, members in itertools.groupby(resources, clusterizer.resource_group_key):
        if group[1] == "malloc":
            malloced.extend(list(members))
    return malloced


def test_sliding_window(pcs_single_prof):
    """Tests sliding window method"""
    runner = CliRunner()
    result = runner.invoke(cli.postprocessby, ["0@i", "clusterizer", "-s", "sliding_window"])
    asserts.predicate_from_cli(result, result.exit_code == 0)

    pool_path = os.path.join(os.path.split(__file__)[0], "profiles", "clustering_profiles")
    clustered_profile = store.load_profile_from_file(
        os.path.join(pool_path, "clustering-workload.perf"), True, unsafe_load=True
    )

    postprocessed_profile = copy.deepcopy(clustered_profile)
    params = {
        "window_width": 2,
        "width_measure": "absolute",
        "window_height": 4,
        "height_measure": "absolute",
    }
    clusterizer.postprocess(postprocessed_profile, "sliding_window", **params)
    malloced = get_malloced_resources(postprocessed_profile)
    # Assert we clustered resources to five clusters only
    assert max(res["cluster"] for res in malloced) == 5

    postprocessed_profile = copy.deepcopy(clustered_profile)
    params = {
        "window_width": 20,
        "width_measure": "absolute",
        "window_height": 40,
        "height_measure": "absolute",
    }
    clusterizer.postprocess(postprocessed_profile, "sliding_window", **params)
    malloced = get_malloced_resources(postprocessed_profile)
    # Assert we clustered resources to one clusters only, because the window is big
    assert max(res["cluster"] for res in malloced) == 1

    postprocessed_profile = copy.deepcopy(clustered_profile)
    params = {
        "window_width": 0.5,
        "width_measure": "relative",
        "window_height": 40,
        "height_measure": "absolute",
    }
    clusterizer.postprocess(postprocessed_profile, "sliding_window", **params)
    malloced = get_malloced_resources(postprocessed_profile)
    # Assert we clustered resources to two clusters only
    assert max(res["cluster"] for res in malloced) == 2

    # Try noexistant or unsupported options
    with pytest.raises(SystemExit):
        params = {
            "window_width": 0.5,
            "width_measure": "weighted",
            "window_height": 40,
            "height_measure": "absolute",
        }
        clusterizer.postprocess(postprocessed_profile, "sliding_window", **params)

    with pytest.raises(SystemExit):
        params = {
            "window_width": 0.5,
            "width_measure": "nonexistant",
            "window_height": 40,
            "height_measure": "absolute",
        }
        clusterizer.postprocess(postprocessed_profile, "sliding_window", **params)

    with pytest.raises(SystemExit):
        params = {
            "window_width": 0.5,
            "width_measure": "absolute",
            "window_height": 40,
            "height_measure": "nonexistant",
        }
        clusterizer.postprocess(postprocessed_profile, "sliding_window", **params)
