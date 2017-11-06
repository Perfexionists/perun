.. _jobs-automation:

Automating Runs
===============

Profiles are generated either manually on your own, or you can use Perun ``runner`` infrastructure
to partially automate the generation process. Perun allows either to run the jobs through the
stored configuration (either in local or shared configuration c.f. :doc:`config`) or through
single job specifications.

All of the generated profiles are stored in ``.perun/jobs`` directory with the following name
of the template::

   command-collector-workload-Y-m-d-H-M-S.perf

Where ``command`` corresponds to the name of the application (or script), for which we collected
the data using ``collector`` on ``workload`` at given specified date.

Runner CLI
----------

:doc:`cli` of Perun contains two commands---first for running one specified batch of jobs and other
for running the pre-configured matrix in YAML format (see :ref:`jobs-matrix` for full
specification).

.. click:: perun.cli:job
   :prog: perun run job

.. click:: perun.cli:matrix
   :prog: perun run matrix

.. _jobs-overview:

Overview of Jobs
----------------

As one profiling of our application, we consider that first the data are collected by profiler
(or data collector) and can be further augmented by ordered list of postprocessors (e.g. for
filtering out unwanted data, normalizing or scaling the amounts, etc.). As results we generate
one profile for each application configuration and each profiling job.

The configuration of application is composed of three parts (two being optional):

   1. **Command**, i.e. either the binary or wrapper script that is executed as one command from the
   terminal and ends with success or failure. E.g. running ``perun`` itself, ``ls`` or
   ``./my_binary`` are examples of commands.

   2. **Arguments** (`optional`), i.e. set of parameters or arguments, that are supplied to the
   command. The intuition behind arguments is to differentiate either various optimization levels or
   profile different configurations of ones program. E.g. ``log``, ``-al`` or ``-O2 -v`` are
   examples of command paramters.

   3. **Workloads** (`optional`), i.e. different inputs of command. While this is similar to the
   arguments, it allows more finer specification of jobs, when we want to profile our program on
   workloads with different sizes (since degradations usually manifest under bigger workloads).
   E.g. ``HEAD`` or ``/dir/subdir`` or ``<< "Hello world"`` are examples of workloads.

Internally cartesian product of commands, arguments and workloads is performed yielding the set of
profiling jobs. Then for each of the set (like e.g. ``perun log HEAD``, ```ls -al /dir/subdir`` or
``./my_binary -O2 -v << "Hello world"``) we run specified collectors and finally the list of
postprocessors.

Each collector (resp. postprocessor) runs in three phases (two being optional). First function
``before()`` is executed, where the collector (postprocessor) can prepare additional steps before
actual collection (postprocessing) of the data, like e.g. compiling custom binaries. Then the actual
``collect()`` (``postprocess()``) is executed, which runs the given job with specified collection
(postprocessing) unit yield profile (potentially in raw format). Finally ``after()`` phases is run,
which can further postprocess the generated profile (after success), e.g. by required filtering of
data or by transforming raw profiles to :ref:`profile-format`. See (:doc:`collectors` and
:doc:`postprocessors` for more detailed description of units).

The overall process can be seen as follows::

   for (cmd, argument, workload) in jobs:
      for collector in collectors:
         collector.before(cmd, argument, workload)
         collector.collect(cmd, argument, workload)
         profile = collector.after()
         for postprocessor in postprocessors:
            postprocessor.before(profile)
            postprocessor.postprocess(profile)
            profile = postprocessor.after(profile)

.. image:: /../figs/lifetime-of-profile.*
   :width: 100%
   :align: center

.. _jobs-matrix:

Job Matrix Format
-----------------

In order to maximize the automation of running jobs you can specify in Perun config the
specification of commands, arguments, workloads, collectors and postprocessors (and their internal
configurations). Both the config and the specification of job matrix is based on YAML format.

Example of the job matrix is as follows::

   cmds:
      - perun

   args:
      - log
      - log --short

   workloads:
      - HEAD
      - HEAD~1

   collectors:
      - name: time

   postprocessors:
      - name: normalizer
      - name: regression_analysis
        params:
         - method: full
         - steps: 10


Given matrix will create four jobs (``perun log HEAD``, ``perun log HEAD~1``, ``perun log --short
HEAD`` and ``perun log --short HEAD~1``) which will be issued for runs. Each job will be collected
by :ref:`collectors-time` and then postprocessed first by :ref:`postprocessors-normalizer` and then
by :ref:`postprocessors-regression-analysis` with specification ``{'method': 'full', 'steps': 10``.

In order to configure the matrix for your project run ``perun config --edit`` and add the
following options.

.. matrixunit:: cmds

   List of commands which will be profiled by set of collectors.

.. matrixunit:: args

   List of arguments (or parameters) which are supplied to profiled commands.

.. matrixunit:: workloads

   List of workloads which are supplied to profiled commands.

.. matrixunit:: collectors

   List of collectors which will be used to collect data for the given commands, arguments and
   workloads. Each collector is specified by its `name` and additional `params` which corresponds to
   the dictionary of (key, value) parameters. Note that the same collector can be specified more
   than once (for cases, when one needs different collector configurations)

.. matrixunit:: postprocessors

   List of postprocessors which are used after the successful collection of the profiling data.
   Each postprocessor is specified by its `name` and additional `params` which corresponds to the
   dictionary of (key, value) parameters. Note that the same postprocessor can be specified more
   than just once.
