.. _postprocessors-overview:

Postprocessors Overview
=======================

.. automodule:: perun.postprocess

.. _postprocessors-list:

Supported Postprocessors
------------------------

Perun's tool suite currently contains the following five postprocessors:

  1. :ref:`postprocessors-regression-analysis` (authored by **Jirka Pavela**) attempts to do a
     regression analysis by finding the fitting model for dependent variable based on other
     independent one. Currently the postprocessor focuses on finding a well
     suited model (linear, quadratic, logarithmic, etc.) for the amount of time duration
     depending on size of the data structure the function operates on.

  2. :ref:`postprocessors-regressogram` (authored by **Simon Stupinsky**) also known as the binning
     approach, is the simplest non-parametric estimator. This method trying to fit models through
     data by dividing the interval into N equal-width bucket and the resultant value in each bucket
     is equal to result of selected statistical aggregation function (mean/median) within the values
     in the relevant bucket. In short, we can describe the regressogram as a step function
     (i.e. constant function by parts).

  3. :ref:`postprocessors-moving-average` (authored by **Simon Stupinsky**) also know as the rolling
     average or running average, is the statistical analysis belongs to non-parametric approaches.
     This method is based on the analysis of the given data points by creating a series of values based
     on the specific aggregation function, most often average or possibly median. The resulting values
     are derived from the different subsets of the full data set. We currently support the two main
     methods of this approach and that the **Simple** Moving Average and the **Exponential** Moving
     Average. In the first method is an available selection from two aggregation function: **mean**
     or **median**.

  4. :ref:`postprocessors-kernel-regression` (authored by **Simon Stupinsky**) is a non-parametric
     approach to estimate the conditional expectation of a random variable. Generally, the main goal
     of this approach is to find non-parametric relation between a pair of random variables X <per-key>
     and Y <of-key>. Different from parametric techniques (e.g. linear regression), kernel
     regression does not assume any underlying distribution (e.g. linear, exponential, etc.)
     to estimate the regression function. The main idea of kernel regression is putting the
     **kernel**, that have the role of weighted function, to each observation point in the dataset.
     Subsequently, the kernel will assign weight to each point in depends on the distance from the
     current data point. The kernel basis formula depends only on the *bandwidth* from the current
     ('local') data point X to a set of neighboring data points X.

All of the listed postprocessors can be run from command line. For more information about command
line interface for individual postprocessors refer to :ref:`cli-postprocess-units-ref`.

Postprocessors modules are implementation independent and only requires a simple python interface
registered within Perun. For brief tutorial how to create and register your own postprocessors
refer to :ref:`postprocessors-custom`.


.. _postprocessors-regression-analysis:

Regression Analysis
~~~~~~~~~~~~~~~~~~~

.. automodule:: perun.postprocess.regression_analysis

.. _postprocessors-regression-analysis-cli:

Command Line Interface
""""""""""""""""""""""

.. click:: perun.postprocess.regression_analysis.run:regression_analysis
   :prog: perun postprocessby regression_analysis

.. _postprocessors-regression-analysis-examples:

Examples
""""""""

.. literalinclude:: /../examples/complexity-sll-short-with-ra.perf
    :language: json
    :linenos:
    :emphasize-lines: 44-153

The profile above shows the complexity profile taken from :ref:`collectors-trace-examples` and
postprocessed using the full method. The highlighted part shows all of the fully computed models of
form :math:`y = b_0 + b_1*f(x)`, represented by their types (e.g. `linear`, `quadratic`, etc.),
concrete found coeficients :math:`b_0` and :math:`b_1` and e.g. coeficient of determination
:math:`R^2` for measuring the fitting of the model.

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

.. _postprocessors-regressogram:

Regressogram method
~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: perun.postprocess.regressogram

.. _postprocessors-regressogram-cli:

Command Line Interface
""""""""""""""""""""""

.. click:: perun.postprocess.regressogram.run:regressogram
   :prog: perun postprocessby regressogram

.. _postprocessors-regressogram-examples:

Examples
""""""""

    .. code-block:: json

        {
            "bucket_stats": [
                13.0,
                25.5
            ],
            "uid": "linear::test2",
            "bucket_method": "doane",
            "method": "regressogram",
            "r_square": 0.7575757575757576,
            "x_end": 9.0,
            "statistic_function": "mean",
            "x_start": 0.0
        }

.. _Doanes: https://docs.scipy.org/doc/numpy/reference/generated/numpy.histogram_bin_edges.html#numpy.histogram_bucket_edges

The example above shows an example of profile post-processed by regressogram method (note that
this is only an excerpt of the whole profile). Each such model of shows the computed values in
the individual buckets, that are represented by *bucket_stats*. The next value in this example
is *statistic_function*, which represented the statistic to compute the value in each bucket. Further
contains the name of the method (*bucket_method*) by which was calculated the optimal number of
buckets, in this case specifically computed with Doanes_ formula, and *coefficient of determination*
(:math:`R^2`) for measuring the fitting of the model. Each such model can be used in the further
interpretation of the models (either by :ref:`views-scatter` or :ref:`degradation-method-aat`).

.. image:: /../examples/exp_data_regressogram.*

The :ref:`views-scatter` above shows the interpreted model, computed using the **regressogram**
method. In the picture, one can see that the dependency of running time based on the structural
size is best fitted by `exponential` models.


.. _postprocessors-moving-average:

Moving Average Methods
~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: perun.postprocess.moving_average

.. _postprocessors-moving-average-cli:

Command Line Interface
""""""""""""""""""""""

.. click:: perun.postprocess.moving_average.run:moving_average
   :prog: perun postprocessby moving_average

.. click:: perun.postprocess.moving_average.run:simple_moving_average
   :prog: perun postprocessby moving_average sma

.. click:: perun.postprocess.moving_average.run:simple_moving_median
   :prog: perun postprocessby moving_average smm

.. click:: perun.postprocess.moving_average.run:exponential_moving_average
   :prog: perun postprocessby moving_average ema

.. _postprocessors-moving-average-examples:

Examples
""""""""

    .. code-block:: json

        {
            "bucket_stats": [
              0.0,
              3.0,
              24.0,
              81.0,
              192.0,
              375.0
            ],
            "per_key": "structure-unit-size",
            "uid": "pow::test3",
            "x_end": 5,
            "r_square": 1.0,
            "method": "moving_average",
            "moving_method": "sma",
            "x_start": 0,
            "window_width": 1
        }

The example above shows an example of profile post-processed by moving average postprocessor (note
that this in only an excerpt of the whole profile). Each such model of moving average model shows
the computed values, that are represented by *bucket_stats*. The important role has value *moving_method*,
that represents the method, which was used to create this model. In this field may be one from the
following shortcuts *SMA*, *SMM*, *EMA*, which represents above described methods. The value *r_square*
serves to assess the suitability of the model and represents the *coefficient of determination*
(:math:`R^2`). Another significant value in the context of the information about the moving average
models is the *window_width*. This value represents the width of the window, that was used at creating
this model. Since each model can be used in the further interpretation (either by :ref:`views-scatter`
or :ref:`degradation-method-aat`), another values have auxiliary character and serves for a different
purposes at its interpretation. Additional values that contain the information about postprocess parameters
can be found in the whole profile, specifically in the part about used post-processors.


.. image:: /../examples/exp_data_ema.*

The :ref:`views-scatter` above shows the interpreted model, computed using the **exponential moving average**
method, running with default values of parameters. In the picture, one can see that the dependency of running
time based on the structural size is best fitted by `exponential` models.


.. _postprocessors-kernel-regression:

Kernel Regression Methods
~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: perun.postprocess.kernel_regression

.. _postprocessors-kernel_regression-cli:

Command Line Interface
""""""""""""""""""""""

.. click:: perun.postprocess.kernel_regression.run:kernel_regression
   :prog: perun postprocessby kernel-regression

.. _postprocessors-kernel-regression-estimator_settings:

.. click:: perun.postprocess.kernel_regression.run:estimator_settings
   :prog: perun postprocessby kernel-regression estimator-settings

.. _postprocessors-kernel-regression-user_selection:

.. click:: perun.postprocess.kernel_regression.run:user_selection
   :prog: perun postprocessby kernel-regression user-selection

.. _postprocessors-kernel-regression-method_selection:

.. click:: perun.postprocess.kernel_regression.run:method_selection
   :prog: perun postprocessby kernel-regression method-selection

.. _postprocessors-kernel-regression-kernel_smoothing:

.. click:: perun.postprocess.kernel_regression.run:kernel_smoothing
   :prog: perun postprocessby kernel-regression kernel-smoothing

.. _postprocessors-kernel-regression-kernel_ridge:

.. click:: perun.postprocess.kernel_regression.run:kernel_ridge
   :prog: perun postprocessby kernel-regression kernel-ridge

.. _postprocessors-kernel-regression-examples:

Examples
""""""""

    .. code-block:: json

        {
            "per_key": "structure-unit-size",
            "uid": "quad::test1",
            "kernel_mode": "estimator",
            "r_square": 0.9990518378010778,
            "method": "kernel_regression",
            "x_start": 10,
            "bandwidth": 2.672754640321602,
            "x_end": 64,
            "kernel_stats": [
                  115.6085941489687,
                  155.95838478107163,
                  190.27598428091824,
                  219.36576520977312,
                  252.80699243117965,
                  268.4600214673941,
                  283.3744716372719,
                  282.7535719770607,
                  276.27153279181573,
                  269.69580474542016,
                  244.451017529157,
                  226.98819185034756,
                  180.72465187812492
            ]
        }

The example above shows an example of profile post-processed by *kernel regression* (note that this
is only an excerpt of the whole profile). Each such kernel model shows the values of resulting kernel
estimate, that are part of *kernel_stats* list. Another fascinating value is stored in *kernel_mode*
field and means the relevant mode, which executing the *kernel regression* over this model. In this
field may be one from the following words, which represents the individual modes of kernel regression
postprocessor. The value *r_square* serves to assess the suitability of the kernel model and represents
the *coefficient of determination* (:math:`R^2`). In the context of another kernel estimates for decreasing
or increasing the resulting accuracy is important the field *bandwidth*, which represents the kernel
bandwidth in the current kernel model. Since each model can be used in the further interpretation
(either by :ref:`views-scatter` or :ref:`degradation-method-aat`), another values have auxiliary character
and serves for a different purposes at its interpretation. Additional values that contain the information
about selected parameters at kernel regression postprocessor and its modes, can be found in the whole profile,
specifically in the part about used post-processors.


.. image:: /../examples/example_kernel.*

The :ref:`views-scatter` above shows the interpreted model, computed using the *kernel regression* postprocessor,
concretely with default value of parameters in **estimator-settings** mode of this postprocessor. In the picture, can
be see that the dependency of running time based on the structural size.

.. _postprocessors-custom:

Creating your own Postprocessor
-------------------------------

New postprocessors can be registered within Perun in several steps. Internally they can be
implemented in any programming language and in order to work with perun requires one to three
phases to be specified as given in :ref:`postprocessors-overview`---``before()``, ``postprocess()``
and ``after()``. Each new postprocessor requires a interface module ``run.py``, which contains the
three function and, moreover, a CLI function for Click_ framework.

You can register your new postprocessor as follows:

    1. Run ``perun utils create postprocess mypostprocessor`` to generate a new modules in
       ``perun/postprocess`` directory with the following structure. The command takes a predefined
       templates for new postprocessors and creates ``__init__.py`` and ``run.py`` according to the
       supplied command line arguments (see :ref:`cli-utils-ref` for more information about
       interface of ``perun utils create`` command)::

        /perun
        |-- /postprocess
            |-- /mypostprocessor
                |-- __init__.py
                |-- run.py
            |-- /kernel_regression
            |-- /moving_average
            |-- /regression_analysis
            |-- /regressogram
            |-- __init__.py

    2. First, implement the ``__init__py`` file, including the module docstring with brief
       postprocessor description and definitions of constants that are used for internal
       checks which has the following structure:

    .. literalinclude:: /_static/templates/postprocess_init.py
        :language: python
        :linenos:

    3. Next, implement the ``run.py`` module with ``postprocess()`` fucntion, (and optionally with
       ``before()`` and ``after()`` functions). The ``postprocess()`` function should do the actual
       postprocessing of the profile. Each function should return the integer status of the phase,
       the status message (used in case of error) and dictionary including params passed to
       additional phases and 'profile' with dictionary w.r.t. :ref:`profile-spec`.

    .. literalinclude:: /_static/templates/postprocess_run.py
        :language: python
        :linenos:

    4. Additionally, implement the command line interface function in ``run.py``, named the same as
       your collector. This function will be called from the command line as ``perun postprocessby
       mypostprocessor`` and is based on Click_libary.

    .. literalinclude:: _static/templates/postprocess_run_api.py
        :language: python
        :linenos:
        :diff: _static/templates/postprocess_run.py

    5. Finally register your newly created module in ``get_supported_module_names`` located in
       ``perun.utils.common.cli_kit.py``:

    .. literalinclude:: _static/templates/supported_module_names_postprocess.py
        :language: python
        :linenos:
        :diff: _static/templates/supported_module_names.py

    6. Preferably, verify that registering did not break anything in the Perun and if you are not
       using the developer installation, then reinstall Perun::

        make test
        make install

    7. At this point you can start using your postprocessor either using ``perun postprocessby`` or using the
       following to set the job matrix and run the batch collection of profiles::

        perun config --edit
        perun run matrix

    8. If you think your postprocessor could help others, please, consider making `Pull Request`_.

.. _Pull Request: https://github.com/Perfexionists/perun/pull/new/develop
.. _Click: https://click.palletsprojects.com/en/latest/
