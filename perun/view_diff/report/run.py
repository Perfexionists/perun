"""HTML report difference of the profiles"""
from __future__ import annotations

# Standard Imports
from dataclasses import dataclass
from typing import Any

# Third-Party Imports
import click
import jinja2

# Perun Imports
from perun.utils import log
from perun.utils.common import diff_kit
from perun.profile.factory import Profile
from perun.profile import convert
from perun.view_diff.flamegraph import run as flamegraph_run
from perun.view_diff.table import run as table_run


PRECISION: int = 2


@dataclass
class TableRecord:
    """Represents single record on top of the consumption

    :ivar uid: uid of the records
    :ivar trace: trace of the record
    :ivar abs_amount: absolute value of the uid
    :ivar rel_amount: relative value of the uid
    """

    __slots__ = ["uid", "trace", "short_trace", "trace_list", "abs_amount", "rel_amount"]

    uid: str
    trace: str
    short_trace: str
    trace_list: list[str]
    abs_amount: float
    rel_amount: float


def to_short_trace(trace: str) -> str:
    """Converts longer traces to short representation

    :param trace: trace, delimited by ','
    :return: shorter representation of trace
    """
    split_trace = trace.split(",")
    if len(split_trace) <= 3:
        return trace
    return " -> ".join([split_trace[0], "...", split_trace[-1]])


def profile_to_data(profile: Profile) -> list[TableRecord]:
    """Converts profile to list of columns and list of list of values

    :param profile: converted profile
    :return: list of columns and list of rows
    """
    df = convert.resources_to_pandas_dataframe(profile)

    grouped_df = df.groupby(["uid", "trace"]).agg({"amount": "sum"}).reset_index()
    sorted_df = grouped_df.sort_values(by="amount", ascending=False)
    amount_sum = df["amount"].sum()
    data = []
    for _, row in sorted_df.iterrows():
        data.append(
            TableRecord(
                row["uid"],
                row["trace"],
                to_short_trace(row["trace"]),
                table_run.generate_trace_list(row["trace"], row["uid"]),
                row["amount"],
                round(100 * row["amount"] / amount_sum, PRECISION),
            )
        )
    return data


def generate_html_report(lhs_profile: Profile, rhs_profile: Profile, **kwargs: Any):
    """Generates HTML report of differences

    :param lhs_profile: baseline profile
    :param rhs_profile: target profile
    :param kwargs: other parameters
    """
    log.major_info("Generating HTML Report", no_title=True)
    lhs_data = profile_to_data(lhs_profile)
    log.minor_success("Baseline data", "generated")
    rhs_data = profile_to_data(rhs_profile)
    log.minor_success("Target data", "generated")
    columns = [
        ("uid", "The measured symbol (click [+] for full trace)."),
        (
            f"[{lhs_profile['header']['units'][lhs_profile['header']['type']]}]",
            "The absolute measured value.",
        ),
        ("[%]", "The relative measured value (in percents overall)."),
    ]

    env = jinja2.Environment(loader=jinja2.PackageLoader("perun", "templates"))
    template = env.get_template("diff_view_report.html.jinja2")
    content = template.render(
        lhs_tag="Baseline (base)",
        lhs_columns=columns,
        lhs_data=lhs_data,
        lhs_header=flamegraph_run.generate_header(lhs_profile),
        rhs_tag="Target (tgt)",
        rhs_columns=columns,
        rhs_data=rhs_data,
        rhs_header=flamegraph_run.generate_header(rhs_profile),
        title="Difference of profiles (with tables)",
    )
    log.minor_success("HTML report ", "generated")
    output_file = diff_kit.save_diff_view(
        kwargs.get("output_file"), content, "report", lhs_profile, rhs_profile
    )
    log.minor_status("Output saved", log.path_style(output_file))


@click.command()
@click.option("-o", "--output-file", help="Sets the output file (default=automatically generated).")
@click.pass_context
def report(ctx: click.Context, *_, **kwargs: Any) -> None:
    profile_list = ctx.parent.params["profile_list"]
    generate_html_report(profile_list[0], profile_list[1], **kwargs)
