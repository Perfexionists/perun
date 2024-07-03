"""Wrapper for web collector, which collects profiling data from
TypeScript/JavaScript web applications

Specifies before, collect, after and teardown functions to perform the initialization,
collection and postprocessing of collection data.
"""

import os
import time
import click
import psutil
import requests
import subprocess
import perun.logic.runner as runner

from time import sleep
from typing import Any, List
from datetime import datetime
from perun.utils import log as perun_log
from perun.utils.external import processes
from perun.collect.web.parser import Parser
from perun.utils.structs import CollectStatus


def collect(**kwargs) -> tuple[CollectStatus, str, dict[str, Any]]:
    """Assembles the engine collect program according to input parameters and collection strategy.
    Runs the created collection program and the profiled command.

    :param kwargs: dictionary containing the configuration and probe settings for the collector
    :returns: tuple (CollectStatus enum code,
                    string as a status message, mainly for error states,
                    dict of kwargs (possibly with some new values))
    """

    project_path = kwargs["proj"]
    express_file = kwargs["express"]
    timeout = kwargs["timeout"]
    kwargs["prof_port"] = 9000
    project_port = kwargs["port"]
    profiler_port = kwargs["prof_port"]
    profiler_path = kwargs["otp"]
    command = "start"

    if project_path == "":
        project_path = os.getcwd() + "/"
        print(project_path)

    with processes.nonblocking_subprocess(
            "yarn " + command + " --silent " + "--path " + project_path + express_file,
            {"cwd": profiler_path}
    ) as prof_process:
        perun_log.minor_info("Warm up phase...")
        server_url = "http://localhost:" + str(project_port)
        if wait_until_server_starts(server_url):
            perun_log.minor_info("Collect phase...")

            sleep(timeout)
            kill_processes([project_port, profiler_port])

            perun_log.minor_info("Collecting finished...")
        else:
            perun_log.error("Could not start profiler or target project...")

    return CollectStatus.OK, "", dict(kwargs)


def kill_processes(ports: List[int]) -> None:
    """Terminate processes listening on specified ports after timeout.

    :param ports: List of integers representing ports on which processes are running.
    :return: None
    """

    for port in ports:
        for conn in psutil.net_connections():
            if conn.laddr.port == port and conn.status == 'LISTEN' and port != 0:
                subprocess.run(["kill", "-9", str(conn.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def wait_until_server_starts(url: str, max_attempts: int = 20, wait_time: float = 0.5) -> bool:
    """Wait until a server at the specified URL starts responding.

    :param url: The URL of the server to wait for.
    :param max_attempts: The maximum number of attempts to make before giving up. Default is 10.
    :param wait_time: The time to wait (in seconds) between attempts. Default is 1.
    :return: True if the server started within the specified attempts, False otherwise.
    """

    for _ in range(max_attempts):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return True
        except requests.ConnectionError:
            pass
        sleep(wait_time)
    return False


def after(**kwargs) -> tuple[CollectStatus, str, dict[str, dict[str, dict[str, list[dict[str, Any]] | float]]]]:
    """Parses the trace collector output and transforms it into profile resources

    :param kwargs: the configuration settings for the collector
    :returns: tuple (CollectStatus enum code,
                    string as a status message, mainly for error states,
                    dict of kwargs (possibly with some new values))
    """
    perun_log.minor_info("Post-processing phase... ")

    otp_dir = kwargs["otp"]
    metrics = os.path.join(otp_dir, "data/metrics/metrics.log")
    done_folder = os.path.join(otp_dir, "data/metrics/done")
    timestamp = time.strftime("%Y%m%d%H%M%S")
    new_filename = f"{timestamp}_metrics.log"
    os.makedirs(done_folder, exist_ok=True)

    metrics_data = []
    parser = Parser()

    try:
        with open(metrics, 'r') as metrics_file:
            for line in metrics_file:
                parsed_line = parser.parse_metric(line)
                metrics_data.append(parsed_line)
            os.rename(metrics, os.path.join(done_folder, new_filename))
    except FileNotFoundError as e:
        perun_log.error(f"File {metrics} was not created or cannot be opened")
        exit(1)

    perun_log.minor_info("Data processing finished.")

    return (
        CollectStatus.OK,
        "",
        {
            "profile": {
                "global": {
                    "timestamp": datetime.now().timestamp(),
                    "resources": [
                        {
                            "amount": value,
                            "uid": route,
                            "type": key,
                            "timestamp": timestamp,
                        }
                        for (key, value, route, timestamp) in metrics_data
                    ]
                }
            }
        }
    )


def teardown(**kwargs) -> tuple[CollectStatus, str, dict[str, Any]]:
    """Perform a cleanup of all the collection resources that need it, i.e. files, locks,
    processes, kernel modules etc.

    :param kwargs: the configuration settings for the collector
    :returns: tuple (CollectStatus enum code,
                    string as a status message, mainly for error states,
                    dict of kwargs (possibly with some new values))
    """
    perun_log.minor_info("Teardown phase...")

    kill_processes([kwargs.get("port", 0), kwargs.get("prof_port", 0)])

    return CollectStatus.OK, "", dict(kwargs)


@click.command()
@click.option(
    "--otp",
    "-o",
    type=str,
    required=True,
    default="",
    help="Path to the OpenTelemetry profiler script."
)
@click.option(
    "--proj",
    "-p",
    type=str,
    required=False,
    default="",
    help="Path to the project to be profiled.\n"
         "If it's not given actual directory is used."
)
@click.option(
    "--express",
    "-e",
    type=str,
    required=True,
    help="Path to file in your project containing express() app with export.\n"
         "The export must be default or named 'app'\n"
         "Examples: 'src/app', 'src/app.ts'"
)
@click.option(
    "--port",
    type=int,
    required=True,
    help="Port on which project run."
)
@click.option(
    "--timeout",
    "-t",
    type=int,
    required=False,
    default=60,
    help="Timeout for the runtime of profiling in seconds.\n"
         "Default is seconds."
)
@click.pass_context
def web(ctx: click.Context, **kwargs: Any) -> None:
    """Generates a `web` performance profile, capturing various metrics including response latency (ms), request count,
    error occurrences, file system activity, memory usage, throughput, user CPU usage, system CPU usage,
    user CPU time, system CPU time, etc.
    """

    runner.run_collector_from_cli_context(ctx, "web", kwargs)
