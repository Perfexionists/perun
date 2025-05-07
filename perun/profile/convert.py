"""``perun.profile.convert`` is a module which specifies interface for
conversion of profiles from :ref:`profile-spec` to other formats.

.. _pandas: https://pandas.pydata.org/

Run the following in the Python interpreter to extend the capabilities of
Python to different formats of profiles::

    import perun.profile.convert

Combined with ``perun.profile.factory``, ``perun.profile.query`` and e.g.
`pandas`_ library one can obtain efficient interpreter for executing more
complex queries and statistical tests over the profiles.
"""

from __future__ import annotations

# Standard Imports
from typing import TYPE_CHECKING, Any
import array
import operator

# Third-Party Imports
import numpy
import pandas

# Perun Imports
from perun.postprocess.regression_analysis import transform
from perun.profile import query
from perun.utils import log
from perun.utils.common import common_kit

if TYPE_CHECKING:
    from perun.profile.factory import Profile


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


def to_flame_graph_format(
    profile: Profile,
    profile_key: str = "amount",
    minimize: bool = False,
    squash_unknown: bool = True,
) -> list[str]:
    """Transforms the **memory** profile w.r.t. :ref:`profile-spec` into the
    format supported by perl script of Brendan Gregg.

    .. _Brendan Gregg's homepage: https://www.brendangregg.com/index.html

    :ref:`views-flame-graph` can be used to visualize the inclusive consumption
    of resources w.r.t. the call trace of the resource. It is useful for fast
    detection, which point at the trace is the hotspot (or bottleneck) in the
    computation. Refer to :ref:`views-flame-graph` for full capabilities of our
    Wrapper. For more information about flame graphs itself, please check
    `Brendan Gregg's homepage`_.

    Example of format is as follows::

        >>> print(''.join(convert.to_flame_graph_format(memprof)))
        malloc()~unreachable~0;main()~/home/user/dev/test.c~45 4
        valloc()~unreachable~0;main()~/home/user/dev/test.c~75;__libc_start_main()~unreachable~0 8
        main()~/home/user/dev/test02.c~79 156

    Each line corresponds to some collected resource (in this case amount of
    allocated memory) preceeded by its trace (i.e. functions or other unique
    identifiers joined using ``;`` character).

    :param profile: the memory profile
    :param profile_key: key that is used to obtain the data
    :param minimize: minimizes the uids
    :param squash_unknown: whether recursive [unknown] frames should be squashed into a single one
    :returns: list of lines, each representing one allocation call stack
    """
    stacks = []
    for _, snapshot in profile.all_snapshots():
        for alloc in snapshot:
            if "subtype" not in alloc.keys() or alloc["subtype"] != "free":
                # Workaround for total time used in some collectors, so it is not outputted
                if alloc["uid"] != "%TOTAL_TIME%" and profile_key in alloc:
                    stack = alloc.get("trace", [])
                    stack.append(alloc["uid"])
                    stack_str = ""
                    unknown_cnt = 0
                    for frame in reversed(stack):
                        line = to_uid(frame, minimize)
                        if squash_unknown:
                            # Fold unknown towers
                            if line == "[unknown]":
                                unknown_cnt += 1
                                continue
                            elif unknown_cnt > 0:
                                stack_str += "[unknown[squashed]];"
                                unknown_cnt = 0
                        stack_str += f"{line};"
                    # The unknown frame might have been the last one, in which case the frame was
                    # not yet added to the string.
                    if unknown_cnt > 0:
                        stack_str += "[unknown[squashed]];"
                    if stack_str:
                        stacks.append(f"{stack_str[:-1]} {alloc[profile_key]}\n")
    return stacks


def to_uid(record: dict[str, Any] | str, minimize: bool = False) -> str:
    """Retrieves uid from record

    :param record: record for which we are retrieving uid
    :return: single string representing uid
    """
    if isinstance(record, str):
        result = record
    else:
        result = to_string_line(record)
    return common_kit.hide_generics(result) if minimize else result


def to_string_line(frame: dict[str, Any] | str) -> str:
    """Create string representing call stack's frame

    :param frame: call stack's frame
    :return: line representing call stack's frame
    """
    if isinstance(frame, str):
        return frame
    elif "function" in frame.keys() and "source" in frame.keys() and "line" in frame.keys():
        return f"{frame['function']}()~{frame['source']}~{frame['line']}"
    else:
        assert "func" in frame.keys()
        return f"{frame['func']}"


def plot_data_from_coefficients_of(model: dict[str, Any]) -> dict[str, Any]:
    """Transform coefficients computed by
    :ref:`postprocessors-regression-analysis` into dictionary of points,
    plotable as a function or curve. This function serves as a public wrapper
    over regression analysis transformation function.

    :param model: the models dictionary from profile (refer to
        :pkey:`models`)
    :return: updated models dictionary extended with `plot_x` and
        `plot_y` lists
    """
    model.update(transform.coefficients_to_points(**model))
    return model


def flatten(flattened_value: Any) -> Any:
    """Converts the value to something that can be used as one value.

    Flattens the value to single level, lists are processed to comma separated representation and
    rest is left as it is.
    TODO: Add caching

    :param flattened_value: value that is flattened
    :returns: either decimal, string, or something else
    """
    # Dictionary is processed recursively according to the all items that are nested
    if isinstance(flattened_value, dict):
        nested_values = []
        for key, value in query.all_items_of(flattened_value):
            # Add one level of hierarchy with ':'
            nested_values.append((key, value))
        # Return the overall key as joined values of its nested stuff,
        # only if root is not a list (i.e. root key is not int = index)!
        nested_values.sort(key=common_kit.uid_getter)
        return ":".join(map(str, map(operator.itemgetter(1), nested_values)))
    # Lists are merged as comma separated keys
    elif isinstance(flattened_value, list):
        return ",".join(
            ":".join(str(nested_value[1]) for nested_value in query.flattened_values(i, lv))
            for (i, lv) in enumerate(flattened_value)
        )
    # Rest of the values are left as they are
    else:
        return flattened_value
