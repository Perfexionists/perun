.. _postprocessors-overview:

Postprocessors Overview
=======================

.. automodule:: perun.postprocess

.. _postprocessors-list:

Supported Postprocessors
------------------------

Perun's tool suite currently contains the following two postprocessors:

  1. :ref:`postprocessors-normalizer` scales the resources of the given profile to the
     interval (0, 1). The main intuition behind the usage of this postprocessor is to be able to
     compare profiles from different workloads or parameters, which may have different scales of
     resource amounts.

  2. :ref:`postprocessors-regression-analysis` (authored by **Jirka Pavela**) attempts to do a
     regression analysis by finding the fitting model for dependent variable based on other
     independent one. Currently the postprocessor focuses on finding a well
     suited model (linear, quadratic, logarithmic, etc.) for the amount of time duration
     depending on size of the data structure the function operates on.

All of the listed postprocessors can be run from command line. For more information about command
line interface for individual postprocessors refer to :ref:`cli-postprocess-units-ref`.

Postprocessors modules are implementation independent and only requires a simple python interface
registered within Perun. For brief tutorial how to create and register your own postprocessors
refer to :ref:`postprocessors-custom`.

.. _postprocessors-normalizer:

Normalizer Postprocessor
~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: perun.postprocess.normalizer

Command Line Interface
""""""""""""""""""""""

.. click:: perun.postprocess.normalizer.run:normalizer
   :prog: perun postprocessby normalizer

.. _postprocessors-regression-analysis:

Regression Analysis
~~~~~~~~~~~~~~~~~~~

.. automodule:: perun.postprocess.regression_analysis

.. _postprocessors-regression-analysis-cli:

.. _postprocessors-regression-analysis-examples:

Command Line Interface
""""""""""""""""""""""

.. click:: perun.postprocess.regression_analysis.run:regression_analysis
   :prog: perun postprocessby regression_analysis

.. _postprocessors-custom:

Examples
""""""""

.. literalinclude:: /../examples/complexity-sll-short-with-ra.perf
    :language: json
    :linenos:
    :emphasize-lines: 44-153

The profile above shows the complexity profile taken from :ref:`collectors-complexity-examples` and
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
            |-- /normalizer
            |-- /regression_analysis
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

    5. Finally register your newly created module in :func:`get_supported_module_names` located in
       ``perun.utils.__init__.py``:

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

.. _Pull Request: https://github.com/tfiedor/perun/pull/new/develop
.. _Click: http://click.pocoo.org/5/
