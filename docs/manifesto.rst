===============
Perun Manifesto
===============

.. contents::

Perun Design Choices
====================

This section explains some of the design choices, that were made.
Perun was made with the following goals in mind:

  1. Platform independent---profiling and version controling can be
     done both on Unix/Windows/MacOS systems.

  2. Language independent---perun should be independent on the underlying
     project language (this also complies with the Point 1.).

  3. Lightweight---perun should not be robust, should be easy to install,
     and easy and natural to use. Morever, one should be able to change the
     innermost data as well.

  4. Efficient---eficiency is one of the factors of perun---both in terms of
     space and time consumption.

  5. Fresh and modern---for authors, this serves as great experience for
     exploring modern and fresh technologies and thus appropriate frameworks
     are usually chosen.

This section only serves as self-assurance and possible explanation, why perun
is implemented as it is.

Language of Choice
------------------

**Python** was chosen as the implementation language, both for having large number
of frameworks and libraries and being platform independent. Moreover the implementation
in python is lightweight without need to solve memory allocation and other architecture
specific details.

CLI Framework of Choice
-----------------------

**Click** was chosen as the framework for command line interface. ``Docopts`` was ruled out
for being hard to use, through the docstrings. Click is built over the ``getopts`` and is
similar to the classical ``argparse``, however, is much easier to use and also
enables nesting of the commands, that is necessary for the command line work with
repository-like structure.

GUI Framework of Choice
-----------------------

**Kivy** was chose as the framework for graphical user interface. While other frameworks
were considered as well (like **PyQT**), kivy seems natural for multi-platform applications
and provides nice look. Moreover, ``Kivy`` has clear separation between presentation and
logic.

Visualization of Choice
-----------------------

Currently under consideration. Current candidates are: **Bokeh** and **Mathplotlib**.
**Mathplotlib** is easier to integrate in GUI application of ``Kivy``, however, has
less options and is harder to use. **Bokeh**, on the other hand, is easy to use and
provides lots of customization.

Structure of Perun
------------------

The implementation details of perun storage is inspired by **GIT** design.
While it was considered to use database (like **MongoDB**, that would solve
the efficient storage), we felt, that it would be too robust and will add a layer
of complexity. Instead with the low-level approach to storing the profiles and
other informations enables one to have full control over the Performance Control System
using both low-level and high-level commands. Moreover, the interlacing between VCS and PCS,
like e.g. for **GIT** is then natural and enables one some pretty neat tricks automatizations.

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


Perun Command Line Interface
============================

The command line interface of Perun is realized using the ``Click`` python library,
that was chosen for its flexibility, easy usage and because it is under active development.
Moreover, it can handle nested commands required for repository-like behaviour.

  - ``perun config``---gets and sets the configuration for either global or local vcs
  - ``perun help``---show help for the CLI and perun
  - ``perun init``---inits the empty PCS within the directory as the directory ``.perun``,
    note that if there is existing ``.perun`` directory, the command fails with error

    - ``--init-vcs=TYPE``---besides perun initialize the VCS repository of VCS type;
      note that if there already exist vcs of *TYPE* ``perun init`` ends with error
    - ``--init-vcs-params=PARAMS``---supply additional parameters for ``vcs init``
  - ``perun status``---shows some minor info, of what runners are currently pending, current
    major and minor version

    - ``--short``, ``-s``---short status of the perun
  - ``perun diff PROFILE1 PROFILE2``---shows diff between two chosen profiles,
    represented by SHA-1 hashes

    - ``-diff-algorithm=ALG``---use different diff strategy
  - ``perun add MINOR PROFILE``---manually adds profile to minor version

    - ``--``---separate multiple files
  - ``perun rm``---remove either profile

    - ``--``---separate multiple files
  - ``perun aggregate PROFILE1 PROFILE2``---aggregates profile to one more generic one

    - ``--strategy=STRATEGY``---will use different aggregation strategy
  - ``perun log MINOR``---shows current status, how many profiles are there asociated with each
    minor versions, aggregated informations, statistics, etc.

    - ``--count-only``---only shows number of profiles associated to minor versions
    - ``--show-aggregate``---shows aggregated profiles for each minor version
    - ``--last N``---print only last N minor versions
  - ``perun tag``---tags profiles with user given tags
  - ``perun register``---register new runner for given workloads and major versions or
    register new workload
  - ``perun unregister``---unregister existing runners or workloads

    - ``--``---separation of the list of register runners or workloads
  - ``perun show``---shows profile in CLI (note that this is textual representation mostly)

    - ``--one-line``---displays the profile in one line
    - ``--coloured``---displays the profile with colours
  - ``perun bisect``---similar to git bisect to find quickly which minor version introduced
    the peformance bug

    - ``--auto``---try to infer the bad peformance commits automatically
  - ``perun query``----query the profiles using the perun query language

    - ``SELECT``---select profiles that satisfy the query
    - ``DROP``---remove profiles that satisfy the query
    - ``ADJUST``---adjust the values of profile according to the given transform function

Perun Least Publishable Unit
----------------------------

The least publishable unit (i.e. the minimalisitic prototype of the perun) contains the
following commands:

  - ``perun help``
  - ``perun config``
  - ``perun init``
  - ``perun add``
  - ``perun rm``
  - ``perun log``
  - ``perun show``


Perun Core
==========

This section describes the internal structure of the Perun platform.

Perun Config
------------

  - ``vcs``---information about underlying version control system

Perun Internals
---------------

The internal implementation of Perun is inspired by GIT Version Control System.
All of the internals corresponding to given Version Control System is stored
in the ``.perun`` directory. Removing this directory removes the tracking and
all of the profiles.

The ``.perun`` directory exploits the tree structure of changes in order to
achieve the incremental structure of the profiles.

The ``.perun`` directory contains the following files and special directories:

  - ``HEAD``---currently "checked" out major version
  - ``objects\``---directory with objects (minor version indexes, profiles)
  - ``major-versions\``---directory with all major versions

Each major version corresponds to some minor version (that has some history
of previous minor versions), this way we get the history of our project in
order to execute diffs between minor versions. Minor versions points to indexes
that maps files and workloads to concrete profiles, which are packed using the
Zlib.

Command Case Study: Init new perun control system
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The user wants to initialize new perun pcs.

If the resulting pcs should be manual it is enough to run ``perun init``.
The command will first check if there is not existing pcs and otherwise
creates a new ``.perun`` directory initialized with bare structure.

If the user wants to wrap the perun over existing vcs, the parameter ``--type=VCS``
has to be given. The command first checks if there exists the vcs of
given type, then inits the perun the same way as bare init and
moreover install hooks for the given type of VCS.

Another alternation is to run the ``init`` with ``--init-vcs`` parameter
that along with perun creates a empty repository with given params.

Command Case Study: Add profile
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The user wants to manually add ``PROFILE`` corresponding to ``MINOR`` version.

Both ``PROFILE`` and ``MINOR`` is represented either using references (which
are further translated to SHA-1) or directly by SHA-1.

The input profile is taken and its SHA-1 is computed, which will be used for having unique
representation. The contents of the profile are packed using the Zlib library.

Then we lookup the *index* and *pack* for the given ``MINOR`` SHA-1. First two bytes
are taken that represents the directory, the rest of the 38 bytes are used to identify
corresponding minor version.

Inside the object, we update the fanout table at the start, for the given two bytes
of the ``PROFILE`` SHA-1. The appropriate entry is then added to the index file,
the offsets are updated according to the lenght of the added profile data.

The pack file is then extended by the contents of the given profile.

Command Case Study: Remove profile
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The user wants to manually remove ``PROFILE`` corresponding to ``MINOR`` version.

Both ``PROFILE`` and ``MINOR`` is represented the same as in the previous case study.

Similarly to previous study, the index file is looked up out of ``MINOR`` SHA-1 number.
Inside that we lookup the appropriate entry for the ``PROFILE`` SHA-1. The offset
is retrieved in order to locate the packed profile inside the pack.

Insides of the pack are removed, and the index is updated with new offsets.

Command Case Study: Show profile
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The user wants to show the ``PROFILE`` corresponding to ``MINOR`` version.

Both ``PROFILE`` and ``MINOR`` is represented the same as in the previous case study.

First we look into cache, which stores up to 10 (maybe more?) unpacked profiles for
fast access of the profiles, without the need of unpacking.

Similarly to previous study, the index file is looked up out of ``MINOR`` SHA-1 number.
Inside that we lookup the appropriate entry for the ``PROFILE`` SHA-1. The offset
is retrieved in order to locate the packed profile inside the pack.

The contents are retrieved from the pack, since we know the offset and the size of the
content from the index file. The given data are unpacked using Zlib and added to .cache
for quicker lookup.


Command Case Study: Show all minor versions and profiles
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The user wansts to get the list of all ``MINOR`` version corresponding to the
current ``MAJOR`` version (read from ``HEAD`` file).

First the HEAD reference is obtained, if no SHA-1 is supplied from command line.
which stores the SHA-1 of the most recent minor version. This serves as a starting point for the ``perun log``.

Similarly to previous commands, the SHA-1 is used to locate the entry of the minor version.
Basic informations are printed out, and then the information about profiles. If the ``--count-only``
is supplied, only fanout table is parsed and we return the number of profiles associated to the
minor version. Otherwise every profile in the index file is printed to the output.

After the minor version is parsed, we look at the parent of the minor version and
proceed same as for the previous commit. If we supplied the ``--last=N`` argument,
we print only ``N`` minor versions starting from the given SHA-1.

``core/logic`` Package
----------------------

``core/logic`` package consists of **Runners** and **Preprocessors**.

Job Matrix
~~~~~~~~~~

Perun builds on the ideas of travis, which uses the build matrix for continuous integration.
In the configuration file corresponding to the wrapped repository, there are specified collectors,
postprocess phases, and then the commands that will be run consisting of parameters, binaries
and workloads. Job matrix can e.g. look as follows::

  collectors:
    - name: time
    - name: memory
      sampling: -s 10

  postprocessors:
    - name: filter
      params: <20
    - name: normalizer

  bins:
    - name: gaston
      params:
        -p -q -g
        -s 10
    - mona
      params:
         - q -s

  workloads:
     - ex10.mona
     - ex14.mona

The binaries are paired with their corresponding params and then the cartesian product is
constructed with workloads, this yield the following commands:

  - ``gaston -p -q -g ex10.mona``
  - ``gaston -s 10 ex10.mona``
  - ``gaston -p -q -g ex14.mona``
  - ``gaston -s 10 ex14.mona``
  - ``mona -q -s ex10.mona``
  - ``mona -q -s ex14.mona``

Further the collectors are paired with the list or postprocesses yielding the following phases:

  - ``time | filter <20 | normalizer``
  - ``memory -s 10 | filter <20 | normalizer``

Finally we do the cartesian product with the previous commands yield overall of 12 jobs.

Template for Runners
~~~~~~~~~~~~~~~~~~~~

Each runner ``name`` (e.g. postprocessor and collector) has to be defined in the package ``name``
in the ``name.py`` module, in the corresponding ``perun.{collect,postprocess}`` package. So e.g.
the ``time`` collector will be defined inside the ``perun.collect.time.time`` module.

Inside the ``name.py`` are three functions with the following signatures:

  - ``before(**kwargs)``---phase that is run before the ``collect()`` or ``postprocess()`` phases,
    it is mainly for initialization of various data and/or to produce the runnable binary.
  - ``collect(**kwargs)``/``postprocess(**kwargs)``---the actual phase of the postprocessing or
    collecting of the data. This phase should run the binary and collect either the whole profile
    or at least the raw data. This phase is **mandatory**!
  - ``after(**kwargs)``---phase that is run after the main function. This serves as optional post
    processing of the raw data or the computed profile.

Each of these functions should expect the data defined in the ``header`` part of the profile,
i.e. the command (``cmd``), arguments (``params``), workload (``workload``) and additional params
from the job matrix.

Each of these function should return the triple of ``(status code, status msg, updated kwargs)``,
where:

  - ``status code``---integer representing the status of the phase (0 for OK, nonzero for error),
  - ``status msg``---additional message of the status (mainly for error),
  - ``updated kwargs``---additional params that should be passed to the next phase

Either ``after`` or ``collect``/``postprocess`` function should return the profile in the updated
kwargs associated to the key ``profile``.

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

``core/data`` Package
---------------------

``core/data`` package consists of **Profiles** and wrappers over **Version Control Systems**.

``view`` Package
----------------

``view`` Package contains the **GUI** and **Visualizers** for the profiles.

Profiles
========

Perun currently supports only three types of profiles (time, space, trace).
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
  3. Trace---the complexity of the program or given/chosen functions

Perun profile format is currently under development, the current version is
described in the following snipped, where the # parts are used as comments for
the parts of the profile

Note that the minor_version is removed, as the profile can possibly correspond to more minor
versions, e.g. when nothing was changed with the commit::

  Profile = {
    'header': {
      # General information about profile: its type
      'type': 'memory',
      # Command that was run and for which the data was collected
      'cmd': '/dir/subdir/bin',
      # Params used to run the command
      'params': '-g -w -c',
      # Workload, i.e. some file/input/output supplied
      'workload': 'load.in',
      # Units for the given types
      'units': [
        'memory': 'MB',
        'time': 'ns'
      ]
    }

    # Collector informations
    'collector': {
      # The name of the run collector
      'name' : 'collector_name',
      # Parameters used during running of the collector
      'params': '-sample 20 --no-recurse',
    },

    # Information about all of the postprocessor phases
    'postprocessors': [
      {'name': 'filter', 'params': '<30'}
    ],

    # Information about result of the computation
    'result': {
      'status': 0
      'status-msg': 'everything was expensive'
    }

    # Global snapshot
    'global': {
        # Timestamp of the snapshot (when it ended)
        'time': 12.32s,
        # List of resources corresponding to the snapshot with additional info
        'resources': [
           # Amount: how many of the resource it was consumed
           # Uid: unique identifier of the location or the resource
           # Type: type of the quantified resource
           # Trace: trace of the resource (callstacks, previous calls, whatever)
           {
             # Amount of the consumed resources
             'amount': 30,
             # Unique identification of the resource: name of the function, etc.
             'uid': '/dir/subdir/loc',
             # Type of the consumed resources
             'type': 'memory',
             # Subtype of the resource (e.g. time delta, malloc, calloc allocations, etc.)
             'subtype': 'malloc',
             # Trace leading to the UID
             'trace':'',
             # Address where the resource was consumed (mainly for memory)
             'address': '242341243',
             # Number of units in the structure (for Jirka's BP)
             'structure-unit-size': 132,
           },
        ]
     },

     # List of snapshots containing objects similar to global one
     'snapshots': [
       {
         'time': '1.0s',
         'resources': [
            {'amount': 12MB, 'uid': '/dir/subdir/loc#13' },
            {'amount':  1MB, 'uid': '/dir/subdir/loc#47' }
         ]
       },
       {
         'time': '2.0s',
         'resources': [
            {'amount': 37MB, 'uid': '/dir/subdir/loc#13' },
            {'amount':  3MB, 'uid': '/dir/subdir/loc#47' }
         ]
       }
     ]
  }

Example of time profile, with data collected by ``time`` utility::

  {
    'type': 'time',
    'minor_version': a5cf40ebf33610c97083b209fc12a36adc3a99ff,
    'cmd': '/dir/subdir/bin',
    'param': '-g -w -v',
    'workload': 'load.in',

    'collector': {
       'name': 'time',
       'params': ''
    },

    'global': {
        'timestamp': 12.32s,
        'resources': [
           {'amount': 0.616s, 'uid': 'real'}
           {'amount': 0.500s, 'uid': 'user'}
           {'amount': 0.125s, 'uid': 'sys'}
        ]
    },

  'snapshots': []
  }

Example of mixed profile, with data collected by custom collector::

  {
    'type': 'mixed',
    'minor_version': a5cf40ebf33610c97083b209fc12a36adc3a99ff,
    'cmd': './gaston',
    'param': '--serialize',
    'workload': 'ex4.mona',

    'collector': {
       'name': 'gaston-collect',
       'params': ''
    },

    'global': {
       'timestamp': 0.59s,
       'resources':[
          {'amount': 0.10s, 'uid': 'sa-creation', 'type': 'time'},
          {'amount': 0.45s, 'uid': 'dec-proc', 'type': 'time'},
          {'amount': 0.01s, 'uid': 'cleaning', 'type': 'time'},
          {'amount': 4817, 'uid': 'mona-space', 'type': 'term'},
          {'amount': 31712, 'uid': 'overall-space', 'type': 'term'},
          {'amount': 977296, 'uid': 'fixpoint-space', 'type': 'term'}
       ]
   }
  }

Example of memory collected data::

  {
    'type': 'memory',
    'minor_version': a5cf40ebf33610c97083b209fc12a36adc3a99ff,
    'cmd': './gaston',
    'param': '--serialize',
    'workload': 'ex4.mona',

    'collector': {
       'name': 'massif',
       'params': ''
    },

    'snapshots': [
      { 'timestamp': 123393017,
        'resources': [
          {'amount': 4134891, 'uid': 'mem_heap_B', 'type': 'memory'},
          {'amount': 564725, 'uid': 'mem_heap_extra_B', 'type': 'memory'}
        ]
      },
      { 'timestamp': 16162105,
        'resources': [
          {'amount': 4134891, 'uid': 'mem_heap_B', 'type': 'memory'},
          {'amount': 564725, 'uid': 'mem_heap_extra_B', 'type': 'memory'}
        ]
      }
    ]
  }

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

Performance Statistics
----------------------

Perun provides various global statistics for each tracked Version Control Systems.
It can generate statistics over the time or over minor and major versions.
