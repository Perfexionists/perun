"""Functions related to chatbot support in diff views."""

from __future__ import annotations

# Standard Imports
from pathlib import Path

# Third-Party Imports

# Perun Imports
from perun.utils import log, streams


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
