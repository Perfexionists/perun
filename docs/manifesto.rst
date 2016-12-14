===============
Perun Manifesto
===============

.. contents::

Perun Overview
==============

Perun logic is similar to the MVC (Model-View-Controler) architecture
and consists of three main parts:

  1. **Data** (Model)---wraps VCS and its Major Version with parallel 
     PCS structure and conveys the mapping of profiles to minor version.
     Data has no own logics, and only servers as midlayer between various
     VCS, like. GIT, SVN, etc.

  2. **Logic** (Controller)---conveys the main logic of the PCS, updates
     the data and issues viewing of the data either in GUI or CLI applications.
     Controller consists of Preprocessors, that prepares the source files for
     profiling, and Runners that provides profiles. Logic includes layers for
     VCS hooks, external programs, etc.

  3. **View**---conveys the presentation of the data layer. This includes
     Command Line Interface, that can either run as IDLE, or by using commands
     in terminal; and moreover graphical interface implemented in Kivy framework.


Perun Applications
==================

Perun Command Line Interface
----------------------------

  - ``perun config``---gets and sets the configuration for either global or local vcs
  - ``perun help``---show help for the CLI and perun
  - ``perun init``---inits the empty PCS within the directory as the directory ``.perun``,
    note that if there is existing ``.perun`` directory, the command fails with error
  - ``perun status``---shows some minor info, of what runners are currently pending, current
    major and minor version
  - ``perun diff``---shows diff between two chosen profiles, represented by SHA-1 hashes
  - ``perun add``---manually adds either profile, workload or runner
  - ``perun rm``---remove either profile, workload, or runner
  - ``perun aggregate``---aggregates profile to one more generic one
  - ``perun log``---shows current status, how many profiles are there asociated with each
    minor versions, aggregated informations, statistics, etc.
  - ``perun tag``---tags profiles with user given tags
  - ``perun register``---register new runner for given workloads and major versions
  - ``perun show``---shows profile in CLI (note that this is textual representation mostly)
  - ``perun bisect``---similar to git bisect to find quickly which minor version introduced
    the peformance bug


Perun Core
==========

This section describes the internal structure of the Perun platform.

Perun Internals
---------------

The internal implementation of Perun is inspired by GIT Version Control System.
All of the internals corresponding to given Version Control System is stored
in the ``.perun`` directory. Removing this directory removes the tracking and
all of the profiles.

The ``.perun`` directory exploits the tree structure of changes in order to 
achieve the incremental structure of the profiles.

``logic`` Package
-----------------

``logic`` package consists of **Runners** and **Preprocessors**.

Runner Scheduler
~~~~~~~~~~~~~~~~

Runner scheduler is the event driven manager, that manages the runs of asociated runners.
Each time we want to computed the profile, runner along with workload and type of run
is added to scheduler. The scheduled runs are then either run in parallel or sequentially
and generates profiles.

Runners have following modes:

  - ``on_commit`` (``on_new_version``)---asociated runners are run everytime
	new Minor Version is commited to VCS (commit in GIT),
  - ``on_push`` (``on_remote_upload``)---asociated runners are run everytime
	local version control is pushed to remote control system,
  - ``on_checkout`` (``on_backtrack_version``)---asociated runners are run everytime
    older minor or major version is checked out,
  - ``on_demand``---asociated runners are manually run,
  - ``on_scheduled_time``---asociated runners are run at scheduled time and date

Profiles
========

Perun currently supports only three types of profiles (time, space, complexity). 
These can be visualized with several strategies.

!Note that if the checked out Major Version has some uncommited changes, then the
computed profiles cannot be assigned to current minor version!

The main profile of Perun is based on JSON, which is suitable both for presentation
and manipulation within Python and Javascript, and moreover is human readable.

Aside from this format, various Adapters can be constructed to support more formats,
like e.g. Massif format,  callgrind, etc.

Profile types
-------------

Our current focus is on the following types of profiles:

  1. Time---amount of time the program spends on given workload
  2. Space---amount of resources the program spends on given workload,
     moreover, the mapping of objects to addresses.
  3. Complexity---the complexity of the program or given/chosen functions

Collective Profiles
~~~~~~~~~~~~~~~~~~~

*Aggregated Profile* is computed by performing the aggreagion on two profiles, i.e.
creating the most general profile subsuming both of these profile.
Aggregated profiles are not supported for some types of profiles.

Profiles can be aggregated within the same Minor Version, either for the same workload 
or for different workloads.
This yields so called **Collective Profile**.

Collective Profiles are computed either by relative info, and/or by assigning weight
to concrete profiles. Collective profiles serves as general information about the 
current state of the performance for the given Minor Version.

Differential Profiles
~~~~~~~~~~~~~~~~~~~~~

*Differential Profile* (or Profile Diffs) are computed by performing diff between
two profiles of same type. In some cases the diff can fail and thus each diff has
to be run with given diff strategy, in order to infer missing or conflicting differences.

Profile visualizations
----------------------

  - Table
  - Graph
  - Flame Graph
  - Heat Map
  - Object Map

Perun Modes
===========

Perun will be able to run in three modes:
  1. **Offline Mode**---the default mode, where everything is run on the host system

  2. **Online Mode**---optional mode, where everything is run on remote system 
     (supported systems are (i) Travis and possibly (ii) Jenkins)

  3. **Mixed Mode**---mode, where some of the runners will run on host system, 
     and rest will run on remote system

Modes are set for each *Major Version* exclusively, 
as we may need different performance testing for different Major Versions
(note that Major Versions corresponds to Branches in GIT VCS, where this makes sense).
By default, in every tracked *Version Control System* runs in **Offline**.

Offline Mode
------------

The default mode of the Perun. This can be further differentiated to following two strategies:
  1. **Eager Offline Mode**---as soon as you commit, the runners are dispatched and
     profiles are computed.

  2. **Postponed Offline Mode**---the runner jobs are batched in Scheduler to run
     at specific or postponed times.

On client side this is achieved automatically by exploiting the hooks of the 
version controls (for GIT this is achievable) or either by manual run.
For GIT, Perun supports the following hooks:

  - **git commit**---run registered profiles, and optionally merges profiles to aggregated profile,
  - **git checkout**---constructs actual profiles
  - **git branch**---if constructing the new branch, the Perun will ask if
    we want to copy the Perun specification file ``.perun.yml`` for the new branch

Online Mode
-----------

Online mode requires that the tracked version control systems has built in
the Continuous Integration (travis, jenkins). The ``travis.yml`` is modified
to achieve the online mode.

Currently there are several possible strategies of Online mode implementation:
  1. Using web hooks and communicate with travis by HTTP requests (limited though)

  2. Push stuff through github releases

  3. Custom scripts that can fetch the profile.

In travis, this can be implemented within after_success, which means the buggy and
failing build will not be profiled.

Mixed Mode
----------

Alternates between Offline and Online modes. The user has to state, which workloads
and runners are run online and which offline. 

Other Features
===============

This section presents other features that are implemented and supported in Perun.

Notifications
-------------

Whenever the profile is computed, we can issue a checks, whether e.g. pefromance
degradated, or moved over some given threshold. In case this holds, an notification
is send to emails set in config.

Peformance Statistics
---------------------

Perun provides various global statistics for each tracked Version Control Systems.
It can generate statistics over the time or over minor and major versions.
