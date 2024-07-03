"""
Performance profiles originate either from the user's own means (i.e. by
building their own collectors and generating the profiles w.r.t
:ref:`profile-spec`) or using one of the collectors from Perun's tool suite.

Perun can can interpret the profiling data in several ways:

    1. By **directly running interpretation modules** through ``perun show``
       command, that takes the profile w.r.t. :ref:`profile-spec` and uses
       various output backends (e.g. Bokeh_, ncurses_ or plain terminal). The
       output method and format is up to the authors.

    2. By **using python interpreter** together with internal modules for
       manipulation, conversion and querying the profiles (refer to
       :ref:`profile-api`, :ref:`profile-query-api`, and
       :ref:`profile-conversion-api`) and external statistical libraries, like
       e.g. using pandas_.

The format of input profiles has to be w.r.t. :ref:`profile-spec`, in
particular the interpreted profiles should contain the :pkey:`resources` region
with data.

Automatically generated profiles are stored in the ``.perun/jobs/``
directory as a file with the ``.perf`` extension. The filename is by default
automatically generated according to the following template::

        bin-collector-workload-timestamp.perf

Refer to :doc:`cli`, :doc:`jobs`, :doc:`collectors` and :doc:`postprocessors`
for more details about running command line commands, generating batch of jobs,
capabilities of collectors and postprocessors techniques respectively.
Internals of perun storage is described in :doc:`internals`.

Note that interface of show allows one to use `index` and `pending` tags of
form ``i@i`` and ``i@p`` respectively, which serve as a quality-of-life feature
for easy specification of visualized profiles.

.. image:: /../figs/architecture-views.*
    :width: 100%
    :align: center

.. _Bokeh: https://bokeh.pydata.org/en/latest/
.. _ncurses: https://www.gnu.org/software/ncurses/ncurses.html
.. _pandas: https://pandas.pydata.org/
"""
from __future__ import annotations

from typing import Callable, Any


def lazy_get_cli_commands() -> list[Callable[..., Any]]:
    """
    Lazily imports CLI commands
    """
    import perun.view.bars.run as bars_run
    import perun.view.flamegraph.run as flamegraph_run
    import perun.view.flow.run as flow_run
    import perun.view.scatter.run as scatter_run
    import perun.view.tableof.run as tableof_run
    import perun.view.web.run as web_run

    return [
        bars_run.bars,
        flamegraph_run.flamegraph,
        flow_run.flow,
        scatter_run.scatter,
        tableof_run.tableof,
        web_run.web,
    ]
