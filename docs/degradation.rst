.. _degradation-overview:

Detecting Performance Degradation
=================================

For every new minor version of project, we usually generate new batch of profiles with concrete
configuration (i.e. set collectors, postprocessors, etc.), which are assigned to the minor version
to preserve the history of the project. However, each change of project, and each minor version,
can cause a degradation of the project.

Perun allows one to automatically check the degradation between various versions of history and
guards against potential degradation introduced in new versions of project. One can employ several
strategies for different configurations of profiles, each suitable for different types of
degradation. Potential changes of performance are then reported, together with more precise
information, about their location, the rate of degradation or the confidence of the detected
degradation, so one can evaluate whether the detected changes are real or spurious.

The detection of degradation is always between two profiles with the same configuration (i.e
collected by same collectors, postprocessed using same postprocessors, and collected for the same
command, arguments and workload). These profiles always correspond to a minor version (so called
target) and its parents (so called baseline). Baseline profiles do not have to be necessarily the
direct predecessor of the minor version, but can be found deeper in the hierarchy (i.e. the root of
the project or minor version from two days ago). During the check of degradation of one profile
corresponding to the target, we find the nearest baseline profile in the history. One pair of
target and baseline profile can then be checked by multiple methods and can report multiple
degradations.

.. image:: /../figs/diff-analysis.*
    :align: center
    :width: 100%

.. _degradation-output:

Results of Detection
--------------------

Between the pair of target and baseline profile one can use multiple methods. Each method can then
yield multiple reports about found degradation. Each degradation reports the following:

  1. **Type of the change**---can be one of the following:

     ``No Change``:

       Represents that the performance of the given uniquely identified resource groups was not
       changed in any way and it stayed the same. By default these changes are not reported in
       standard output, but can be shown by increasing the verbosity of the command line interface
       (see :doc:`cli` how to increase the verbosity of the output).

     ``Degradation``/``Optimization``:

       Represents that the performance of resource group has degradated (resp optimized), i.e. has
       worsen (resp got better). Each report usually shows also the confidence of the detection,
       e.g. by high value of coefficient of determination (see
       :ref:`postprocessors-regression-analysis`).

     ``Maybe Degradation``/``Maybe Optimization``:

       Represents detected change which is unverified or has a low confidence (so the change can be
       either false positive or false negative).

     ``Unknown``:

      Represents that the given method could not determine anything at all.

  2. **Subtype of the change**---which describes the type of the change in more details, such as
     that the change was in `complexity order` or `ratio`.

  3. **Confidence**---depends on the underlying detection methods and represents how likely the
     degradation is real and not spurious or caused by badly collected data. For methods based on
     :ref:`postprocessors-regression-analysis` this corresponds to the coefficient of determination
     which shows the fitness of the function models to the actually measured values.

  4. **Location**---in minimal this corresponds to the unique identifier of the group of
      resources, such as the name of the function or the precise chunk of the code.

By default, if the method does not detect any change between two profiles, it is not reported at
all. This behaviour can be changed by increasing the verbosity of the output (see :doc:`cli` how to
increase the verbosity of the output)

.. _degradation-methods:

Detection Methods
-----------------

Currently we support just two simple strategies for detection of the performance changes:

  1. :ref:`degradation-method-bmoe` which is based on results of
     :ref:`postprocessors-regression-analysis`` and only checks for each uniquely identified group
     of resources, whether the best model changed (in lexicographic ordering of model types), such
     as that the best model changed from `linear` to `quadratic`.

  2. :ref:`degradation-method-aat` which computes for each uniquely identified group of resources
     averages as a representation of the performance. Each average is then compared with the
     baseline average and if it exceeds a certain threshold it detects the change.

.. _degradation-method-bmoe:

Best Model Order Equality
~~~~~~~~~~~~~~~~~~~~~~~~~

  - **Limitations**: Profiles postprocessed by :ref:`postprocessors-regression-analysis`

The `Best Model Order Equality` takes the best model (the one with highest `coefficient of
determination`) as the representant of the performance of one group of uniquely identified
resources. Then each pair of baseline and target models is compared lexicographically, and any
change is detected as either ``Optimization`` or ``Degradation``.

The example of output generated by `Best Model Order Equality` method is as follows ::

    * 1eb3d6: Fix the degradation of search
    |\
    | * 7813e3: Implement new version of search
    |   > collected by complexity+regression_analysis for cmd: '$ mybin'
    |     > applying 'best_model_order_equality' method
    |       - Optimization         at SLList_search(SLList*, int)
    |           from: power -> to: linear (with confidence r_square = 0.99)
    |
    * 7813e3: Implement new version of search
    |\
    | * 503885: Fix minor issues
    |   > collected by complexity+regression_analysis for cmd: '$ mybin'
    |     > applying 'best_model_order_equality' method
    |       - Degradation          at SLList_search(SLList*, int)
    |           from: linear -> to: power (with confidence r_square = 0.99)
    |
    * 503885: Fix minor issues

In the output above, we detected the ``Optimization`` between commits ``1eb3d6`` and ``7813e3``,
where the best model of running time of ``SLList_search`` function changed from `power` model to
`linear` one. For the methods based on :ref:`postprocessors-regression-analysis` we can use the
`coefficient of determination` (:math:`r^2`) to represent a confidence, and take the minimal
`coefficient of determination` of target and baseline model as confidence for this detected change.

.. _degradation-method-aat:

Average Amount Threshold
~~~~~~~~~~~~~~~~~~~~~~~~

  - **Limitations**: `None`

The `Average Amount Threshold` checker groups all of the resources according to the unique
identifier (uid) and then computes the averages as representants of baseline and target profiles.
The computed averages are then compared, and according to the set threshold the checker detectes
either ``Optimization`` or ``Degradation`` (the threshold ration is ``2.0`` for degradation and
``0.5`` for optimization, i.e. the threshold is two times speed-up or speed-down)

The example of output generated by `Average Amount Threshold` method is as follows ::

    * 1eb3d6: Fix the degradation of search
    |\
    | * 7813e3: Implement new version of search
    |   > collected by complexity+regression_analysis for cmd: '$ mybin'
    |     > applying 'average_amount_threshold' method
    |       - Optimization         at SLList_search(SLList*, int)
    |           from: 60677.98ms -> to: 135.29ms
    |
    * 7813e3: Implement new version of search
    |\
    | * 503885: Fix minor issues
    |   > collected by complexity+regression_analysis for cmd: '$ mybin'
    |     > applying 'average_amount_threshold' method
    |       - Degradation          at SLList_search(SLList*, int)
    |           from: 156.48ms -> to: 60677.98ms
    |
    * 503885: Fix minor issues

In the output above, we detected the ``Optimization`` between commits ``1eb3d6`` and ``7813e3``,
where the average amount of running time for ``SLList_search`` function changed from about six
seconds to hundred miliseconds. For this detector we report no confidence at all.

.. _degradation-config:

Configuring Degradation Detection
---------------------------------

Method that are used for given profiles are based on their configuration and rules defined in
:ckey:`degradation.strategies` key in configuration. By `configuration` we consider the tuple of
`(command, arguments, workload, collector, postprocessors)` which represent how the data were
collected for the given minor version. The strategies are specified as an ordered list, and are
collected through all of the configurations (starting from the runtime configuration, through local
ones, up to the global configuration). Then for each profile, we iterate through the list and find
either the first that is applicable according to the set rules (by setting :ckey:`degradation.apply` to ``first``) or all applicable ones (by setting :ckey:`degradation.apply` to ``all``).


The example of strategies is as follows:

  .. code-block:: yaml

      degradation:
        strategies:
          - type: mixed
            postprocessor: regression_analysis
            method: bmoe
         -  cmd: mybin
            type: memory
            method: bmoe
          - method: aat

The following list will apply the :ref:`degradation-method-bmoe` method to either mixed profiles
postprocessed by :ref:`postprocessors-regression-analysis` or to memory profiles collected from
command ``mybin``. The methods can either be specified by their full name or using the short
strings by taking the first letters of each word of the name of the method.

.. _degradation-cli:

Degradation CLI
---------------

:doc:`cli` contains group of two commands for checking the degradation in the current
project---``perun check head`` (for running the degradation check for one minor version of the
project) and ``perun check all`` for iteratively applying the degradation check for all minor
versions of the project. The first command is mostly meant to run as a hook after each new commit
(after running ``perun run matrix`` generating the new batch of profiles), while the latter is
meant to be used for new projects, after crawling through the whole history of the project.

.. click:: perun.cli:check_head
   :prog: perun check head

.. click:: perun.cli:check_all
   :prog: perun check all
