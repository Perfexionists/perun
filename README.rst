===============================================
  Perun: Lightweight Performance Version System
===============================================

.. _Bokeh: https://bokeh.pydata.org/en/latest/
.. _Click: http://click.pocoo.org/5/
.. _JSON: https://www.json.org/
.. _Yaml: http://yaml.org/

.. image:: https://travis-ci.org/tfiedor/perun.svg?branch=develop
    :target: https://travis-ci.org/tfiedor/perun
.. image:: https://codecov.io/gh/tfiedor/perun/branch/develop/graph/badge.svg
    :target: https://codecov.io/gh/tfiedor/perun
.. image:: https://codeclimate.com/github/tfiedor/perun/badges/gpa.svg
    :target: https://codeclimate.com/github/tfiedor/perun
    :alt: Code Climate

.. image:: figs/perun-logo.png
    :width: 300px
    :scale: 20%
    :align: center

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

.. image:: /figs/perun-flow.svg
   :align: center
   :width: 100%

    Perun is meant to be used in two ways: (1) for a single developer (or a small team) as a complete
    solution for automating, storing and interpreting performance of ones project or (2) as a dedicated
    store for a bigger projects and teams. Its git-like design aims at easy distribution and simple
    interface makes it a simple store of profiles along with the context.

    Currently we are considering making a storage layer abstracting the storing of the profile either
    in filesystem (in git) or in database. This is currently in discussion in case the filesystem
    storage will not scale enough.

Getting started
===============

You can install Perun as follows::

    make init
    make install

These commands installs Perun to your system as a python package. You can then run perun safely
from the command line using the ``perun`` command. Run either ``perun --help`` or see the
:doc:`cli` documentation for more information about running Perun commands from command line.

.. note::
Depending on your OS and the location of Python libraries, you might require root permissions
   to install Perun.

In order to partially verify that Perun runs correctly in your environment, run the automated tests
as follows::

    make test

Developing
==========

Alternatively you can install Perun in development mode::

    make init
    make dev

This method of installation allows you to make a changes to the code, which will be then reflected
by the installation.

In order to partially verify that Perun runs correctly in your environment, run the automated tests
as follows::

    make test

Features
========

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
    both by Windows and Unix-like platforms. However, several visualizations currently requires
    support for ``ncurses`` library (e.g. :ref:`views-heapmap`).

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

Contributing
============

.. _upstream: https://github.com/tfiedor/perun
.. _send us PR: https://github.com/tfiedor/perun/pull/new/develop

If you'd like to contribute, please fork the repository and use a feature
branch. Pull requests are warmly welcome.

In case you run in some unexpected behaviour, error or anything suspicious, either contact us
directly through mail or `create a new Issue`_.

In order to extend the tool suite with custom modules (collectors, postprocessors and
visualizations) one needs to implement ``run.py`` module inside the custom package stored in
appropriate subdirectory (``perun.collect``, ``perun.postprocess`` and ``perun.view``
respectively). For more information about registering new profiling data collector, profile
postprocessor, or new visual interpretation of results refer to :ref:`collectors-custom`,
:ref:`postprocessors-custom` and :ref:`views-custom` respectively.

If you think your custom module could help others, please `send us PR`_, we will review the code
and in case it is suitable for wider audience, we will include it in our upstream_.
.. _create a new Issue: https://github.com/tfiedor/perun/issues/new

Links
=====

TODO
    - Project homepage: https://your.github.com/awesome-project/
    - Repository: https://github.com/your/awesome-project/
    - Issue tracker: https://github.com/your/awesome-project/issues
      - In case of sensitive bugs like security vulnerabilities, please contact
        my@email.com directly instead of using issue tracker. We value your effort
        to improve the security and privacy of this project!
    - Related projects:
      - Your other project: https://github.com/your/other-project/
      - Someone else's project: https://github.com/someones/awesome-project/

Licensing
=========

The code in this project is licensed under GNU GPLv3 license.

Acknowledgements
================

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
