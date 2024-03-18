"""Set of helpers for working with traces """
from __future__ import annotations

# Standard Imports
from typing import Any
import functools

# Third-Party Imports

# Perun Imports


@functools.cache
def split_to_words(identifier: str) -> set[str]:
    """Splits identifier of function into list of words

    For simplicity, we assume, that identifier is in snake case, so camel case will not be split

    :param identifier: identifier of function or other primitive, that consists of words
    :return: list of words in identifier
    """
    return set(identifier.split("_"))


def switch_cost(lhs_identifier: str, rhs_identifier: str) -> float:
    """Computes cost of switching lhs_identifier with rhs_identifier

    The cost is computed as 1 - 2 * number of common words / (number of words in LHS + number of words in RHS)

    :param lhs_identifier: left hand side identifier (function)
    :param rhs_identifier: right hand side identifier (function)
    :return: float cost of switching lhs with rhs
    """
    key = (
        f"{lhs_identifier};{rhs_identifier}"
        if lhs_identifier < rhs_identifier
        else f"{rhs_identifier};{lhs_identifier}"
    )
    if key not in SWITCH_CACHE.keys():
        lhs_words = split_to_words(lhs_identifier)
        rhs_words = split_to_words(rhs_identifier)
        cost = 1 - (2 * len(lhs_words.intersection(rhs_words)) / (len(lhs_words) + len(rhs_words)))
        SWITCH_CACHE[key] = cost
    return SWITCH_CACHE[key]


DISTANCE_CACHE: dict[str, float] = {}
OPTIMIZED_DISTANCE_CACHE: dict[str, float] = {}
SWITCH_CACHE: dict[str, float] = {}


def compute_distance(
    lhs_trace: list[dict[str, Any]],
    rhs_trace: list[dict[str, Any]],
    trace_key: str = "func",
) -> float:
    """Computes the distance between two traces

    The distance is computed as least number of applications of following operations:

      1. Match (cost = 0): matching parts of the traces, i.e. the same functions;
      2. Insert/Delete (cost = 1): adding or deleting part of the trace, so the traces match
      3. Substituion (cost = variable): switching part of the trace with another

    This is based on [ISCSME'21] paper called:
    Performance debugging in the large via mining millions of stack traces

    We assume, that the inputs are in form of list which contains the dictionaries
    with key "func" that corresponds to the name of the ids. One can change it using
    the parameter "trace_key".

    :param lhs_trace: lhs trace of function names
    :param rhs_trace: rhs trace of function names
    :param trace_key: key that is used for retrieving the trace names
    :return: distance between two traces
    """
    key = f"{','.join(l[trace_key] for l in lhs_trace)};{','.join(r[trace_key] for r in rhs_trace)}"

    if key not in DISTANCE_CACHE.keys():
        # We need to insert everything from RHS, hence full cost of what is in RHS
        if len(lhs_trace) == 0:
            cost = float(len(rhs_trace))
        # We need to insert everything from LHS, hence full cost of what is in LHS
        elif len(rhs_trace) == 0:
            cost = float(len(lhs_trace))
        # 1. First parts are matched in the trace, so the cost is the cost of matching the rest of the trace
        elif lhs_trace[0][trace_key] == rhs_trace[0][trace_key]:
            cost = compute_distance(lhs_trace[1:], rhs_trace[1:], trace_key)
        # Else, we have to either try to insert/delete or switch functions
        else:
            # 2. We try Insertion/Deletion of the current functions, and add the cost of inserting/deleting
            cost_delete_lhs = compute_distance(lhs_trace[1:], rhs_trace, trace_key) + 1
            cost_delete_rhs = compute_distance(lhs_trace, rhs_trace[1:], trace_key) + 1
            # 3. We try Switch of the current two functions add the switch cost and compute the rest of the distance
            cost_switch = compute_distance(lhs_trace[1:], rhs_trace[1:], trace_key) + switch_cost(
                lhs_trace[0][trace_key], rhs_trace[0][trace_key]
            )
            # We take the minimum of the computed costs
            cost = min(cost_delete_lhs, cost_delete_rhs, cost_switch)
        DISTANCE_CACHE[key] = cost
    return DISTANCE_CACHE[key]
