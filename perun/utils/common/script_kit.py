"""Contains helper scripts for creating units from templates."""
from __future__ import annotations

# Standard Imports
from pathlib import Path
from typing import Any
import os

# Third-Party Imports

import jinja2

# Perun Imports
from perun.logic import config
from perun.utils import log
from perun.utils.common import common_kit
from perun.utils.exceptions import ExternalEditorErrorException
from perun.utils.external import commands


def get_script(script_name: str) -> str:
    """Retrieves path to the script

    :param script_name: name of the retrieved script
    :return path to the script
    """
    script_dir = Path(Path(__file__).resolve().parent, "..", "..", "scripts")
    return os.path.join(script_dir, script_name)


def create_unit_from_template(template_type: str, no_edit: bool, **kwargs: Any) -> None:
    """Function for creating a module in the perun developer directory from template

    This function serves as a generator of modules and packages of units and algorithms for perun.
    According to the template_type this loads a concrete set of templates, (if needed) creates
    a target directory and then initializes all the needed modules.

    If no_edit is set to true, all the created modules, and the registration point (i.e. file,
    where new modules has to be registered) are opened in the editor set in the general.config key
    (which is looked up recursively).

    :param str template_type: name of the template set, that will be created
    :param bool no_edit: if set to true, then external editor will not be called to edit the files
    :param dict kwargs: additional parameters to the concrete templates
    :raises ExternalEditorErrorException: When anything bad happens when processing newly created
        files with editor
    """

    def template_name_filter(template_name: str) -> bool:
        """Helper function for filtering functions which starts with the template_type name

        :param str template_name: name of the template set
        :return: true if the function starts with template_type
        """
        return template_name.startswith(template_type)

    log.major_info("Creating Unit from Template")
    # Lookup the perun working dir according to the current file
    perun_dev_dir = os.path.abspath(os.path.join(os.path.split(__file__)[0], ".."))
    if (
        not os.path.isdir(perun_dev_dir)
        or not os.access(perun_dev_dir, os.W_OK)
        or template_type not in os.listdir(perun_dev_dir)
    ):
        log.error(
            f"cannot use {perun_dev_dir} as target developer directory "
            "(either not writeable or does not exist)\n\n"
            "Perhaps you are not working from perun dev folder?"
        )
    log.minor_status("Target Perun development dir", status=log.path_style(perun_dev_dir))

    # Initialize the jinja2 environment and load all templates for template_type set
    env = jinja2.Environment(loader=jinja2.PackageLoader("perun", "templates"), autoescape=True)
    list_of_templates = env.list_templates(filter_func=template_name_filter)

    # Specify the target dir (for packages we create a new directory)
    if "__init__" in "".join(list_of_templates):
        # We will initialize it in the isolate package
        target_dir = os.path.join(perun_dev_dir, template_type, kwargs["unit_name"])
        common_kit.touch_dir(target_dir)
    else:
        target_dir = os.path.join(perun_dev_dir, template_type)
    log.minor_status(f"Initializing new {template_type} module", status=log.path_style(target_dir))

    # Iterate through all templates and create the new files with rendered templates
    successfully_created_files = []
    log.increase_indent()
    for template_file in list_of_templates:
        # Specify the target filename of the template file
        template_filename, _ = os.path.splitext(template_file)
        template_filename = (
            kwargs["unit_name"] if "." not in template_filename else template_filename.split(".")[1]
        )
        template_filename += ".py"
        successfully_created_files.append(os.path.join(target_dir, template_filename))
        # Render and write the template into the resulting file
        with open(os.path.join(target_dir, template_filename), "w") as template_handle:
            template_handle.write(env.get_template(template_file).render(**kwargs))
        log.minor_success(f"module {log.path_style(template_filename)}", "created")

    log.decrease_indent()

    # Add the registration point to the set of file
    successfully_created_files.append(os.path.join(perun_dev_dir, template_type, "../__init__.py"))
    if template_type in ("postprocess", "collect", "view"):
        successfully_created_files.append(os.path.join(perun_dev_dir, "utils", "../__init__.py"))
    log.minor_info("New module has to be registered at", end=":\n")
    log.increase_indent()
    log.minor_info(log.path_style(f"{os.path.join(template_type, '__init.py')}"))
    log.minor_info(log.path_style(f"{os.path.join('utils', '__init.py')}"))
    log.decrease_indent()

    # Unless specified in other way, open all of the files in the w.r.t the general.editor key
    if not no_edit:
        editor = config.lookup_key_recursively("general.editor")
        log.minor_status("Opening the files in", status=f"{log.cmd_style(editor)}")
        try:
            commands.run_external_command([editor] + successfully_created_files[::-1])
        except Exception as inner_exception:
            raise ExternalEditorErrorException(editor, str(inner_exception))
