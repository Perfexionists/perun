"""
Base package for difference of profiles
"""
from __future__ import annotations

from typing import Callable, Any


def lazy_get_cli_commands() -> list[Callable[..., Any]]:
    """
    Lazily imports CLI commands
    """
    import perun.view_diff.flamegraph.run as flamegraph_run
    import perun.view_diff.table.run as table_run
    import perun.view_diff.report.run as report_run

    return [flamegraph_run.flamegraph, table_run.table, report_run.report]
