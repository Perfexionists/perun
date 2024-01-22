Perun: Performance Under Control
================================

.. image:: /../figs/perun-logo.png
   :align: center

.. _Bokeh: https://bokeh.pydata.org/en/latest/
.. _Click: https://click.palletsprojects.com/en/latest/
.. _JSON: https://www.json.org/
.. _Yaml: http://yaml.org/

What is Perun?
--------------

`Have you ever encountered a sudden performance degradation and could not figure out, when and
where the degradation was introduced?`

`Do you think that you have no idea whether the overall performance of your application is getting
better or not over the time?`

`Is it hard for you to set performance regression testing everytime you create a new project?`

`Do you ever feel that you completely loose the control of the performance of your projects?`

There exists solutions for managing changes of ones project---Version Control Systems (VCS)---but
precise managing of performance is harder. This calls for solutions tuned to support performance
management---Performance Versioning Systems.

Perun is an open source light-weight Performance Version System. While revision (or version)
control systems track how your code base is changing, what features were added and keeps snapshots
of versions of projects, they are mostly generic in order to satisfy needs of broad range of
project types. And actually you can run all of the performance regressions tests manually and then
use, e.g. git, to store the actual profiles for each minor version (e.g.  commits) of your project.
However, you are forced to do all of the profiling, annotations with tags and basic informations
about collected resources, and many more by yourself, otherwise you lose the precise history of the
performance your application. Or you can use database, but lose the flexibility and easy usage of
the versioning systems and you have to design and implement some user interface yourself.

Perun is in summary a wrapper over existing Version Systems and takes care of managing profiles for
different versions of projects. Moreover, it offers a tool suite allowing one to automate the
performance regression test runs, postprocess existing profiles or interpret the results. In
particular, it has the following advantages over databases and sole Version Control Systems:

  1. **Context**---each performance profile is assigned to a concrete minor version adding the
     missing context to your profiles---what was changed in the code base, when it was changed,
     who made the changes, etc. The profiles themselves contains collected data and addition
     information about the performance regression run or application configurations.

  2. **Automation**---Perun allows one to easily automate the process of profile collection,
     eventually reducing the whole process to a single command and can be hence hooked, e.g. when
     one commits new changes, in supported version control system to make sure one never misses
     to generate new profiles for each new minor or major version of project. The specification
     of jobs is inspired by continuous integration systems, and is designed as YAML file, which
     serves as a natural format for specifying the automated jobs.

  3. **Genericity**---supported format of the performance profiles is based on JSON_ notation and
     has just a minor requirements and restrictions. Perun tool suite contains a basic set of
     generic (and several specific) visualizations, postprocessing and collection modules which
     can be used as building blocks for automating jobs and interpreting results. Perun itself
     poses only a minor requirements for creating and registering new modules, e.g. when one
     wants to register new profiling data collectors, data postprocessors, customized
     visualiations or different version control systems.

  4. **Easy to use**---the workflow, interface and storage of Perun is heavily inspired by the git
     systems aiming at natural use (at least for majority of potential users). Current version
     has a Command Line Interface consisting of commands similar to git (such as e.g. add,
     status, log). Interactive Graphical User Interface is currently in development.

.. image:: /../figs/perun-flow.*
   :align: center
   :width: 100%

Perun is meant to be used in two ways: (1) for a single developer (or a small team) as a complete
solution for automating, storing and interpreting performance of ones project or (2) as a dedicated
store for a bigger projects and teams. Its git-like design aims at easy distribution and simple
interface makes it a simple store of profiles along with the context.

Currently we are considering making a storage layer abstracting the storing of the profile either
in filesystem (in git) or in database. This is currently in discussion in case the filesystem
storage will not scale enough.

Installation
------------

You can install Perun as follows::

    make init
    make install

These commands installs Perun to your system as a python package. You can then run perun safely
from the command line using the ``perun`` command. Run either ``perun --help`` or see the
:doc:`cli` documentation for more information about running Perun commands from command line.

.. note::
   Depending on your OS and the location of Python libraries, you might require root permissions
   to install Perun.

Alternatively you can install Perun in development mode::

    make init
    make dev

This method of installation allows you to make a changes to the code, which will be then reflected
by the installation.

In order to partially verify that Perun runs correctly in your environment, run the automated tests
as follows::

    make test

In case you run in some unexpected behaviour, error or anything suspicious, either contact us
directly through mail or `create a new Issue`_.

.. _create a new Issue: https://github.com/Perfexionists/perun/issues/new

Lifetime of a profile
---------------------

Format of performance profiles is based on JSON_ format. It tries to unify various performance
metrics and methods for collecting and postprocessing of profiling data. Profiles themselves are
stored in a storage (parallel to vcs storage; currently in filesystem), compressed using the `zlib`
compression method along with the additional information, such as how the profile was collected,
how profiling resources were postprocessed, which metric units are used, etc. For learning how the
profiles are stored in the storage and the internals of Perun refer to :doc:`internals`. For exact
format of the supported profile refer to :ref:`profile-spec`.

.. image:: /../figs/lifetime-of-profile.*
   :width: 70%
   :align: center

The Figure above shows the lifetime of one profile. Profiles can be generated by set of collectors
(such as :ref:`collectors-trace` which collects time durations depending on sizes of data
structures, or simple :ref:`collectors-time` for basic timing) and can be further refined and
transformed by sequence of postprocessing steps (like e.g.
:ref:`postprocessors-regression-analysis` for estimating regression models of dependent variables
based on independent variables, or :ref:`postprocessors-regressogram`, etc.).

Stored profiles then can be interpreted by set of visualization techniques like e.g.
:ref:`views-flame-graph`, :ref:`views-scatter`, or generic :ref:`views-bars` and :ref:`views-flow`.
Refer to :doc:`views` for more concise list and documentation of interpretation capabilities of
Perun's tool suite.

Perun architecture
------------------

Internal architecture of Perun can be divided into several units---logic (commands, jobs, runners,
store), data (vcs and profile), and the tool suite (collectors, postprocessors and visualizers).
Data includes the core of the Perun---the profile manipulation and supported wrappers (currently
git and simple custom vcs) over the existing version control systems. The logic is in charge of
automation, higher-logic manipulations and takes care of actual generation of the profiles.
Moreover, the whole Perun suite contains set of collectors for generation of profiles, set of
postprocessors for transformation and various visualization techniques and wrappers for graphical
and command line interface.

.. image:: /../figs/perun-architecture-less-trans.*
   :width: 100%
   :align: center

The scheme above shows the basic decomposition of Perun suite into sole units. Architecture of
Perun was designed to allow simple extension of both internals and tool suite. In order to register
new profiling data collector, profile postprocessor, or new visual interpretation of results refer
to :ref:`collectors-custom`, :ref:`postprocessors-custom` and :ref:`views-custom` respectively.

List of Features
----------------

In the following, we list the foremost features and advantages of Perun:

  * **Unified format**---we base our format on JSON_ with several minor limitations, e.g. one needs
    to specify header region or set of resources under fixed keys. This allows us to reuse existing
    postprocessors and visualisers to achieve great flexibility and easily design new methods. For
    full specification of our format refer to :ref:`profile-spec`.

  * **Natural specification of Profiling Runs**---we base the specification of profiling jobs in
    Yaml_ format. In project configuration we let the user choose the set of collectors, set of
    postprocessors and configure runnable applications along with different parameter combinations
    and input workloads. Based on this specification we build a job matrix, which is then
    sequentially run and generates list of performance profiles. After the functional changes to
    project one then just needs to run ``perun run matrix`` to genereate new batch of performance
    profiles for latest (or currently checked-out) minor version of project.

  * **Git-inspired Interface**---the :doc:`cli` is inspired by git version control systems and
    specifies commands like e.g. ``add``, ``remove``, ``status``, or ``log``, well-known to basic
    git users. Moreover, the interface is built using the Click_ library providing flexible option
    and argument handling. The overall interface was designed to have a natural feeling when
    executing the commands.

  * **Efficient storage**---performance profiles are stored compressed in the storage in parallel
    to versions of the profiled project. Each stored object is then identified by its hash
    indentificator allowing quick lookup and reusing of object blobs. Storage in this form is
    rather packed and allows easy distribution.

  * **Multiplatform-support**---Perun is implemented in Python 3 and its implementation is supported
    both by Windows and Unix-like platforms.

  * **Regression Analysis**---Perun's suite contains a postprocessing module for
    :ref:`postprocessors-regression-analysis`, which supports several different strategies for
    finding the best model for given data (such as linear, quadratic, or constant model). Moreover,
    it contains switch for a more fine analysis of the data e.g. by performing regression analysis
    on smaller intervals, or using bisective method on whole data interval. Such analyses allows
    one to effectively interpret trends in data (e.g. that the duration of list search is lineary
    dependent on the size of the list) and help with detecting performance regressions.

  * **Interactive Visualizations**---Perun's tool suite includes several visualization modules,
    some of them based on Bokeh_ visualization library, which provides nice and interactive plots,
    in exchange of scalability (note that we are currently exploring libraries that can scale better)
    ---in browser, resizable and manipulable.

  * **Useful API for profile manipulation**---helper modules are provided for working with our
    profiles in external applications (besides loading and basic usage)---we have API for executing
    simple queries over the resources or other parts of the profiles, or convert and transform the
    profiles to different representations (e.g. pandas data frame, or flame-graph format).
    This way, Perun can be used, e.g. together with ``python`` and ``pandas``, as interactive
    interpret with support of statistical analysis.

  * **Automatic Detection of Performance Degradation**---we are currently exploring effective
    heuristics for automatic detection of performance degradation between two project versions (e.g.
    between two commits). Our methodology is based on statistical methods and outputs of
    :ref:`postprocessors-regression-analysis`. More details about degradation detection can be
    found at :doc:`degradation`

Currently we are working on several extensions of Perun, that could be integrated in near future.
Namely, in we are exploring the following possible features into Perun:

  * **Regular Expression Driven Collector**---one planned collectors should be based on parsing the
    standard text output for a custom specified metrics, specified by regular expressions. We
    believe this could allow generic and quick usage to generate the performance profiles without
    the need of creating new specific collectors.

  * **Fuzzing Collector**---other planned collector should be based on method of fuzz
    testing---i.e. modifying inputs in order to force error or, in our case, a performance change.
    We believe that this collector could generate interesting profiles and lead to a better
    understanding of ones applications.

  * **Clustering Postprocessor**---we are exploring now how to make any profile usable for
    regression analysis. The notion of clustering is based on assumption, that there exists an
    independent variable (but unknown to us) that can be used to model the dependent variable (in
    our case the amount of resources). This postprocessor should try to find the optimal clustering
    of the dependent values in order to be usable by :ref:`postprocessors-regression-analysis`.

  * **Automatic Hooks**---in near future, we want to include the initially planned feature of
    Perun, namely the automatic hooks, that will allow to automate the runs of job matrix,
    automatic detection of degradation and efficient storage. Hooks would then trigger the profile
    collection e.g. `on_commit`, `on_push`, etc.

Overview of Customization
-------------------------

.. _upstream: https://github.com/Perfexionists/perun
.. _send us PR: https://github.com/Perfexionists/perun/pull/new/develop

In order to extend the tool suite with custom modules (collectors, postprocessors and
visualizations) one needs to implement ``run.py`` module inside the custom package stored in
appropriate subdirectory (``perun.collect``, ``perun.postprocess`` and ``perun.view``
respectively). For more information about registering new profiling data collector, profile
postprocessor, or new visual interpretation of results refer to :ref:`collectors-custom`,
:ref:`postprocessors-custom` and :ref:`views-custom` respectively.

If you think your custom module could help others, please `send us PR`_, we will review the code
and in case it is suitable for wider audience, we will include it in our upstream_.

Custom Collector
^^^^^^^^^^^^^^^^

Collectors serves as a unit for generating profiles containing captured resources.
In general the collection process can be broken into three phases:

  1. **Before**---optional phase before the actual collection of profiling data, which is meant to
     prepare the profiled project for the actual collection. This phases corresponds to various
     initializations, custom compilations, etc.

  2. **Collect**---the actual collection of profiling data, which should capture the profiled
     resources and ideally generate the profile w.r.t. :ref:`profile-spec`.

  3. **After**---last and optional phase after resources has been successfully collected (either in
     raw or supported format). This phase includes e.g. corresponds filters or transformation of
     the profile.

Each collector should be registered in ``perun.collect`` package and needs to implement the
proposed interfaced inside the ``run.py`` module. In order to register and use a new collector one
needs to implement the following api in the ``run.py`` module::

  def before(**kwargs):
      """(optional) Phase before execution of collector"""
      return status_code, status_msg, kwargs

  def collect(**kwargs):
      """Collection of the profile---returned profile is in kwargs['profile']"""
      kwargs['profile'] = collector.do_collection()
      return status_code, status_msg, kwargs

  def after(**kwargs):
      """(optional) Final postprocessing of the generated profile"""
      return status_code, status_msg, kwargs

For full explanation how to register and create a new collector module refer to
:ref:`collectors-custom`.

Custom Postprocessor
^^^^^^^^^^^^^^^^^^^^

Postprocessors in general work the same as collectors and can be broken to three phases as well.
The required API to be implemented has a similar requirements and one needs to implement the
following in the ``run.py`` module::

  def before(**kwargs):
      """(optional) Phase before execution of postprocessor"""
      return status_code, status_msg, kwargs

  def postprocess(**kwargs):
      """Postprocessing of the profile---returned profile is in kwargs['profile']"""
      kwargs['profile'] = postprocessor.do_postprocessing()
      return status_code, status_msg, kwargs

  def after(**kwargs):
      """(optional) Final postprocessing of the generated profile"""
      return status_code, status_msg, kwargs

For full explanation how to register and create a new postprocessor module refer to
:ref:`postprocessors-custom`.

Custom Visualization
^^^^^^^^^^^^^^^^^^^^

New visualizations have to be based on the :ref:`profile-spec` (or its supported conversions, see
:ref:`profile-conversion-api`) and has to just implement the following in the ``run.py`` module::

  import click
  import perun.utils.helpers as helpers

  @click.command()
  @helpers.pass_profile
  def visualization_name(profile, **kwargs):
      """Display the profile in custom format"""
      pass

The Click_ library is used for command line interface. For full explanation how to register and
create a new collector module refer to :ref:`views-custom`.

Acknowledgements
----------------

.. _Red Hat: https://www.redhat.com/en/global/czech-republic
.. _Aquas: https://aquas-project.eu/
.. _BUT FIT: https://www.fit.vutbr.cz/

We thank for the support received from `Red Hat`_ (especially branch of Brno), Brno University of
Technology (`BUT FIT`_) and H2020 ECSEL project Aquas_.

Further we would like to thank the following individuals (in the alphabetic order) for their
(sometimes even just a little) contributions:

  * **Jan Fiedor** (Honeywell)---for feedback, and technical discussions;
  * **Martin Hruska** (BUT FIT)---for feedback, and technical discussions;
  * **Petr Müller** (SAP)---for nice discussion about the project;
  * **Michal Kotoun** (BUT FIT)---for feedback, and having faith in this repo;
  * **Hanka Pluhackova** (BUT FIT)---for awesome logo, theoretical discussions about statistics, feedback, and lots of ideas;
  * **Adam Rogalewicz** (BUT FIT)---for support, theoretical discussions, feedback;
  * **Tomas Vojnar** (BUT FIT)---for support, theoretical discussions, feedback;
  * **Jan Zeleny** (Red Hat)---for awesome support, and feedback.

