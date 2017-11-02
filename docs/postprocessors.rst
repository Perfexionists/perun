.. _postprocessors-overview:

Postprocessors Overview
=======================

.. todo::
   Missing info: Ways how postprocessors are run (by command and by matrix

.. automodule:: perun.postprocess

.. todo::
   Add picture of architecture with highlighted modules

.. todo::
   Discuss how the profiles are generated

.. _postprocessors-list:

Supported Postprocessors
------------------------

Perun currently supports three postprocessors:

  1. :ref:`postprocessors-normalizer`, which scales the resources of the given profile to the
     interval (0, 1). The main intuition behind the usage of this postprocessor is to be able to
     compare profiles from different workloads or parameters, which may have different scales of
     resource amounts.

  2. :ref:`postprocessors-filter`, which filters the values according to the chosen rules. This is
     used to further reduce the profile by omitting resources which are not useful at all.

  3. :ref:`postprocessors-regression-analysis` (authored by **Jirka Pavela**), which attempts to
     do a regression analysis of the given data. Currently the postprocessor focuses on finding
     a well suited model (linear, quadratic, logarithmic, etc.) for the amount of time duration
     depending on size of the data structure the function operates on.

Moreover, you can easily create and register your own postprocessors as described in
:ref:`postprocessors-custom`. Postprocessors modules are implementation independent and only
requires a simple python interface registered within Perun.

.. _postprocessors-filter:

Filter Postprocessor
~~~~~~~~~~~~~~~~~~~~

.. automodule:: perun.postprocess.filter

.. automodule:: perun.postprocess.filter.run

Command Line Interface
""""""""""""""""""""""

.. click:: perun.postprocess.filter.run:filter
   :prog: perun postprocessby filter

.. _postprocessors-normalizer:

Normalizer Postprocessor
~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: perun.postprocess.normalizer

.. automodule:: perun.postprocess.normalizer.run

Command Line Interface
""""""""""""""""""""""

.. click:: perun.postprocess.normalizer.run:normalizer
   :prog: perun postprocessby normalizer

.. _postprocessors-regression-analysis:

Regression Analysis
~~~~~~~~~~~~~~~~~~~

.. automodule:: perun.postprocess.regression_analysis

.. automodule:: perun.postprocess.regression_analysis.run

Command Line Interface
""""""""""""""""""""""

.. click:: perun.postprocess.regression_analysis.run:regression_analysis
   :prog: perun postprocessby regression_analysis

.. _postprocessors-custom:

Creating your own Postprocessor
-------------------------------

.. todo::
   Include from "template" stored somewhere in the perun directory

.. todo::
   Add reference to click

.. todo::
   Write about the requirements for the __init__.py

New postprocessors can be easily registered within Perun in several steps. Internally they can
be implemented in any programming language and in order to work with perun requires one to three
phases to be specified as given in :ref:`postprocessors-overview`---``before()``, ``postprocess()``
and ``after()``. Each new postprocessor also requires a interface module ``run.py``, which
contains the three function and, moreover, a CLI function for Click framework.

You can register your new postprocessor as follows:

    1. Create a new module in ``perun/postprocess`` with the following structure::

        /perun
        |-- /postprocess
            |-- /new_module
                |-- __init__.py
                |-- run.py
            |-- /regression_analysis
            ...

    2. Implement the ``run.py`` module with ``postprocess()`` fucntion, (and optionally with
       ``before()`` and ``after()`` functions).

    3. Implement command line interface function in ``run.py``. This function will be called when
       Perun is run from the command line as ``perun postprocessby ... new_module``

    4. Verify that registering did not break anything in the Perun and optionally reinstall Perun::

         make test
         make install
