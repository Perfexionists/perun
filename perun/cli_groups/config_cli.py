"""Group of CLI commands used for manipulation with config"""

from __future__ import annotations

# Standard Imports
from typing import Any

# Third-Party Imports
import click

# Perun Imports
from perun.logic import commands
from perun.utils import log as perun_log
from perun.utils.common import cli_kit
from perun.utils.exceptions import (
    MissingConfigSectionException,
    ExternalEditorErrorException,
)


@click.group()
@click.option(
    "--local",
    "-l",
    "store_type",
    flag_value="local",
    help="Sets the local config, i.e. ``.perun/local.yml``, as the source config.",
)
@click.option(
    "--shared",
    "-s",
    "store_type",
    flag_value="shared",
    help="Sets the shared config, i.e. ``shared.yml.``, as the source config",
)
@click.option(
    "--nearest",
    "-n",
    "store_type",
    flag_value="recursive",
    default=True,
    help=(
        "Sets the nearest suitable config as the source config. The"
        " lookup strategy can differ for ``set`` and "
        "``get``/``edit``."
    ),
)
@click.pass_context
def config(ctx: click.Context, **kwargs: Any) -> None:
    """Manages the stored local and shared configuration.

    Perun supports two external configurations:

        1. ``local.yml``: the local configuration stored in ``.perun``
           directory, containing the keys such as specification of wrapped
           repository or job matrix used for quick generation of profiles (run
           ``perun run matrix --help`` or refer to :doc:`jobs` for information
           how to construct the job matrix).

        2. ``shared.yml``:  the global configuration shared by all perun
           instances, containing shared keys, such as text editor, formatting
           string, etc.

    The syntax of the ``<key>`` in most operations consists of section
    separated by dots, e.g. ``vcs.type`` specifies ``type`` key in ``vcs``
    section. The lookup of the ``<key>`` can be performed in three modes,
    ``--local``, ``--shared`` and ``--nearest``, locating or setting the
    ``<key>`` in local, shared or nearest configuration respectively (e.g. when
    one is trying to get some key, there may be nested perun instances that do
    not contain the given key). By default, perun operates in the nearest
    config mode.

    Refer to :doc:`config` for full description of configurations and
    :ref:`config-types` for full list of configuration options.

    E.g. using the following one can retrieve the type of the nearest perun
    instance wrapper:

    .. code-block:: bash

        $ perun config get vcs.type
        vcs.type: git
    """
    if kwargs.get("store_type") == "local":
        commands.try_init()
    ctx.obj = kwargs


@config.command("get")
@click.argument(
    "key",
    required=True,
    metavar="<key>",
    type=click.STRING,
    callback=cli_kit.config_key_validation_callback,
)
@click.pass_context
def config_get(ctx: click.Context, key: str) -> None:
    """Looks up the given ``<key>`` within the configuration hierarchy and returns
    the stored value.

    The syntax of the ``<key>`` consists of section separated by dots, e.g.
    ``vcs.type`` specifies ``type`` key in ``vcs`` section. The lookup of the
    ``<key>`` can be performed in three modes, ``--local``, ``--shared`` and
    ``--nearest``, locating the ``<key>`` in local, shared or nearest
    configuration respectively (e.g. when one is trying to get some key, there
    may be nested perun instances that do not contain the given key). By
    default, perun operates in the nearest config mode.

    Refer to :doc:`config` for full description of configurations and
    :ref:`config-types` for full list of configuration options.

    E.g. using the following can retrieve the type of the nearest perun
    wrapper:

    .. code-block:: bash

        $ perun config get vcs.type
        vcs.type: git

        $ perun config --shared get general.editor
        general.editor: vim
    """
    try:
        commands.config_get(ctx.obj["store_type"], key)
    except MissingConfigSectionException as mcs_err:
        perun_log.error(f"error while getting key '{key}': {mcs_err}")


@config.command("set")
@click.argument(
    "key",
    required=True,
    metavar="<key>",
    type=click.STRING,
    callback=cli_kit.config_key_validation_callback,
)
@click.argument("value", required=True, metavar="<value>")
@click.pass_context
def config_set(ctx: click.Context, key: str, value: Any) -> None:
    """Sets the value of the ``<key>`` to the given ``<value>`` in the target
    configuration file.

    The syntax of the ``<key>`` corresponds of section separated by dots, e.g.
    ``vcs.type`` specifies ``type`` key in ``vcs`` section. Perun sets the
    ``<key>`` in three modes, ``--local``, ``--shared`` and ``--nearest``,
    which sets the ``<key>`` in local, shared or nearest configuration
    respectively (e.g.  when one is trying to get some key, there may be nested
    perun instances that do not contain the given key). By default, perun will
    operate in the nearest config mode.

    The ``<value>`` is arbitrary depending on the key.

    Refer to :doc:`config` for full description of configurations and
    :ref:`config-types` for full list of configuration options and their
    values.

    E.g. using the following can set the log format for nearest perun instance
    wrapper:

    .. code-block:: bash

        $ perun config set format.shortlog "| %source% | %collector% |"
        format.shortlog: | %source% | %collector% |
    """
    commands.config_set(ctx.obj["store_type"], key, value)


@config.command("edit")
@click.pass_context
def config_edit(ctx: click.Context) -> None:
    """Edits the configuration file in the external editor.

    The used editor is specified by the :ckey:`general.editor` option,
    specified in the nearest perun configuration..

    Refer to :doc:`config` for full description of configurations and
    :ref:`config-types` for full list of configuration options.
    """
    try:
        commands.config_edit(ctx.obj["store_type"])
    except (
        ExternalEditorErrorException,
        MissingConfigSectionException,
    ) as editor_exception:
        perun_log.error(f"could not invoke external editor: {editor_exception}")


@config.command("reset")
@click.argument("config_template", required=False, default="master", metavar="<template>")
@click.pass_context
def config_reset(ctx: click.Context, config_template: str) -> None:
    """Resets the configuration file to a sane default.

    If we are resetting the local configuration file we can specify a <template> that
    will be used to generate a predefined set of options. Currently, we support the following:

      1. **user** configuration is meant for beginner users, that have no experience with Perun and
      have not read the documentation thoroughly. This contains a basic preconfiguration that should
      be applicable for most of the projects---data are collected by :ref:`collectors-time` and are
      automatically registered in the Perun after successful run. The performance is checked using
      the :ref:`degradation-method-aat`. Missing profiling info will be looked up automatically.

      2. **developer** configuration is meant for advanced users, that have some understanding of
      profiling and/or Perun. Fair amount of options are up to the user, such as the collection of
      the data and the commands that will be profiled.

      3. **master** configuration is meant for experienced users. The configuration will be mostly
      empty.

    See :ref:`config-templates` to learn more about predefined configuration options.
    """
    commands.config_reset(ctx.obj["store_type"], config_template)
