"""Functions for converting native profiles to folded profiles."""

from __future__ import annotations

# Standard Imports
from typing import Any, Iterator, TYPE_CHECKING

# Third-Party Imports

# Perun Imports
from perun.utils.common import common_kit

if TYPE_CHECKING:
    from perun.profiles.native import Profile


def native_to_folded(
    profile: Profile,
    profile_key: str = "amount",
    agg_func: common_kit.Aggregations = common_kit.Aggregations.default(),
) -> Iterator[tuple[str, int]]:
    """Transforms the **memory** or **time** profile w.r.t. :ref:`profile-spec` into the
    folded format used, e.g., by flame graph scripts.

    .. _Brendan Gregg's homepage: https://www.brendangregg.com/index.html

    :ref:`views-flame-graph` can be used to visualize the inclusive consumption
    of resources w.r.t. the call trace of the resource. It is useful for fast
    detection, which point at the trace is the hotspot (or bottleneck) in the
    computation. Refer to :ref:`views-flame-graph` for full capabilities of our
    Wrapper. For more information about flame graphs itself, please check
    `Brendan Gregg's homepage`_.

    Example of format is as follows::

        >>> print(''.join(native_to_folded(memprof)))
        malloc()~unreachable~0;main()~/home/user/dev/test.c~45 4
        valloc()~unreachable~0;main()~/home/user/dev/test.c~75;__libc_start_main()~unreachable~0 8
        main()~/home/user/dev/test02.c~79 156

    Each line corresponds to some collected resource (in this case amount of
    allocated memory) preceded by its trace (i.e. functions or other unique
    identifiers joined using ``;`` character).

    :param profile: the memory/time profile
    :param profile_key: the key under which the measured consumption is stored
    :param agg_func: an aggregation to use when multiple measurements are present in time profiles

    :returns: an iterator over folded profile records of (stack_trace, consumption)
    """
    if profile["header"]["type"] == "memory":
        for _, snapshot in profile.all_snapshots():
            for alloc in snapshot:
                if "subtype" not in alloc.keys() or alloc["subtype"] != "free":
                    # Workaround for total time used in some collectors, so it is not outputted
                    if alloc["uid"] == "%TOTAL_TIME%" or profile_key not in alloc:
                        continue
                    stack: list[dict[str, Any]] = alloc.get("trace", alloc["uid"])
                    folded_record = ";".join((_to_string_line(frame) for frame in reversed(stack)))
                    yield folded_record, alloc[profile_key]
    else:
        agg_callable = common_kit.get_aggregation_callable(agg_func)
        for resource in profile.get_kperf_resources():
            yield resource["uid"], int(agg_callable(resource[profile_key]))


def _to_string_line(frame: dict[str, Any] | str) -> str:
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
