.. _degradation-overview:

Detecting Performance Changes
=============================

For every new minor version of project (or every project release), developers should usually
generate new batch of performance profiles with the same concrete configuration of resource
collection (i.e. the set of collectors and postprocessors run on the same commands).These profiles
are then assigned to the minor version to preserve the history of the project performance. However,
every change of the project, and every new minor version, can cause a performance degradation of
the project. And manual evaluation whether the degradation has happened is hard.

Perun allows one to automatically check the performance degradation between various minor versions
within the history and protect the project against potential degradation introduced by new minor
versions. One can employ multiple strategies for different configurations of profiles, each
suitable for concrete types of degradation or performance bugs. Potential changes of performance
are then reported for pairs of profiles, together with more precise information, such as the
location, the rate or the confidence of the detected change. These information then help developer
to evaluate whether the detected changes are real or spurious. The spurious warnings can naturally
happen, since the collection of data is based on dynamic analysis and real runs of the program; and
both of them can be influenced heavily by environment or other various aspects, such as higher
processor utilization.

The detection of performance change is always checked between two profiles with the same
configuration (i.e collected by same collectors, postprocessed using same postprocessors, and
collected for the same combination of command, arguments and workload). These profiles correspond
to some minor version (so called target) and its parents (so called baseline). But baseline
profiles do not have to be necessarily the direct predecessor (i.e. the old head) of the target
minor version, and can be found deeper in the version hierarchy (e.g. the root of the project or
minor version from two days ago, etc.). During the check of degradation of one profile
corresponding to the target, we find the nearest baseline profile in the history. Then for one pair
of target and baseline profiles we can use multiple methods and these methods can then report
multiple performance changes (such as optimizations and degradations).

.. image:: /../figs/diff-analysis.*
    :align: center
    :width: 100%

.. _degradation-output:

Results of Detection
--------------------

Between the pair of target and baseline profile one can use multiple methods, each suitable for
specific type of change. Each such method can then yield multiple reports about detected
performance changes (however, some of these can be spurious). Each degradation report can contain
the following details:

  1. **Type of the change**---the overall general classification of the performance change, which
     can be one of the following six values representing both certain and uncertain answers:

     ``No Change``:

       Represents that the performance of the given uniquely identified resource group was not
       changed in any way and it stayed the same (within some bound of error). By default these
       changes are not reported in the standard output, but can be made visible by increasing the
       verbosity of the command line interface (see :doc:`cli` how to increase the verbosity of the
       output).

     ``Total Degradation`` or ``Total Optimization``:

       Represents an overall program degradation or optimization. The overall degradation or
       optimization report may actually be further divided into per-binary or per-file reports
       (e.g., a standalone report for ``mybin`` and its library ``mylib`` as done by
       :ref:`degradation-method-eto`).

     ``Not in Baseline`` or ``Not in Target``:

       Represents a performance change caused by new or deleted resources, e.g., functions that
       are newly introduced (resp newly missing) in the new project version. Reporting these
       changes is useful since even a simple function refactoring may introduce serious performance
       slowdown or speedup.

     ``Severe Degradation`` or ``Severe Optimization``:

       Represents that the performance of resource group has severely degraded (resp optimized),
       i.e., got severely worse (resp better) with a high confidence. Each report also usually
       shows the confidence of this report, e.g. by the value of coefficient of determination (see
       :ref:`postprocessors-regression-analysis`), which quantifies how the prediction or
       regression models of both versions were fitting the data.

     ``Degradation`` or ``Optimization``:

       Represents that the performance of resource group has degraded (resp optimized), i.e. got
       worse (resp got better) with a fairly high confidence. Each report also usually shows the
       confidence of this report, e.g. by the value of coefficient of determination (see
       :ref:`postprocessors-regression-analysis`), which quantifies how the prediction or
       regression models of both versions were fitting the data.


     ``Maybe Degradation`` or ``Maybe Optimization``:

       Represents detected performance change which is either unverified or with a low confidence
       (so the change can be either false positive or false negative). This classification of
       changes allows methods to provide more broader evaluation of performance change.

     ``Unknown``:

      Represents that the given method could not determine anything at all.

  2. **Subtype of the change**---the description of the type of the change in more details, such as
     that the change was in `complexity order` (e.g. the performance model degraded from linear
     model to power model) or `ratio` (e.g. the average speed degraded two times)

  3. **Confidence**---an indication how likely the degradation is real and not spurious or caused
     by badly collected data. The actual form of confidence is dependent on the underlying
     detection method. E.g. for methods based on :ref:`postprocessors-regression-analysis` this
     can correspond to the coefficient of determination which shows the fitness of the function
     models to the actually measured values.

  4. **Location**---the unique identification of the group of resources, such as the name of the
     function, the precise chunk of the code or line in code.

If the underlying method does not detect any change between two profiles, by default nothing is
reported at all. However, this behaviour can be changed by increasing the verbosity of the output
(see :doc:`cli` how to increase the verbosity of the output)

.. _degradation-methods:

Detection Methods
-----------------

Currently we support three simple strategies for detection of the performance changes:

  1. :ref:`degradation-method-bmoe` which is based on results of
     :ref:`postprocessors-regression-analysis` and only checks for each uniquely identified group
     of resources, whether the best performance (or prediction) model has changed (considering
     lexicographic ordering of model types), e.g. that the best model changed from `linear` to
     `quadratic`.

  2. :ref:`degradation-method-aat` which computes averages as a representation of the performance
     for each uniquely identified group of resources. Each average of the target is then compared
     with the average of the baseline and if the their ration exceeds a certain threshold interval,
     the method reports the change.

  3. :ref:`degradation-method-eto` which identifies outliers within the function exclusive time
     deltas. The outliers are identified using three different statistical techniques, resulting in
     three different change severity categories based on which technique discovered the outlier.

Refer to :ref:`degradation-custom` to create your own detection method.

.. _degradation-method-bmoe:

Best Model Order Equality
~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: perun.check.methods.best_model_order_equality

.. _degradation-method-aat:

Average Amount Threshold
~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: perun.check.methods.average_amount_threshold

.. _degradation-method-eto:

Exclusive Time Outliers
~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: perun.check.methods.exclusive_time_outliers

.. _degradation-fast-check:

Fast Check
~~~~~~~~~~

.. automodule:: perun.check.methods.fast_check

.. _degradation-lreg:

Linear Regression
~~~~~~~~~~~~~~~~~

.. automodule:: perun.check.methods.linear_regression

.. _degradation-preg:

Polynomial Regression
~~~~~~~~~~~~~~~~~~~~~

.. automodule:: perun.check.methods.polynomial_regression

.. _degradation-config:

Configuring Degradation Detection
---------------------------------

We apply concrete methods of performance change detection to concrete pairs of profiles according
to the specified `rules` based on profile collection configuration. By `configuration` we mean the
tuple of `(command, arguments, workload, collector, postprocessors)` which represent how the data
were collected for the given minor version. This way for each new version of project, it is
meaningful to collect new data using the same config and then compare the results. The actual rules
are specified in configuration files by :ckey:`degradation.strategies`. The strategies are
specified as an ordered list, and all of the applicable rules are collected through all of the
configurations (starting from the runtime configuration, through local ones, up to the global
configuration). This yields a `list of rules` (each rule represented as key-value dictionary)
ordered by the priority of their application. So for each pair of tested profiles, we iterate
through this ordered list and find either the first that is applicable according to the set rules
(by setting the :ckey:`degradation.apply` key to value ``first``) or all applicable rules (by
setting the :ckey:`degradation.apply` key to value ``all``).

The example of configuration snippet that sets rules and strategies for one project can be as
follows:

  .. code-block:: yaml

      degradation:
        apply: first
        strategies:
          - type: mixed
            postprocessor: regression_analysis
            method: bmoe
          - cmd: mybin
            type: memory
            method: bmoe
          - method: aat

The following list of strategies will first try to apply the :ref:`degradation-method-bmoe` method
to either mixed profiles postprocessed by :ref:`postprocessors-regression-analysis` or to memory
profiles collected from command ``mybin``. All of the other profiles will be checked using
:ref:`degradation-method-aat`. Note that applied methods can either be specified by their full name
or using the short strings by taking the first letters of each word of the name of the method, so
e.g. `BMOE` stands for :ref:`degradation-method-bmoe`.

.. _degradation-custom:

Create Your Own Degradation Checker
-----------------------------------

New performance change checkers can be registered within Perun in several steps. The checkers have
just small requirements and have to `yield` the reports about degradation as a instances of
``DegradationInfo`` objects specified as follows:

.. currentmodule: perun.utils.structs
.. autoclass::  perun.utils.structs.common_structs.DegradationInfo
   :members:

.. autoclass::  perun.utils.structs.common_structs.PerformanceChange
   :members:

You can register your new performance change checker as follows:

    1. Run ``perun utils create check my_degradation_checker`` to generate a new modules in
       ``perun.check.methods`` directory with the following structure. The command takes a predefined
       templates for new degradation checkers and creates ``my_degradation_checker.py`` according
       to the supplied command line arguments (see :ref:`cli-utils-ref` for more information about
       interface of ``perun utils create`` command)::

        /perun
        |-- /check
            |-- __init__.py
            |-- average_amount_threshold.py
            |-- my_degradation_checker.py

    2. Implement the ``my_degradation_checker.py`` file, including the module docstring with brief
       description of the change check with the following structure:

      .. literalinclude:: /_static/templates/degradation_api.py
          :language: python
          :linenos:

    3. Next, in the ``__init__.py`` module register the short string for your new method as
       follows:

      .. literalinclude:: /_static/templates/degradation_init_new_check.py
          :language: python
          :linenos:
          :diff: /_static/templates/degradation_init.py

    4. Preferably, verify that registering did not break anything in the Perun and if you are not
       using developer instalation, then reinstall Perun::

        make test
        make install

    5. At this point you can start using your check using ``perun check head``, ``perun check
       all`` or ``perun check profiles``.

    6. If you think your collector could help others, please, consider making `Pull Request`_.

.. _Pull Request: https://github.com/Perfexionists/perun/pull/new/develop

.. _degradation-cli:

Degradation CLI
---------------

:doc:`cli` contains group of two commands for running the checks in the current project---``perun
check head`` (for running the check for one minor version of the project; e.g. the current `head`)
and ``perun check all`` for iterative application of the degradation check for all minor versions
of the project. The first command is mostly meant to run as a hook after each new commit (obviously
after successfull run o f``perun run matrix`` generating the new batch of profiles), while the
latter is meant to be used for new projects, after crawling through the whole history of the
project and collecting the profiles. Additionally ``perun check profiles`` can be used for an
isolate comparison of two standalone profiles (either registered in index or as a standalone file).

.. click:: perun.cli_groups.check_cli:check_head
   :prog: perun check head

.. click:: perun.cli_groups.check_cli:check_all
   :prog: perun check all

.. click:: perun.cli_groups.check_cli:check_profiles
   :prog: perun check profiles
