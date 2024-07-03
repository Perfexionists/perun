"""
Performance profiles originate either from the user's own means (i.e. by
building their own collectors and generating the profiles w.r.t
:ref:`profile-spec`) or using one of the collectors from Perun's tool suite.

Perun can collect profiling data in two ways:

    1. By **Directly running collectors** through ``perun collect`` command,
       that generates profile using a single collector with given collector
       configuration. The resulting profiles are not postprocessed in any way.

    2. By **Using job specification** either as a single run of batch of
       profiling jobs using ``perun run job`` or according to the specification
       of the so-called job matrix using ``perun run matrix`` command.

The format of resulting profiles is w.r.t. :ref:`profile-spec`. The
:preg:`origin` is set to the current ``HEAD`` of the wrapped repository.
However, note that uncommited changes may skew the resulting profile and Perun
cannot guard your project against this. Further, :preg:`collector_info` is
filled with configuration of the run collector.

All  automatically generated profiles are stored in the ``.perun/jobs/``
directory as a file with the ``.perf`` extension. The filename is by default
automatically generated according to the following template::

        bin-collector-workload-timestamp.perf

Profiles can be further registered and stored in persistent storage using
``perun add`` command.  Then both stored and pending profiles (i.e. those not
yet assigned) can be postprocessed using the ``perun postprocessby`` or
interpreted using available interpretation techniques using ``perun show``.
Refer to :doc:`cli`, :doc:`postprocessors` and :doc:`views` for more details
about running command line commands, capabilities of postprocessors and
interpretation techniques respectively. Internals of perun storage is described
in :doc:`internals`.

.. image:: /../figs/architecture-collectors.*
    :width: 100%
    :align: center
"""
from __future__ import annotations
from typing import Callable, Any


def lazy_get_cli_commands() -> list[Callable[..., Any]]:
    """
    Lazily imports CLI commands
    """
    import perun.collect.bounds.run as bounds_run
    import perun.collect.complexity.run as complexity_run
    import perun.collect.kperf.run as kperf_run
    import perun.collect.memory.run as memory_run
    import perun.collect.time.run as time_run
    import perun.collect.trace.run as trace_run
    import perun.collect.web.run as web_run

    return [
        bounds_run.bounds,
        complexity_run.complexity,
        kperf_run.kperf,
        memory_run.memory,
        time_run.time,
        trace_run.trace,
        web_run.web,
    ]
