.. _cli-overview:

Command Line Interface
======================

.. automodule:: perun.cli

.. click:: perun.cli:cli
   :prog: perun

.. _cli-main-ref:

Perun Commands
--------------

.. click:: perun.cli:init
   :prog: perun init

.. click:: perun.cli_groups.config_cli:config
   :prog: perun config

.. click:: perun.cli_groups.config_cli:config_get
   :prog: perun config get

.. click:: perun.cli_groups.config_cli:config_set
   :prog: perun config set

.. click:: perun.cli_groups.config_cli:config_edit
   :prog: perun config edit

.. click:: perun.cli:add
   :prog: perun add

.. click:: perun.cli:remove
   :prog: perun rm

.. click:: perun.cli:status
   :prog: perun status

.. click:: perun.cli:log
   :prog: perun log

.. click:: perun.cli_groups.run_cli:run
   :prog: perun run

.. click:: perun.cli_groups.run_cli:job
   :prog: perun run job

.. click:: perun.cli_groups.run_cli:matrix
   :prog: perun run matrix

.. click:: perun.cli_groups.check_cli:check_group
   :prog: perun check

.. click:: perun.cli_groups.check_cli:check_head
   :prog: perun check head

.. click:: perun.cli_groups.check_cli:check_all
   :prog: perun check all

.. click:: perun.cli_groups.check_cli:check_profiles
   :prog: perun check profiles

.. click:: perun.cli:fuzz_cmd
   :prog: perun fuzz

.. _cli-collect-ref:

Collect Commands
----------------

.. click:: perun.cli_groups.collect_cli:collect
   :prog: perun collect

.. _cli-collect-units-ref:

Collect units
~~~~~~~~~~~~~

.. click:: perun.collect.trace.run:trace
   :prog: perun collect trace

.. click:: perun.collect.memory.run:memory
   :prog: perun collect memory

.. click:: perun.collect.time.run:time
   :prog: perun collect time

.. click:: perun.collect.bounds.run:bounds
   :prog: perun collect bounds

.. _cli-postprocess-ref:

Postprocess Commands
--------------------

.. click:: perun.cli:postprocessby
   :prog: perun postprocessby

.. _cli-postprocess-units-ref:

Postprocess units
~~~~~~~~~~~~~~~~~

.. _cli-views-ref:

.. click:: perun.postprocess.regression_analysis.run:regression_analysis
   :prog: perun postprocessby regression_analysis

.. click:: perun.postprocess.regressogram.run:regressogram
   :prog: perun postprocessby regressogram

.. click:: perun.postprocess.moving_average.run:moving_average
   :prog: perun postprocessby moving_average

.. click:: perun.postprocess.moving_average.run:simple_moving_average
   :prog: perun postprocessby moving_average sma

.. click:: perun.postprocess.moving_average.run:simple_moving_median
   :prog: perun postprocessby moving_average smm

.. click:: perun.postprocess.moving_average.run:exponential_moving_average
   :prog: perun postprocessby moving_average ema

.. click:: perun.postprocess.kernel_regression.run:kernel_regression
   :prog: perun postprocessby kernel-regression

.. click:: perun.postprocess.kernel_regression.run:estimator_settings
   :prog: perun postprocessby kernel-regression estimator-settings

.. click:: perun.postprocess.kernel_regression.run:user_selection
   :prog: perun postprocessby kernel-regression user-selection

.. click:: perun.postprocess.kernel_regression.run:method_selection
   :prog: perun postprocessby kernel-regression method-selection

.. click:: perun.postprocess.kernel_regression.run:kernel_smoothing
   :prog: perun postprocessby kernel-regression kernel-smoothing

.. click:: perun.postprocess.kernel_regression.run:kernel_ridge
   :prog: perun postprocessby kernel-regression kernel-ridge

Show Commands
-------------

.. click:: perun.cli:show
   :prog: perun show

.. _cli-views-units-ref:

Show units
~~~~~~~~~~

.. click:: perun.view.bars.run:bars
   :prog: perun show bars

.. click:: perun.view.flamegraph.run:flamegraph
   :prog: perun show flamegraph

.. click:: perun.view.flow.run:flow
   :prog: perun show flow

.. click:: perun.view.scatter.run:scatter
   :prog: perun show scatter

.. _cli-utils-ref:

Utility Commands
----------------

.. click:: perun.cli_groups.utils_cli:utils_group
   :prog: perun utils

.. click:: perun.cli_groups.utils_cli:create
   :prog: perun utils create

.. click:: perun.cli_groups.utils_cli:temp_group
   :prog: perun temp

.. click:: perun.cli_groups.utils_cli:temp_list
   :prog: perun temp list

.. click:: perun.cli_groups.utils_cli:temp_sync
   :prog: perun temp sync

.. click:: perun.cli_groups.utils_cli:stats_group
   :prog: perun stats

.. click:: perun.cli_groups.utils_cli:stats_list_files
   :prog: perun stats list-files

.. click:: perun.cli_groups.utils_cli:stats_list_versions
   :prog: perun stats list-versions

.. click:: perun.cli_groups.utils_cli:stats_delete_group
   :prog: perun stats delete

.. click:: perun.cli_groups.utils_cli:stats_delete_file
   :prog: perun stats delete file

.. click:: perun.cli_groups.utils_cli:stats_delete_minor
   :prog: perun stats delete minor

.. click:: perun.cli_groups.utils_cli:stats_delete_all
   :prog: perun stats delete ll

.. click:: perun.cli_groups.utils_cli:stats_clean
   :prog: perun stats clean

.. click:: perun.cli_groups.utils_cli:stats_sync
   :prog: perun stats sync
