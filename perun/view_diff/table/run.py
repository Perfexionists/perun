"""Table difference of the profiles

The difference is in form of:

cmd       | cmd
workload  | workload
collector | kernel

  rank | col1 | col2 | ... | coln
  grp1 |  ..  |  ..  | ..  | ..
  grp2 |  ..  |  ..  | ..  | ..

"""
from __future__ import annotations

# Standard Imports
from dataclasses import dataclass
from typing import Any
import itertools

# Third-Party Imports
import click
import pandas
import tabulate

# Perun Imports
from perun.utils import log
from perun.profile import convert
from perun.profile.factory import Profile

PRECISION: int = 2


@dataclass
class TableRecord:
    """Represents single record on top of the consumption

    :ivar uid: uid of the records
    :ivar trace: trace of the record
    :ivar trace_list: trace as list of formatted strings
    :ivar abs: absolute value of the uid
    :ivar rel: relative value of the uid
    """

    uid: str
    trace: str
    trace_list: list[str]
    abs: str
    rel: float


def generate_trace_list(trace: str, uid: str) -> list[str]:
    """Generates list of traces

    :param trace: trace to uid
    :param uid: called uid
    """
    if trace.strip() == "":
        return [uid]
    data = []
    lhs_trace = trace.split(",") + [uid]
    for i, lhs in enumerate(lhs_trace):
        if i == 0:
            data.append(lhs)
            continue
        indent = " " * i + "┕ "
        data.append(indent + lhs)
    return data


def print_header(lhs_profile: Profile, rhs_profile: Profile) -> None:
    """Prints the header of the profile

    :param lhs_profile: left (baseline) profile for which we are printing some header
    :param rhs_profile: right (target) profile for which we are printing some header
    """
    log.major_info("Difference Summary")
    command = " ".join([lhs_profile["header"]["cmd"], lhs_profile["header"]["workload"]]).strip()
    data = [
        ["baseline origin", lhs_profile.get("origin")],
        ["target origin", rhs_profile.get("origin")],
        ["command", command],
        ["collector command", log.collector_to_command(lhs_profile.get("collector_info", {}))],
    ]
    print(tabulate.tabulate(data))  # type: ignore


def get_top_n_records(profile: Profile, **kwargs: Any) -> list[TableRecord]:
    """Retrieves top N records in the profile

    :param profile: profile for which we are analysing top N records
    :param kwargs: other parameters
    :return: list of top N records
    """
    df = convert.resources_to_pandas_dataframe(profile)

    if filters := kwargs.get("filters"):
        df = filter_df(df, filters)

    grouped_df = df.groupby(["uid", "trace"]).agg({"amount": "sum"}).reset_index()
    sorted_df = grouped_df.sort_values(by="amount", ascending=False)
    amount_sum = df["amount"].sum()
    top_n = []
    for _, top in sorted_df.head(kwargs["top_n"]).iterrows():
        top_n.append(
            TableRecord(
                top["uid"],
                top["trace"],
                generate_trace_list(top["trace"], top["uid"]),
                top["amount"],
                round(100 * top["amount"] / amount_sum, PRECISION),
            )
        )
    return top_n


def print_traces(top_n_lhs: TableRecord, top_n_rhs: TableRecord) -> None:
    """Prints formatted traces next to each other

    :param top_n_lhs: baseline record
    :param top_n_rhs: target record
    """
    data = []
    tabulate.PRESERVE_WHITESPACE = True
    lhs_trace = top_n_lhs.trace.split(",") + [top_n_lhs.uid]
    rhs_trace = top_n_rhs.trace.split(",") + [top_n_rhs.uid]
    for i, (lhs, rhs) in enumerate(itertools.zip_longest(lhs_trace, rhs_trace, fillvalue="")):
        indent = " " * i + "┕ "
        lhs_in_color = log.in_color(lhs, "green" if lhs in rhs_trace else "red")
        rhs_in_color = log.in_color(rhs, "green" if lhs in rhs_trace else "red")
        data.append(
            [(indent + lhs_in_color) if lhs else lhs, (indent + rhs_in_color) if rhs else rhs]
        )
    print(tabulate.tabulate(data, headers=["baseline trace", "target trace"]))
    tabulate.PRESERVE_WHITESPACE = False


def filter_df(df: pandas.DataFrame, filters: list[tuple[str, Any]]) -> pandas.DataFrame:
    """Filters dataframe based on list of rules

    :param df: input dataframe
    :param filters: list of tuples of column and value
    :return: filtered pandas dataframe
    """
    mask = None
    for column, value in filters:
        if mask is None:
            mask = df[column] == value
        else:
            mask |= df[column] == value
    return df[mask]  # type: ignore


def compare_profiles(lhs_profile: Profile, rhs_profile: Profile, **kwargs: Any) -> None:
    """Compares the profiles and prints table for top N ranks

    :param lhs_profile: baseline profile
    :param rhs_profile: target profile
    :param kwargs: other parameters
    """
    # Print short header with some information
    print_header(lhs_profile, rhs_profile)

    # Compare top-N resources
    top_n_lhs = get_top_n_records(lhs_profile, **kwargs)
    top_n_rhs = get_top_n_records(rhs_profile, **kwargs)

    lhs_tag = f"baseline({kwargs['group_by']})"
    rhs_tag = f"target({kwargs['group_by']})"
    columns = ["uid", "rel", "diff"]

    for i, (top_lhs, top_rhs) in enumerate(zip(top_n_lhs, top_n_rhs)):
        log.major_info(f"Top-{i+1} Record")
        data = [
            [lhs_tag, top_lhs.uid, top_lhs.rel, float(top_lhs.abs) - float(top_rhs.abs)],
            [rhs_tag, top_rhs.uid, top_rhs.rel, float(top_rhs.abs) - float(top_lhs.abs)],
        ]
        print(tabulate.tabulate(data, headers=[str(i + 1)] + columns))
        log.newline()
        print_traces(top_lhs, top_rhs)


@click.command()
@click.option(
    "-n", "--top-n", type=click.INT, help="Prints top [INT] records (default=10).", default=10
)
@click.option(
    "-f",
    "--filter",
    "filters",
    nargs=2,
    multiple=True,
    help="Filters the result to concrete column and concrete value.",
)
@click.option(
    "-g",
    "--group-by",
    default="origin",
    type=click.STRING,
    help="Names the each profile by its particular option (default=origin).",
)
@click.pass_context
def table(ctx: click.Context, *_: Any, **kwargs: Any) -> None:
    assert ctx.parent is not None and f"impossible happened: {ctx} has no parent"
    profile_list = ctx.parent.params["profile_list"]
    compare_profiles(profile_list[0], profile_list[1], **kwargs)
