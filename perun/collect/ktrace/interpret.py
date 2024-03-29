from __future__ import annotations

# Standard Imports
from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any, Generic, TypeVar, Type, Literal
import itertools
import os
import pathlib
import struct

# Third-Party Imports
import pandas as pd
import progressbar

# Perun Imports
from perun.utils import log


NS_TO_MS = 1000000


DataT = TypeVar("DataT", bound="FuncData")


def fold_recursive_calls_in_trace(trace: list[str], generalize=False):
    """Folds consecutive recursive calls to single uid

    TODO: REMOVE TEMPORARY AFTER MERGING OF UNMERGED BRANCH

    If generalize is set to True, then each consecutive calls to certain UID will be
    folded to ^*, otherwise to ^{number_of_consecutive_calls}.

    So, e.g., for trace [a, b, c, c, c], we get [a, b, c^3] for generalize=False, and [a, b, c^*] otherwise.

    :param trace: list of strings in order of calls
    :param generalize: if set to true, then the folded calls will be generalized to *
    :return: trace with folded recursive calls
    """
    folded_trace = []
    for uid, group in itertools.groupby(trace):
        count = sum(1 for _ in group)
        if count > 1:
            folded_trace.append(f"{uid}^*" if generalize else f"{uid}^{count}")
        else:
            folded_trace.append(uid)
    return folded_trace


class FuncData(ABC):
    @abstractmethod
    def update(self, inclusive_t: int, exclusive_t: int, callees_cnt: int) -> None:
        ...


class FuncDataDetails(FuncData):
    __slots__ = "inclusive_time", "exclusive_time", "callees_count"

    def __init__(self) -> None:
        self.inclusive_time: list[int] = []
        self.exclusive_time: list[int] = []
        self.callees_count: int = 0

    def update(self, inclusive_t: int, exclusive_t: int, callees_cnt: int) -> None:
        self.inclusive_time.append(inclusive_t)
        self.exclusive_time.append(exclusive_t)
        self.callees_count += callees_cnt


class FuncDataFlat(FuncData):
    __slots__ = [
        "inclusive_time",
        "exclusive_time",
        "incl_t_min",
        "incl_t_max",
        "excl_t_min",
        "excl_t_max",
        "call_count",
        "callees_count",
    ]

    def __init__(self) -> None:
        self.inclusive_time: int = 0
        self.exclusive_time: int = 0
        self.incl_t_min: int = -1
        self.incl_t_max: int = 0
        self.excl_t_min: int = -1
        self.excl_t_max: int = 0
        self.call_count: int = 0
        self.callees_count: int = 0

    def update(self, inclusive_t: int, exclusive_t: int, callees_cnt: int) -> None:
        self.inclusive_time += inclusive_t
        self.exclusive_time += exclusive_t
        self.call_count += 1
        self.callees_count += callees_cnt
        # Update the max and min values
        if self.incl_t_min == -1:
            self.incl_t_min = inclusive_t
            self.excl_t_min = exclusive_t
        else:
            self.incl_t_min = min(self.incl_t_min, inclusive_t)
            self.excl_t_min = min(self.excl_t_min, exclusive_t)
        self.incl_t_max = max(self.incl_t_max, inclusive_t)
        self.excl_t_max = max(self.excl_t_max, exclusive_t)


class TraceContextsMap(Generic[DataT]):
    __slots__ = "idx_name_map", "data_t", "trace_map", "durations", "total_runtime"

    def __init__(self, idx_name_map: dict[int, str], data_type: Type[DataT]) -> None:
        self.idx_name_map: dict[int, str] = idx_name_map
        self.data_t: Type[DataT] = data_type
        # Trace (sequence of function IDs) -> Trace ID
        self.trace_map: dict[tuple[int, ...], int] = {}
        # Function ID, Trace ID -> Inclusive, Exclusive durations, callees count
        self.durations: dict[tuple[int, int], DataT] = {}
        self.total_runtime: int = 0

    def add(
        self, func_id: int, trace: tuple[int, ...], inclusive_t: int, exclusive_t: int, callees: int
    ) -> None:
        trace_id = self.trace_map.setdefault(trace, len(self.trace_map))
        func_times = self.durations.setdefault((func_id, trace_id), self.data_t())
        func_times.update(inclusive_t, exclusive_t, callees)

    def __iter__(self) -> Iterator[tuple[str, tuple[str, ...], DataT]]:
        # Reverse the trace map for fast retrieval of Trace ID -> Trace
        trace_map_rev: dict[int, tuple[int, ...]] = {
            trace_id: trace for trace, trace_id in self.trace_map.items()
        }
        for (func_id, trace_id), func_times in self.durations.items():
            # Func name, Trace (sequence of func names), inclusive times, exclusive times
            yield (
                self.idx_name_map.get(func_id, str(func_id)),
                # Translate the function indices to names
                tuple(
                    self.idx_name_map.get(trace_func, str(trace_func))
                    for trace_func in trace_map_rev[trace_id]
                ),
                func_times,
            )


class TraceRecord:
    __slots__ = "func_id", "timestamp", "callees", "callees_time"

    def __init__(self, func_id: int, timestamp: int) -> None:
        self.func_id: int = func_id
        self.timestamp: int = timestamp
        self.callees: int = 0
        self.callees_time: int = 0


def report_finished_event(ts, top_record, record_stack, function_name, trace_contexts):
    if (duration := ts - top_record.timestamp) < 0:
        log.error(
            f"corrupted log: invalid timestamps for {function_name}:"
            f" duration of inclusive time: {duration} is negative."
        )
    if (duration - top_record.callees_time) < 0:
        log.error(
            f"corrupted log: invalid timestamps for {function_name}:"
            f" duration of exclusive time: {duration - top_record.callees_time} is negative."
        )
    # Obtain the trace from the stack
    trace = tuple(record.func_id for record in record_stack if record.func_id != -1)
    # Update the exclusive time of the parent call
    record_stack[-1].callees += 1
    record_stack[-1].callees_time += duration
    # Register the new function duration record
    trace_contexts.add(
        top_record.func_id,
        trace,
        duration,
        duration - top_record.callees_time,
        top_record.callees,
    )


def parse_traces(
    raw_data: pathlib.Path,
    func_map: dict[int, str],
    data_type: Type[DataT],
    skip_mismatched: bool = False,
) -> TraceContextsMap[DataT]:
    # Dummy TraceRecord for measuring exclusive time of the top-most function call
    record_stacks: dict[(int, int), list[TraceRecord]] = {}
    trace_contexts = TraceContextsMap(func_map, data_type)
    parsed_lines = []  # Used for debug only

    file_size = os.path.getsize(raw_data)
    read_bytes = 0
    chunk_size = 24

    with progressbar.ProgressBar(max_value=file_size + chunk_size) as progress:
        with open(raw_data, "rb") as data_handle:
            # Special handling for the first line to get the first timestamp
            record = data_handle.read(chunk_size)
            read_bytes += chunk_size
            progress.update(read_bytes)
            if record is None or record == b"":
                return trace_contexts
            _, _, _, trace_contexts.total_runtime = struct.unpack("iIQQ", record)
            ts: int
            while record:
                # [0] 32 lowest bits: pid, 32 upper bits: func ID (28b) + event type (4b)
                # [1] 32b empty, 32bit tid
                # [2] 64b timestamp
                pid, record_id, tid, ts = struct.unpack("iIQQ", record)
                if (pid, tid) not in record_stacks:
                    record_stacks[(pid, tid)] = [TraceRecord(-1, 0)]
                record_stack = record_stacks[(pid, tid)]
                event_type = record_id & 0xF
                func_id = record_id >> 4
                if log.is_verbose_enough(log.VERBOSE_DEBUG):
                    stack = ";".join(
                        func_map.get(record.func_id, record.func_id) for record in record_stack
                    )
                    parsed_lines.append(
                        f"{ts}:({pid}:{tid})({func_map.get(func_id, func_id)}):{'call' if event_type == 0 else 'return'}"
                    )
                if event_type == 0:
                    record_stack.append(TraceRecord(func_id, ts))
                    record = data_handle.read(chunk_size)
                    read_bytes += chunk_size
                    progress.update(read_bytes)
                    continue
                found_matching_record = False
                while True:
                    # We found the sentinel
                    if record_stack[-1].func_id == -1 and len(record_stack) == 1:
                        break
                    top_record = record_stack.pop()
                    if top_record.func_id != func_id:
                        log.warn(
                            f"stack mismatch: expected {func_map.get(top_record.func_id, top_record.func_id)} "
                            f"{('skipping' if skip_mismatched else 'approximating')},"
                            f" but got {func_map.get(func_id, func_id)}."
                        )
                        if log.is_verbose_enough(log.VERBOSE_DEBUG):
                            parsed_lines.append(f"{ts}:stack-mismatch:expected {func_map.get(top_record.func_id, top_record.func_id)} got {func_map.get(func_id, func_id)}")
                        if not skip_mismatched:
                            report_finished_event(
                                ts,
                                top_record,
                                record_stack,
                                func_map.get(top_record.func_id, top_record.func_id),
                                trace_contexts,
                            )
                        continue
                    found_matching_record = True
                    break
                if not found_matching_record:
                    log.warn(f"no calling event for {func_map.get(func_id, func_id)} (skipping)")
                    record = data_handle.read(chunk_size)
                    read_bytes += chunk_size
                    progress.update(read_bytes)
                    if log.is_verbose_enough(log.VERBOSE_DEBUG):
                        parsed_lines.append(
                            f"{ts}:missing-call:expected {func_map.get(func_id, func_id)}"
                        )
                    continue
                report_finished_event(
                    ts, top_record, record_stack, func_map.get(func_id, func_id), trace_contexts
                )
                record = data_handle.read(chunk_size)
                read_bytes += chunk_size
                progress.update(read_bytes)
            # Compute an approximation of the total runtime
            trace_contexts.total_runtime = ts - trace_contexts.total_runtime

            # Register overall
            exclusive = sum(val[-1].callees_time for val in record_stacks.values())
            trace_contexts.add(
                -1, (), trace_contexts.total_runtime, exclusive, file_size // chunk_size
            )
    if log.is_verbose_enough(log.VERBOSE_DEBUG):
        log.minor_info("Events left in stack")
        log.increase_indent()
        for stack in record_stacks.values():
            for event in stack:
                log.minor_info(
                    f"({func_map.get(event.func_id, event.func_id)}, {event.callees_time})"
                )
        log.decrease_indent()
        with open("ktrace-parse-debug.log", "w") as debug_log:
            debug_log.write("\n".join(parsed_lines))
    return trace_contexts


def traces_flat_to_pandas(trace_contexts: TraceContextsMap[FuncDataFlat]) -> pd.DataFrame:
    pandas_rows: list[tuple[Any, ...]] = []
    for func_name, trace, func_times in trace_contexts:
        pandas_rows.append(
            (
                func_name,
                " -> ".join(trace),
                func_times.call_count,
                func_times.callees_count,
                func_times.callees_count / func_times.inclusive_time,
                func_times.inclusive_time / NS_TO_MS,
                func_times.inclusive_time / trace_contexts.total_runtime,
                func_times.exclusive_time / NS_TO_MS,
                func_times.exclusive_time / trace_contexts.total_runtime,
                func_times.inclusive_time / func_times.call_count / NS_TO_MS,
                func_times.exclusive_time / func_times.call_count / NS_TO_MS,
                func_times.incl_t_min,
                func_times.excl_t_min,
                func_times.incl_t_max,
                func_times.excl_t_max,
            )
        )
    df = pd.DataFrame(
        pandas_rows,
        columns=[
            "Function",
            "Trace",
            "Calls [#]",
            "Callees [#]",
            "Callees Mean [#]",
            "Total Inclusive T [ms]",
            "Total Inclusive T [%]",
            "Total Exclusive T [ms]",
            "Total Exclusive T [%]",
            "I Mean",
            "E Mean",
            "I Min",
            "E Min",
            "I Max",
            "E Max",
        ],
    )
    df.sort_values(by=["Total Exclusive T [%]"], inplace=True, ascending=False)
    return df


def append_resources(
    func_name: str,
    trace: tuple[str],
    resources: list[dict[str, Any]],
    times: list[int],
    resource_type: Literal["exclusive", "inclusive"],
) -> None:
    """Helper function for simple clustering of the resources

    :param func_name: name of the function for which the resources correspond
    :param trace: tuple of function names corresponding to the trace of the resource
    :param resources: resulting resources
    :param times: measured inclusive/exlusive times
    :param resource_type: type of resources added (currently supports inclusive or exclusive time
    """
    for _, group in itertools.groupby(times, lambda x: (len(str(x)), int(str(x)[0]))):
        group = list(group)
        resources.append(
            {
                "amount": group[0],
                "uid": func_name,
                "ncalls": len(group),
                "type": "time",
                "subtype": resource_type,
                "trace": fold_recursive_calls_in_trace(list(trace)),
            }
        )


def pandas_to_resources(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Transforms pandas dataframe to list of resources

    :param df: pandas dataframe
    :return: list of resources
    """
    resources = []
    for _, row in df.iterrows():
        function = row["Function"]
        trace = row["Trace"].split(" -> ") if row["Trace"] else []
        ncalls = row["Calls [#]"]

        resource = {
            "uid": function,
            "ncalls": ncalls,
            "type": "stats",
            "trace": fold_recursive_calls_in_trace(list(trace)),
        }
        for col in df.columns:
            if col in ("Function", "Trace", "Calls [#]"):
                continue
            resource[col] = row[col]
        resources.append(resource)
    return resources


def trace_details_to_resources(
    trace_contexts: TraceContextsMap[FuncDataDetails],
) -> list[dict[str, Any]]:
    """Converts the traces into a list of resources saveable to Perun

    :param trace_contexts: structure that holds trace context
    :return: list of dictionaries, with key and values as needed by perun
    """
    resources = []
    for func_name, trace, func_times in trace_contexts:
        append_resources(func_name, trace, resources, func_times.inclusive_time, "inclusive")
        append_resources(func_name, trace, resources, func_times.exclusive_time, "exclusive")
    return resources


def traces_details_to_pandas(trace_contexts: TraceContextsMap[FuncDataDetails]) -> pd.DataFrame:
    pandas_rows: list[tuple[Any, ...]] = []
    for func_name, trace, func_times in trace_contexts:
        inclusive_t_stats = pd.Series(func_times.inclusive_time).describe(
            percentiles=[0.10, 0.25, 0.50, 0.75, 0.90]
        )
        inclusive_sum = sum(func_times.inclusive_time)
        exclusive_t_stats = pd.Series(func_times.exclusive_time).describe(
            percentiles=[0.10, 0.25, 0.50, 0.75, 0.90]
        )
        exclusive_sum = sum(func_times.exclusive_time)
        incl_excl_flattened = [
            val / NS_TO_MS
            for incl_excl_tuple in zip(inclusive_t_stats.iloc[1:], exclusive_t_stats.iloc[1:])
            for val in incl_excl_tuple
        ]
        pandas_rows.append(
            (
                func_name,
                " -> ".join(trace),
                int(inclusive_t_stats["count"]),
                func_times.callees_count,
                func_times.callees_count / len(func_times.inclusive_time),
                inclusive_sum / NS_TO_MS,
                inclusive_sum / trace_contexts.total_runtime,
                exclusive_sum / NS_TO_MS,
                exclusive_sum / trace_contexts.total_runtime,
                *incl_excl_flattened,
            )
        )
    df = pd.DataFrame(
        pandas_rows,
        columns=[
            "Function",
            "Trace",
            "Calls [#]",
            "Callees [#]",
            "Callees Mean [#]",
            "Total Inclusive T [ms]",
            "Total Inclusive T [%]",
            "Total Exclusive T [ms]",
            "Total Exclusive T [%]",
            "I Mean",
            "E Mean",
            "I Std",
            "E Std",
            "I Min",
            "E Min",
            "I 10%",
            "E 10%",
            "I 25%",
            "E 25%",
            "I 50%",
            "E 50%",
            "I 75%",
            "E 75%",
            "I 90%",
            "E 90%",
            "I Max",
            "E Max",
        ],
    )
    df.sort_values(by=["Total Exclusive T [%]"], inplace=True, ascending=False)
    return df
