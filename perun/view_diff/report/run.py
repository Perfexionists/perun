"""HTML report difference of the profiles"""
from __future__ import annotations

# Standard Imports
from dataclasses import dataclass
from typing import Any
import os

# Third-Party Imports
import click
import jinja2

# Perun Imports
from perun.utils import log
from perun.profile.factory import Profile
from perun.profile import convert, helpers


PRECISION: int = 2


@dataclass
class TableRecord:
    """Represents single record on top of the consumption

    :ivar uid: uid of the records
    :ivar trace: trace of the record
    :ivar abs_amount: absolute value of the uid
    :ivar rel_amount: relative value of the uid
    """

    __slots__ = ["uid", "trace", "short_trace", "abs_amount", "rel_amount"]

    uid: str
    trace: str
    short_trace: str
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
    columns = ["uid", "amount", "relative", "short trace"]

    env = jinja2.Environment(loader=jinja2.PackageLoader("perun.view_diff.report", "templates"))
    template = env.get_template("report.html.jinja2")
    content = template.render(
        lhs_tag="baseline",
        lhs_columns=columns,
        lhs_data=lhs_data,
        rhs_tag="target",
        rhs_columns=columns,
        rhs_data=rhs_data,
        title="Difference of profiles",
    )
    log.minor_success("HTML report ", "generated")
    if (output_file := kwargs.get("output_file")) is None:
        lhs_name = os.path.splitext(helpers.generate_profile_name(lhs_profile))[0]
        rhs_name = os.path.splitext(helpers.generate_profile_name(rhs_profile))[0]
        output_file = f"report-diff-of-{lhs_name}-and-{rhs_name}" + ".html"

    if not output_file.endswith("html"):
        output_file += ".html"

    with open(output_file, "w", encoding="utf-8") as template_out:
        template_out.write(content)
    log.minor_status("Output saved", log.path_style(output_file))


@click.command()
@click.option("-o", "--output-file", help="Sets the output file (default=automatically generated).")
@click.pass_context
def report(ctx: click.Context, *_, **kwargs: Any) -> None:
    profile_list = ctx.parent.params["profile_list"]
    generate_html_report(profile_list[0], profile_list[1], **kwargs)
