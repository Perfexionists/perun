.. _views-overview:

Visualizations Overview
=======================

.. automodule:: perun.view

.. _views-list:

Supported Visualizations
------------------------

.. _tabulate: https://pypi.org/project/tabulate/
.. _Bokeh: https://bokeh.pydata.org/en/latest/
.. _ncurses: https://www.gnu.org/software/ncurses/ncurses.html

Perun's tool suite currently contains the following visualizations:

    1. :ref:`views-bars` visualizes the data as bars, with moderate customization possibilities.
       The output is generated as an interactive HTML file using the Bokeh_ library, where one can
       e.g. move or resize the graph. `Bars` supports high number of profile types.

    2. :ref:`views-flow` visualizes the data as flow (i.e. classical continuous graph), with
       moderate customization possiblities. The output is generated as an interactive HTML file
       using the Bokeh_ library, where one can move and resize the graph. `Flow` supports high
       number of profile types.

    3. :ref:`views-flame-graph` is an interface for Perl script of Brendan Gregg, that converts the
       (currently limited to memory profiles) profile to an internal format and visualize the
       resources as stacks of portional resource consumption depending on the trace of the
       resources.

    4. :ref:`views-scatter` visualizes the data as points on two dimensional grid, with moderate
       customization possibilities. This visualization also display regression models, if the input
       profile was postprocessed by :ref:`postprocessors-regression-analysis`.

    5. :ref:`views-tableof` transforms either the resources or models of the profile into a tabular
       representation. The table can be further modified by (1) changing the format (see tabulate_
       for table formats), (2) limiting rows or columns displayed, or (3) sorting w.r.t specified
       keys.

All of the listed visualizations can be run from command line. For more information about command
line interface for individual visualization either refer to :ref:`cli-collect-units-ref` or to
corresponding subsection of this chapter.

For a brief tutorial how to create your own visualization module and register it in Perun for
further usage refer to :ref:`views-custom`. The format and the output is of your choice, it only
has to be built over the format as described in :ref:`profile-spec` (or can be based over one of
the conversions, see :ref:`profile-conversion-api`).

.. _views-bars:

Bars Plot
~~~~~~~~~

.. automodule:: perun.view.bars

Overview and Command Line Interface
"""""""""""""""""""""""""""""""""""

.. click:: perun.view.bars.run:bars
   :prog: perun show bars

.. _views-bars-examples:

Examples of Output
""""""""""""""""""

.. image:: /../examples/complexity-bars.*

The :ref:`views-bars` above shows the overall sum of the running times for each
``structure-unit-size`` for the ``SLList_search`` function collected by
:ref:`collectors-trace`. The interpretation highlights that the most of the consumed running
time were over the single linked lists with 41 elements.

.. image:: /../examples/memory-bars-stacked.*

The `bars` above shows the `stacked` view of number of memory allocations made per each snapshot
(with sampling of ``1`` second). Each bar shows overall number of memory operations, as well as
proportional representation of different types of memory (de)allocation. It can also be seen that
``free`` is called approximately the same time as allocations, which signifies that everything was
probably freed.

.. image:: /../examples/memory-bars-sum-grouped.*

The `bars` above shows the `grouped` view of sum of memory allocation of the same type per each
snapshot (with sampling of ``0.5`` seconds). Grouped pars allows fast comparison of total amounts
between different types. E.g. ``malloc`` seems to allocated the most memory per each snapshot.

.. _views-flame-graph:

Flame Graph
~~~~~~~~~~~

.. automodule:: perun.view.flamegraph

Overview and Command Line Interface
"""""""""""""""""""""""""""""""""""

.. click:: perun.view.flamegraph.run:flamegraph
   :prog: perun show flamegraph

.. _views-flamegraph-examples:

.. image:: /../examples/memory-flamegraph.*

The :ref:`views-flame-graph` is an efficient visualization of inclusive consumption of resources.
The width of the base of one flame shows the bottleneck and hotspots of profiled binaries.

Examples of Output
""""""""""""""""""

.. _views-flow:

Flow Plot
~~~~~~~~~

.. automodule:: perun.view.flow

Overview and Command Line Interface
"""""""""""""""""""""""""""""""""""

.. click:: perun.view.flow.run:flow
   :prog: perun show flow

.. _views-flow-examples:

Examples of Output
""""""""""""""""""

.. image:: /../examples/memory-flow.*

The :ref:`views-flow` above shows the mean of allocated amounts per each allocation site (i.e.
``uid``) in stacked mode. The stacking of the means clearly shows, where the biggest allocations
where made during the program run.

.. image:: /../examples/complexity-flow.*

The :ref:`views-flow` above shows the trend of the average running time of the ``SLList_search``
function depending on the size of the structure we execute the search on.

.. _views-scatter:

Scatter Plot
~~~~~~~~~~~~

.. automodule:: perun.view.scatter

Overview and Command Line Interface
"""""""""""""""""""""""""""""""""""

.. click:: perun.view.scatter.run:scatter
   :prog: perun show scatter

.. _views-scatter-examples:

Examples of Output
""""""""""""""""""

.. image:: /../examples/complexity-scatter-with-models-full.*

The :ref:`views-scatter` above shows the interpreted models of different complexity example,
computed using the **full computation** method. In the picture, one can see that the depedency of
running time based on the structural size is best fitted by `linear` models.

.. image:: /../examples/complexity-scatter-with-models-initial-guess.*

The next `scatter plot` displays the same data as previous, but regressed using the `initial guess`
strategy. This strategy first does a computation of all models on small sample of data points. Such
computation yields initial estimate of fitness of models (the initial sample is selected by
random). The best fitted model is then chosen and fully computed on the rest of the data points.

The picture shows only one model, namely `linear` which was fully computed to best fit the given
data points. The rest of the models had worse estimation and hence was not computed at all.

.. _views-tableof:

Table Of
~~~~~~~~

.. automodule:: perun.view.tableof

Overview and Command Line Interface
"""""""""""""""""""""""""""""""""""
.. click:: perun.view.tableof.run:tableof
   :prog: perun show tableof

.. click:: perun.view.tableof.run:resources
   :prog: perun show tableof resources

.. click:: perun.view.tableof.run:models
   :prog: perun show tableof models

.. _views-tableof-examples:

Examples of Output
""""""""""""""""""

In the following, we show several outputs of the :ref:`views-tableof`.

.. literalinclude:: /../examples/tableof_models_sll
    :linenos:

The table above shows list of models for `SLList_insert` and `SLList_search` functions for
Singly-linked List implementation of test complexity repository sorted by the value of coefficient
of determination `r_square` (see :ref:`postprocessors-regression-analysis` for more details about
models and coefficient of determination). For each type of model (e.g. linear) we list the value of
its coefficients (e.g. for linear function `b1` corresponds to the slope of the function
and `b0` to interception of the function).

From the measured data the insert is estimated to be constant and search to be linear.

.. literalinclude:: /../examples/tableof_resources_ccsds
    :linenos:

The second table shows list of function with quadratic complexities inferred by
:ref:`collectors-bounds` for `dwtint.c` module of the CCSDS codec (will be publically available in
near future). The rest of the function either could not be inferred (e.g. due to unsupported
construction, or requiring more elaborate static resource bounds analysis---e.g. due to the missing
heap analysis) or were linear or constant.

.. literalinclude:: /../examples/tableof_models_latex_vim
    :linenos:

The last example, shows list of estimated linear functions for `vim` *v7.4.2293* sorted by
coefficient of determination `r_square`. The output uses different format (`latex`).

.. _views-custom:

Creating your own Visualization
-------------------------------

.. currentmodule:: perun.utils.common.cli_kit

New interpretation modules can be registered within Perun in several steps. The visualization
methods has the least requirements and only needs to work over the profiles w.r.t.
:ref:`profile-spec` and implement method for Click_ api in order to be used from command line.

You can register your new visualization as follows:

    1. Run ``perun utils create view myview`` to generate a new modules in
       ``perun/view`` directory with the following structure. The command takes a predefined
       templates for new visualization techniques and creates ``__init__.py`` and ``run.py``
       according to the supplied command line arguments (see :ref:`cli-utils-ref` for more
       information about interface of ``perun utils create`` command)::

        /perun
        |-- /view
            |-- /myview
                |-- __init__.py
                |-- run.py
            |-- /bars
            |-- /flamegraph
            |-- /flow
            |-- /scatter

    2. First, implement the ``__init__.py`` file, including the module docstring with brief
       description of the visualization technique and definition of constants which has the
       following structure:

    .. literalinclude:: /_static/templates/views_init.py
        :language: python
        :linenos:

    3. Next, in the ``run.py`` implement module with the command line interface function, named the
       same as your visualization technique. This function is called from the command line as
       ``perun show ``perun show myview`` and is based on Click_ library.

    4. Finally register your newly created module in ``get_supported_module_names`` located in
       ``perun.utils.common.cli_kit.py``:

    .. literalinclude:: _static/templates/supported_module_names_views.py
        :language: python
        :linenos:
        :diff: _static/templates/supported_module_names.py

    5. Preferably, verify that registering did not break anything in the Perun and if you are not
       using the developer installation, then reinstall Perun::

        make test
        make install

    6. At this point you can start using your visualization either using ``perun show``.

    7. If you think your collector could help others, please, consider making `Pull Request`_.

.. _Pull Request: https://github.com/Perfexionists/perun/pull/new/develop
.. _Click: https://click.palletsprojects.com/en/latest/
