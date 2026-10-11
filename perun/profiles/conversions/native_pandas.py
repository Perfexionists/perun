"""Functions for converting native profiles to Pandas representations.

.. _pandas: https://pandas.pydata.org/
"""

from __future__ import annotations

# Standard Imports
import array
from typing import Any, TYPE_CHECKING

# Third-Party Imports
import numpy
import pandas

# Perun Imports
from perun.profiles.native import query
from perun.utils import log

if TYPE_CHECKING:
    from perun.profiles.native import Profile


def resources_to_pandas_dataframe(profile: Profile) -> pandas.DataFrame:
    """Converts the profile (w.r.t :ref:`profile-spec`) to format supported by
    `pandas`_ library.

    Queries through the resources in the `profile`, and flattens each
    key and value to the tabular representation. Refer to `pandas`_ library for
    more possibilities how to work with the tabular representation of collected
    resources.

    E.g. given `time` and `memory` profiles ``tprof`` and ``mprof``
    respectively, one can obtain the following formats::

        >>> convert.resources_to_pandas_dataframe(tprof)
           amount  snapshots   uid
        0  0.616s          0  real
        1  0.500s          0  user
        2  0.125s          0   sys

        >>> convert.resources_to_pandas_dataframe(mmprof)
            address  amount  snapshots subtype                   trace    type
        0  19284560       4          0  malloc  malloc:unreachabl...  memory
        1  19284560       0          0    free  free:unreachable:...  memory

                          uid uid:function  uid:line                 uid:source
        0  main:../memo...:22         main        22   ../memory_collect_test.c
        1  main:../memo...:27         main        27   ../memory_collect_test.c

    :param profile: dictionary with profile w.r.t. :ref:`profile-spec`
    :returns: converted profile to ``pandas.DataFramelist`` with resources
        flattened as a pandas dataframe
    """
    # Since some keys may be missing in the resources, we consider the possible fields
    resource_keys = list(profile.all_resource_fields())
    values: dict[str, list[Any] | array.array[float] | array.array[int]] = {
        key: [] for key in resource_keys
    }
    values["snapshots"] = array.array("I")

    # All resources at this point should be flat
    for snapshot, resource in log.progress(
        profile.all_resources(flatten_values=True), "Converting To Pandas"
    ):
        values["snapshots"].append(snapshot)
        for resource_key in resource_keys:
            values[resource_key].append(resource.get(resource_key, numpy.nan))

    return pandas.DataFrame(values)


def models_to_pandas_dataframe(profile: Profile) -> pandas.DataFrame:
    """Converts the models of profile (w.r.t :ref:`profile-spec`) to format
    supported by `pandas`_ library.

    Queries through all the models in the `profile`, and flattens each
    key and value to the tabular representation. Refer to `pandas`_ library for
    more possibilities how to work with the tabular representation of models.

    :param profile: dictionary with profile w.r.t. :ref:`profile-spec`
    :returns: converted models of profile to ``pandas.DataFramelist``
    """
    # Note that we need to this inefficiently, because some keys can be missing in resources
    model_keys = list(query.all_model_fields_of(profile))
    values: dict[str, list[Any]] = {key: [] for key in model_keys}

    for _, model in log.progress(profile.all_models(), description="Converting To Pandas"):
        flattened_resources = dict(list(query.all_items_of(model)))
        for model_key in model_keys:
            values[model_key].append(flattened_resources.get(model_key, numpy.nan))

    return pandas.DataFrame(values)
