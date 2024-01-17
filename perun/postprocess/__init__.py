"""
Performance profiles originate either from the user's own means (i.e. by
building their own collectors and generating the profiles w.r.t
:ref:`profile-spec`) or using one of the collectors from Perun's tool suite.

Perun can postprocess such profiling data in two ways:

    1. By **Directly running postprocessors** through ``perun postprocessby``
       command, that takes the profile (either stored or pending) and uses a
       single postprocessor with given configuration.

    2. By **Using job specification** either as a single run of batch of
       profiling jobs using ``perun run job`` or according to the specification
       of the so-called job matrix using ``perun run matrix`` command.

The format of input and resulting profiles has to be w.r.t.
:ref:`profile-spec`. By default, new profiles are created. The :preg:`origin`
set to the origin of the original profile. Further, :preg:`postprocessors` is
extended with configuration of the run postprocessor (appended at the end).

All postprocessed profiles are stored in the ``.perun/jobs/`` directory
as a file with the ``.perf`` extension. The filename is by default
automatically generated according to the following template::

        bin-collector-workload-timestamp.perf

Profiles can be further registered and stored in persistent storage using
``perun add`` command.  Then both stored and pending profiles (i.e. those not
yet assigned) can be interpreted using available interpretation techniques
using ``perun show``.  Refer to :doc:`cli` and :doc:`views` for more details
about running command line commands and capabilities fo interpretation
techniques respectively. Internals of perun storage is described in
:doc:`internals`.

.. image:: /../figs/architecture-postprocessors.*
    :width: 100%
    :align: center
"""
from __future__ import annotations
from typing import Callable, Any


def lazy_get_cli_commands() -> list[Callable[..., Any]]:
    """
    Lazily imports CLI commands
    """
    import perun.postprocess.kernel_regression.run as kernel_regression_run
    import perun.postprocess.moving_average.run as moving_average_run
    import perun.postprocess.regression_analysis.run as regression_analysis_run
    import perun.postprocess.regressogram.run as regressogram_run

    return [
        kernel_regression_run.kernel_regression,
        moving_average_run.moving_average,
        regression_analysis_run.regression_analysis,
        regressogram_run.regressogram,
    ]
