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

.. click:: perun.cli:config
   :prog: perun config

.. click:: perun.cli:config_get
   :prog: perun config get

.. click:: perun.cli:config_set
   :prog: perun config set

.. click:: perun.cli:config_edit
   :prog: perun config edit

.. click:: perun.cli:add
   :prog: perun add

.. click:: perun.cli:rm
   :prog: perun rm

.. click:: perun.cli:status
   :prog: perun status

.. click:: perun.cli:log
   :prog: perun log

.. click:: perun.cli:run
   :prog: perun run

.. click:: perun.cli:job
   :prog: perun run job

.. click:: perun.cli:matrix
   :prog: perun run matrix

.. click:: perun.cli:check_group
   :prog: perun check

.. click:: perun.cli:check_head
   :prog: perun check head

.. click:: perun.cli:check_all
   :prog: perun check all

.. click:: perun.cli:check_profiles
   :prog: perun check profiles

.. _cli-collect-ref:

Collect Commands
----------------

.. click:: perun.cli:collect
   :prog: perun collect

.. _cli-collect-units-ref:

Collect units
~~~~~~~~~~~~~

.. click:: perun.collect.complexity.run:complexity
   :prog: perun collect complexity

.. click:: perun.collect.memory.run:memory
   :prog: perun collect memory

.. click:: perun.collect.time.run:time
   :prog: perun collect time

.. _cli-postprocess-ref:

Postprocess Commands
--------------------

.. click:: perun.cli:postprocessby
   :prog: perun postprocessby

.. _cli-postprocess-units-ref:

Postprocess units
~~~~~~~~~~~~~~~~~

.. _cli-views-ref:

.. click:: perun.postprocess.normalizer.run:normalizer
   :prog: perun postprocessby normalizer

.. click:: perun.postprocess.regression_analysis.run:regression_analysis
   :prog: perun postprocessby regression_analysis

Show Commands
-------------

.. click:: perun.cli:show
   :prog: perun show

.. _cli-views-units-ref:

Show units
~~~~~~~~~~

.. click:: perun.view.alloclist.run:alloclist
   :prog: perun show alloclist

.. click:: perun.view.bars.run:bars
   :prog: perun show bars

.. click:: perun.view.flamegraph.run:flamegraph
   :prog: perun show flamegraph

.. click:: perun.view.flow.run:flow
   :prog: perun show flow

.. click:: perun.view.heapmap.run:heapmap
   :prog: perun show heapmap

.. click:: perun.view.scatter.run:scatter
   :prog: perun show scatter

.. _cli-utils-ref:

Utility Commands
----------------

.. click:: perun.cli:utils_group
   :prog: perun utils

.. click:: perun.cli:create
   :prog: perun utils create
