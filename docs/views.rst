.. _views-overview:

Visualizations Overview
=======================

.. todo::
   Add examples of outputs for each of the visualization

.. automodule:: perun.view

.. _views-list:

Supported Visualizations
------------------------

Perun currently supports the following visualizations:

    1. :ref:`views-bars`, customizable plot for visualizing data in bars-like format. The output
       is generated as an interactive HTML file using the Bokeh library, where one can move and
       resize the graph. Works on all of the kinds of profiles.

    2. :ref:`views-flow`, customizable plot for visualizing data in classic flow format. The output
       is generated as an interactive HTML file using the Bokeh library, where one can move and
       resize the graph. Works on all of the kinds of profiles.

    3. :ref:`views-flame-graph`, an interface for Perl script of Brendan Gregg, that converts the
       (currently only memory profiles) profile to its format and visualize the resources depending
       on the trace of the resources.

    4. :ref:`views-scatter`, a customizable scatter plot for visualizing the data in 2D format.
       Moreover in this visualization, regression models are output as well.

    5. :ref:`views-heapmap`, a heap map of allocation resources. The output is dependent on ncurses
       library and hence can currently be used only from UNIX terminals.

Moreover, you can easily create your own visualization and register them in Perun for further usage
as is described in :ref:`views-custom`. The format and the output is of your choice, it only has
to be built over the format as described in :ref:`profile-spec`.

.. _views-bars:

Bars Plot
~~~~~~~~~

.. automodule:: perun.view.bars

.. automodule:: perun.view.bars.run

Command Line Interface
""""""""""""""""""""""

.. click:: perun.view.bars.run:bars
   :prog: perun show bars

.. _views-bars-examples:

Examples of Output
""""""""""""""""""

.. _views-flame-graph:

Flame Graph
~~~~~~~~~~~

.. automodule:: perun.view.flamegraph

.. automodule:: perun.view.flamegraph.run

Command Line Interface
""""""""""""""""""""""

.. click:: perun.view.flamegraph.run:flamegraph
   :prog: perun show flamegraph

.. _views-flamegraph-examples:

Examples of Output
""""""""""""""""""

.. _views-flow:

Flow Plot
~~~~~~~~~

.. automodule:: perun.view.flow

.. automodule:: perun.view.flow.run

Command Line Interface
""""""""""""""""""""""

.. click:: perun.view.flow.run:flow
   :prog: perun show flow

.. _views-flow-examples:

Examples of Output
""""""""""""""""""

.. _views-heapmap:

Heap Map
~~~~~~~~

.. automodule:: perun.view.heapmap

.. automodule:: perun.view.heapmap.run

Command Line Interface
""""""""""""""""""""""

.. click:: perun.view.heapmap.run:heapmap
   :prog: perun show heapmap

.. _views-heapmap-examples:

Examples of Output
""""""""""""""""""

.. _views-scatter:

Scatter Plot
~~~~~~~~~~~~

.. automodule:: perun.view.scatter

.. automodule:: perun.view.scatter.run

Command Line Interface
""""""""""""""""""""""

.. click:: perun.view.scatter.run:scatter
   :prog: perun show scatter

.. _views-scatter-examples:

Examples of Output
""""""""""""""""""

.. _views-custom:

Creating your own Visualization
-------------------------------

You can register your new visualization as follows:

    1. Create a new module in ``perun/view`` with the following structure::

        /perun
        |-- /collect
            |-- /new_module
                |-- __init__.py
                |-- run.py
            |-- /complexity
            ...

    2. Implement the ``run.py`` module with the command line interface function. This function will
       be called when Perun is run from command line as ``perun show new_module``.

    3. Verify that registering did not break anything in the Perun and optionally reinstall Perun::

        make test
        make install
