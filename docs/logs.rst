.. _logs-overview:

Customize Logs and Statuses
===========================

``log`` and ``status`` commands print information about wrapped repository annotated by performance
profiles. ``log`` outputs the minor versions history for a current major version, along with
the information about annotated profiles. ``status`` shows information of given minor version,
along with precise information about associated profiles, how they were computed, etc.

Outputs of both ``log`` and ``status`` can be customized c.f. :ref:`logs-log` and :ref`logs-status`.

.. _logs-status:

Customizing Statuses
--------------------

Output of ``status`` can be modified by the formatting string specified by
:ckey:`global.profile_info_fmt`. The format consists of raw delimiters and special tags, which can
be used to output concrete information about profiles, like e.g. its commands, types, time, etc.

E.g. the following formatting string::

     ┃ [type] ┃ [cmd] ┃ [workload] ┃ [collector]  ┃ ([time]) ┃ [id] ┃

will yield the following status by running ``perun status`` (both for stored and pending
profiles::

    ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════▣
      id ┃   type  ┃  cmd   ┃ workload ┃  args  ┃ collector  ┃         time        ┃                        id                        ┃
    ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════▣
     0@p ┃ [mixed] ┃ target ┃ hello    ┃        ┃ complexity ┃ 2017-09-07 14:41:49 ┃ .perun/jobs/big.perf                             ┃
     1@p ┃ [time ] ┃ perun  ┃          ┃ status ┃ time       ┃ 2017-10-19 12:30:29 ┃ .perun/jobs/perun-time--2017-10-19-10-30-29.perf ┃
     2@p ┃ [time ] ┃ perun  ┃          ┃ --help ┃ time       ┃ 2017-10-19 12:30:31 ┃ .perun/jobs/perun-time--2017-10-19-10-30-30.perf ┃
    ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════▣

Note that the first ``id`` in the ``status`` output is fixed and represents a "tag", which can be
used for ``add``, ``rm``, ``show`` and ``postprocessby`` commands as a quick identifiers of concrete
profiles. Following types and specifications can be included in the formatting string:

``[type]``:
    Shows the most generic type of the profile regarding the collected resources, e.g. memory, time,
    mixed, etc.

``[cmd]``:
    Command for which the data were collected for, i.e. the binary or script that was executed and
    profiled.

``[args]``:
    Arguments (or parameters) which were supplied to the profiled command.

``[workload]``:
    Workload which was supplied to the profiled command, i.e. some inputs of the profiled program,
    script or binary.

``[collector]``:
    Collector which was used for collection of the data.

``[time]``:
    Time when the profile was generated in format `YEAR-MONTH-DAY HOURS:MINUTES:SECONDS`.

``[id]``:
    Identification of the profile, i.e. the name of the generated profile and its path.

.. todo::
    Add rest of the missing options.

.. _logs-log:

Customizing Logs
----------------

Output of ``log --short`` can be modified by the formatting string specified by
:ckey:`global.minor_version_info_fmt`. Formatting string can display both raw characters
(delimiters, etc.) and information about minor version (e.g. minor version description, number of
assigned profiles, etc.) specified by tags.

E.g. the following formatting string::

    '[id:6] ([stats]) [desc]'

will yield the following output by running ``perun log --short``::

    minor   (a|m|x|t profiles) info
    53d35c  (2|0|2|0 profiles) Add deleted jobs directory
    07f2b4  (1|0|1|0 profiles) Add necessary files for perun to work on this repo.
    bd3dc3  ---no--profiles--- root

Following types and specifications can be included in the formatting string:

``[id:num]``:
    Identification of the minor version. E.g. in ``git`` this corresponds to the SHA of one commit.
    ``num`` can be used to shorten the displayed identification to ``num`` characters.

``[stats]``:
    Short summary overall number of profiles (``a``) and number of memory (``m``), mixed (``x``)
    and time (``t``) profiles.

``[desc]``:
    Short description of the minor version. E.g. in ``git`` this corresponds to the short commit
    message.

.. todo::
    Add rest of the missing options.
