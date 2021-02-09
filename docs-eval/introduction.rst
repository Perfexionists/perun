Perun: Performance Under Control
================================

.. image:: /../figs/perun-logo.png
   :align: center

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

  3. **Genericity**---supported format of the performance profiles is based on JSON notation and
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

