"""
Functions for working with templates
"""

from __future__ import annotations

# Standard Imports
from pathlib import Path
from typing import Callable, Any, Optional, Mapping

# Third-Party Imports
from jinja2 import Environment, FileSystemLoader, Template

# Perun Imports


def get_template(
    template_name: str, filters: Optional[Mapping[str, Callable[[str], str]]] = None
) -> Template:
    """Loads jinja2 template from the templates directory

    Note: there are some issues with using PackageLoader of Jinja2 in combination
    with meson.build; when using the editable install (make dev) it seems that it
    nondeterministically sets the wrong path resulting into errors. It works fine
    for classic installation (make install).

    Hence, we wrapped it in FileSystemLoader with absolute paths.

    :return: loaded template from perun/templates directory
    """
    # Note: we keep the autoescape=false, since we kindof believe we are not trying to fuck us up
    env = Environment(loader=FileSystemLoader(Path(__file__).parent))
    for filter_name, filter_func in (filters or {}).items():
        env.filters[filter_name] = filter_func
    return env.get_template(template_name)


def get_environment(**kwargs: Any) -> Environment:
    """Returns Jinja2 environment for working with template

    :return: jinja environment
    """
    return Environment(loader=FileSystemLoader(Path(__file__).parent), **kwargs)
