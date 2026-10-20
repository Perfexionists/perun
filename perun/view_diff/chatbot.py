"""Functions related to chatbot support in diff views."""

from __future__ import annotations

# Standard Imports
from pathlib import Path

# Third-Party Imports

# Perun Imports
from perun.utils import log, streams

SUMMARY_PROMPT = """Summarize the performance comparison using the report overview below.
First, look at the div with id="environment" and analyze the changes in the system configuration.
Pay special attention to the boot parameters (BOOT_IMAGE) and the kernel versions if they differ.
Do the same for the divs with id="profile-vulnerabilities" and id="profile-metadata".

Then, look at the second list in topFunctionDiffs variable and the comment that explains the four
nested lists. Load at most 10 values from each nested list; each value is a list of two values:
the function ID and its resource consumption delta between the compared profiles. The function IDs
represent indices to a variable "nodes" within this document.

Next, do the same with the second list in topTraceDiffs variable with a small change: each value in
the nested lists represents a stack trace rather than a single function. Parse and translate the
traces (semicolon is the delimiter).

Considering the changes in kernel internals between the measured versions, explain to the user what
the most expensive functions and traces do (for traces, consider the leaf function); what is the
purpose of the functions and how they changed between the versions.

Finally, create a hypothesis for what might have caused the observed performance changes based on
the data. Stress to the user that this is only a hypothesis and suggest a tasklist for
confirming/disproving the hypothesis. If the topFunctionDiffs and topTraceDiffs do not provide
sufficient context, scan the "rawData" variable which contains many more functions and traces.

Importantly, keep the summary concise.
"""


def generate_initial_prompt(chatbot_enabled: bool, chatbot_contexts: tuple[str, ...] | None) -> str:
    """Compose initial chatbot prompt context from possibly multiple sources.

    :param chatbot_enabled: whether chatbot support is enabled or not.
    :param chatbot_contexts: sources of the prompt context; may be either strings or a file paths.

    :return: the resulting prompt context string.
    """
    # Process user-defined chatbot prompt context, if provided.
    if not chatbot_enabled or chatbot_contexts is None:
        return ""
    log.minor_info("Processing chatbot prompt context")
    context_str: str = ""
    for source in chatbot_contexts:
        if source.endswith(".prompt"):
            # The context is stored in a file, attempt to open and read it.
            with streams.safely_open_and_log(Path(source), "r", fatal_fail=False) as handle:
                if handle is not None:
                    context_str += f"\n{handle.read()}"
        else:
            context_str += f"\n{source}"
    return context_str + "\n"
