# Perun: Lightweight Performance Version System

[![build status](https://github.com/Perfexionists/perun/actions/workflows/ubuntu.yml/badge.svg)](https://github.com/Perfexionists/perun/actions)
[![codecov](https://codecov.io/gh/Perfexionists/perun/graph/badge.svg?token=3x4Luodr84)](https://codecov.io/gh/Perfexionists/perun)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/a704486b4679442cb2a53173475f79ca)](https://app.codacy.com/gh/Perfexionists/perun/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
[![GitHub tag](https://img.shields.io/github/tag/Perfexionists/perun.svg)](https://github.com/Perfexionists/perun)
[![Python Version from PEP 621 TOML](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2FPerfexionists%2Fperun%2Fdevel%2Fpyproject.toml)](https://www.python.org)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)


<p align="center">
  <img src="https://raw.githubusercontent.com/Perfexionists/perun/devel/figs/perun-logo.png" width="75%">
</p>

Perun is an open source light-weight Performance Version System, which works as a wrapper over
projects in Version Control Systems (such as `git`) and (in parallel) tracks performance profiles 
(i.e., collection of performance metrics) corresponding to different versions of underlying project. 
Moreover, it offers a wide tool suite that can be used for automation of the performance regression 
test runs, postprocessing of resulting profiles (e.g., by creating performance models) or 
effective interpretation of the results.

<p align="center">
  <img width="460" height="300" src="https://raw.githubusercontent.com/Perfexionists/perun/devel/figs/perun-vs-vcs.svg">
</p>

In particular, Perun has the following advantages over, e.g., using databases or sole Version Control
Systems for the same purpose:

  1.  **Preserves Context**---each performance profile is assigned to a concrete
      minor version adding the functional context (i.e., code changes) of profiles.
      This way, one knows precisely for which code version, the profile was collected.
      
  2.  **Provides Automation**---Perun allows one to easily automate the process
      of profile collection, eventually reducing the whole process to a
      single command. The specification of jobs is read from YAML files.
      
  3.  **Is Highly Generic**---supported format of the performance profiles is
      based on [JSON](https://www.json.org/). Perun tool suite 
      contains a basic set of visualizations, postprocessing and 
      collection modules, but it is easily extensible.
      
  4.  **Is Easy to use**---the workflow, interface and storage of Perun is
      heavily inspired by the git systems aiming at natural use. 

<p align="center">
  <img src="https://raw.githubusercontent.com/Perfexionists/perun/devel/figs/perun-flow.svg">
</p>

Perun is intended to be used in two ways: (1) for a single developer (or a small team) as a complete
solution for automating, storing and interpreting performance of project or (2) as a dedicated store
for a bigger projects and teams. Its git-like design aims at easy distribution and simple interface
makes it a good store of performance profiles along with the functional (or environmental) context.

## Installation

> [!WARNING]
> Installing Perun into the system Python environment may cause dependency conflicts with other
> packages. We highly suggest using some form of virtual environment to install and run Perun
> (see the [Installation in Virtual Environment section](#installation-in-virtual-environment)).

You can install Perun in the system Python environment from pip as follows:

    pip3 install perun-toolsuite

Alternatively you can install Perun from the source code as follows:

    git clone https://github.com/Perfexionists/perun.git
    cd perun
    make install

These commands install Perun to your system as a runnable python package. You can then run Perun
safely from the command line using the `perun` command. Run either `perun --help` or see the [cli
documentation](https://perfexionists.github.io/perun/cli.html) for more information about running Perun
commands from command line. Note that depending on your OS and the location of Python libraries, you
might require root permissions to install Perun.

## Installation in Virtual Environment

To avoid dependency clashes and other installation issues, we recommend installing Perun in some form
of virtual environment. For example:

- **Using the `venv` standard library.** This is the easiest default approach as no additional packages
  or dependencies are needed. For example, the following code snippet creates a virtual environment
  `perun-venv` in the current directory using the system Python version, activates the environment, and
  installs Perun in the environment.

      python -m venv perun-venv
      source perun-venv/bin/activate
      pip install perun-toolsuite
  
  It is also possible to create a virtual environment using different Python version, provided that the
  Python version executable is installed on the system. For example, `python3.12 -m venv perun-venv` will
  create a virtual environment for Python 3.12. Note that the `perun` CLI command will only be accessible
  when the `perun-venv` virtual environment is activated.

- **Using the [`pipx`](https://pipx.pypa.io/stable/) package.** Pipx automatically creates new virtual
  environment for each installed Python application. Provided you have the `pipx` tool available on your
  system, Perun can be installed as follows:

      pipx install perun-toolsuite

  The `perun` CLI command will now be accessible directly without the need to activate any virtual
  environment.

Other forms of virtual environments might work as well, however, these are the only ones we tested.

## System Dependencies

It is possible that some of the Perun commands may not be working at first, or that the installation fails
(if some of the Python dependencies are not available as wheels and need to be built from source). This is
likely due to some missing system dependencies:
- `g++`
- `python-devel`
- `libmagic`
- `coreutils`
- `cmake` (complexity collector)
- `perf` (kperf collector)
- `libunwind`, `libunwind-devel` (memory collector)
- `perl-open` (flamegraph view)

On macOS, additional system dependencies may be needed:
- `gnu-time`
- `libunwind-headers`

## Limited support for macOS

Although Perun can be installed on macOS machines as well, most of the Perun collectors are not supported
yet. Namely: bounds, complexity, kperf, memory and trace. Moreover, the `perun import record` is not
supported as well due to the `perf` tool not being available on macOS.

## Checking Perun Installation

It is advised to verify that Perun is running correctly in your environment as follows:

    # Runs all tests using pytest
    make test

or alternatively using Tox if you wish to test for more Python versions 
(see the [developing section](#developing)).

Note that we do not guarantee Perun to work on other Python versions than those marked as supported
in the `pyproject.toml` file (also shown as a badge at the top of this README).

## Installing Tracer Dependencies

If you wish to use our `tracer` profiler, you have to install its dependencies first. Please refer
to [INSTALL-tracer.md](https://github.com/Perfexionists/perun/blob/devel/INSTALL-tracer).


## Developing

> [!NOTE]
> Do not forget to check for missing [system dependencies](#system-dependencies) if the installation
> or some of the tests fail.

In order to commit changes to the Perun, you have to install Perun in development mode:

    git clone https://github.com/Perfexionists/perun.git
    cd perun
    make dev

This method of installation allows you to make a changes to the code, which will be then reflected
by the installation.

Again, it is advised to verify that Perun is running correctly in your environment as follows:

    # Runs all tests using pytest
    make test

Or you can use [Tox](https://tox.wiki/en/latest/) to run tests for all the supported
Python versions, as well as run static type checking, code style linting and generating
documentation:

    tox run

If you wish to test only against a single Python version, run Tox as:

    tox run -e py3.Y

where `Y` is the python sub-version you wish to test. To see the available Tox environments (and
consequently, the supported Python versions), run:

    tox list

---

If you are interested in contributing to Perun project, please refer to
[contributing](CONTRIBUTING) section. If you think your results could help others, please [send us
PR](https://github.com/Perfexionists/perun/pull/new/develop), we will review the code and in case it is
suitable for wider audience, we will include it in our [upstream](https://github.com/Perfexionists/perun).

But, please be understanding, we cannot fix and merge everything immediately.

## Getting Started with Perun

In order to start managing performance of your project tracked by `git`, 
go to your project directory and run the following:

    perun init --configure
    
This creates a parallel directory structure for Perun storage (stored in `.perun`), 
and creates initial configuration of the local project settings and opens it in the text editor 
(by default `vim`). 
The configuration is well commented and will help you with setting Perun up for your project.
You can specify, e.g., the set of collectors (such as `time` or `trace`), 
or postprocessors and specify which commands (and with which arguments and workloads) should be profiled. 
See [configuration](https://perfexionists.github.io/perun/config.html) for more details about Perun's configuration.

If you only wish to briefly try Perun out and
assuming you have opened the configuration file from the previous step  
(or you can open it from the path `.perun/local.yaml`),
then we recommend to uncomment keys called `cmds`, `workloads` and `collectors`.
This will suffice to demonstrate Perun's capabilities.

If you set up the configuration properly you can 
now start collecting the profiles for the current version of your project using single command:

    perun run matrix
    
This command collects performance data (resulting into so called profiles), 
according to the previously set configuration (see [specification of job matrix](https://perfexionists.github.io/perun/jobs.html#job-matrix-format) for more
details). You can then further manipulate with these profiles: view the list of collected and registered profiles, 
and visualize the profiles (see [visualization overview](https://perfexionists.github.io/perun/views.html)), or check for
possible performance changes (see [degradation
documentation](https://perfexionists.github.io/perun/degradation.html)):

    # Show list of profiles
    perun status
    
    # Show the first generated profile using tabular view
    perun show 0@p tableof --to-stdout resources
    
    # Register the first generated profile to current minor version
    perun add 0@p
    
Now anytime your codebase changes, rerun the collection phase, register new profiles
and you can check whether any change in performance can be detected:

    # Rerun the collection
    perun run matrix
    
    # Register the profiles for current minor version
    perun add 0@p
    
    # Run the degradation check
    perun check head

## Selected Features of Perun

In the following, we list the foremost features and advantages of using Perun:

-   **Unified performance profile format**: our format of performance profiles is baed on
    [JSON](https://www.json.org/); JSON is easily parsable by other programs and languages and provide
    human-readable format. The downside is, however, its storage size and potentially slow processing.

-   **Natural specification of profiling runs**---we allow users to specify how to execute
    regular or more complex profiling workflows (the so-called jobs) in [Yaml](http://yaml.org/) format;
    YAML is widely used in CI/CD and other approaches, and is supported by many programs and languages.

-   **Git-inspired Interface**---we provide command line interface for our tool suite; the commands are inspired by git
    version control systems e.g. `perun add`, `perun remove`, `perun status`, or `perun log`. This allows users to 
    quickly adapt to using Perun and its tool suite.

-   **Efficient storage**---performance profiles are stored compressed in the storage in parallel
    to versions of the profiled project inspired by git. Note, that the resulting profiles can still be huge; we are
    working on compressing and reducing the resulting profiles even further.

-   **Performance modeling**---Perun's suite contains a postprocessing module for regression
    analysis of profiles that construct mathematical models of dependent variables (e.g. runtime) wrt given independent
    variable (see [regression analysis documentation](https://perfexionists.github.io/perun/postprocessors.html#module-perun.postprocess.regression_analysis)),
    which supports several different strategies for finding the best predicting model for given data
    (such as linear, quadratic, or constant model). We also support more advanced modeling using, e.g. kernel regression
    methods; these, however, require more domain specific knowledge.

-   **Interactive Visualizations**---Perun's tool suite includes support for visualization of the results,
    some of them based on [holoviews](https://holoviews.org/) visualization library, which
    provides nice and interactive plots. However, Perun also supports classical output to console as well.

-   **API for profile manipulation**---Perun provides modules for working with
    profiles in external applications---ranging for executing simple queries over the resources
    or other parts of the profiles, to converting or transforming the profiles to different representations
    (e.g. pandas data frame). We particularly recommend using this API in the Python REPL. 
    See [conversion api](https://perfexionists.github.io/perun/profile.html#module-perun.profile.convert) 
    and [query api](https://perfexionists.github.io/perun/profile.html#module-perun.profile.query) for overview.

-   **Automatic Detection of Performance Degradation**---Perun offers several
    heuristics for automatic detection of performance degradation between two project versions (e.g.
    between two commits). This can be used either in Continuous Integrations, in debugging sessions or as parts of some
    precomming hooks.

-   **Performance Fuzz-testing**---Perun offers a performance oriented fuzz testing ---i.e. modifying inputs in
    order to force error or, in our case, a performance change. This allows users to generate new time-consuming inputs
    for theirs projects.

As a sneak peek, we are currently working and exploring the following featurues in near future of
the project:

-   **Automatic Hooks**---a range of automatic hooks, that will allow to automate the runs of job matrix,
    automatic detection of degradation and efficient storage.

-   **Support for more languages**---we are currently working on support for profiling more programming languages. In
    particular, we wish to explore profiling languages such as C#, Python, Go or TypeScript. Moreover, we wish to support
    some well known profilers such as valgrind toolsuite or perf in our workflow.

-   **Optimization of profiling process**---in our ongoing work we are trying to optimize the runtime and the resulting
    storage space of the profiling process while keeping the precision of the results. Some of our optimizations are
    already merged in the upstream, however, we are currently enhancing our methods.

-   **Optimal selection of versions**---currently we automatically only support the comparison of two latest versions in
    git history. Alternatively, one can select two particular profiles to compare. We currently, exploring differt ways
    how to select version in history for comparison for some given version.

For more information about Perun's feature, please refer to our [extensive list of
features](https://perfexionists.github.io/perun/overview.html#list-of-features)!

Contributing
------------

If you'd like to contribute, please first fork our repository and create a dedicated feature branch. Pull requests are
warmly welcome. We will review the contribution (possibly request some changes).

In case you run into some unexpected behaviour, error or anything suspicious, either contact us
directly through mail or [create a new Issue](https://github.com/Perfexionists/perun/issues/new).

We build Perun so it is easily extensible. In case you are interested in extending our tool
suite with new kinds of collectors, postprocessors or visualization methods, please refer to
appropriate sections in Perun's documentation (i.e. Create your own
[collector](https://perfexionists.github.io/perun/collectors.html#creating-your-own-collector),
[postprocessor](https://perfexionists.github.io/perun/postprocessors.html#creating-your-own-postprocessor) 
or [visualization](https://perfexionists.github.io/perun/views.html#creating-your-own-visualization)).
Do not hesitate to contact us, if you run into any problems.

If you are interested in contributing to Perun project, please first refer to
[contributing](Contributing.md) section. If you think your custom module could help others, please
[send us PR](https://github.com/Perfexionists/perun/pull/new/develop), we will review the code and in case
it is suitable for wider audience, we will include it in our
[upstream](https://github.com/Perfexionists/perun).

But, please be understanding, we cannot fix and merge everything.

Links
-----

-   GitHub repository : [https://github.com/Perfexionists/perun](https://github.com/Perfexionists/perun)
-   Issue tracker: [https://github.com/Perfexionists/perun/issues](https://github.com/Perfexionists/perun/issues)
    -   In case of sensitive bugs like security vulnerabilities, please
        contact [Tomas Fiedor](mailto:TomasFiedor@gmail.com) or [Jirka Pavela](mailto:JirkaPavela@gmail.com) directly
        instead of using issue tracker. We value your effort to improve the security and privacy of our project!
-   Project documentation:
    -   Online: [https://perfexionists.github.io/perun/](https://perfexionists.github.io/perun/)
    -   Latest Typeset: [https://github.com/Perfexionists/perun/blob/devel/docs/pdf/perun.pdf](https://github.com/Perfexionists/perun/blob/devel/docs/pdf/perun.pdf)
-   Redhat Research: [https://research.redhat.com/blog/research_project/perun/](https://research.redhat.com/blog/research_project/perun/)

Unrelated links:

-   Check out our group focusing on performance testing and performance anaysis of programs: [Perfexionists](https://github.com/Perfexionists/)
-   Check out our research group focusing on program analysis, static and dynamic analysis, formal methods, verification
    and many more: [VeriFIT](http://www.fit.vutbr.cz/research/groups/verifit/index.php.en)

Licensing
---------

The code in this project is licensed under [GNU GPLv3 license](https://github.com/Perfexionists/perun/blob/devel/LICENSE).

Acknowledgements
----------------

We thank for the support received from [Red Hat](https://www.redhat.com/en/global/czech-republic)
(especially branch of Brno), Brno University of Technology 
([BUT FIT](https://www.fit.vutbr.cz/)), and the VeriFIT and RedHat research groups.

<p align="center">
  <img src="https://raw.githubusercontent.com/Perfexionists/perun/devel/figs/logo-redhat.png">
  <img src="https://raw.githubusercontent.com/Perfexionists/perun/devel/figs/logo-but.png" width="75%">
  <img src="https://raw.githubusercontent.com/Perfexionists/perun/devel/figs/logo-verifit.png">
</p>

Further we would like to thank the following individuals (in the
alphabetic order) for their (sometimes even just a little)
contributions:

-   **Jan Fiedor** (Honeywell)---for feedback, and technical
  discussions;
-   **Jirka Hladký** and his team, and mainly **Kamil Kolakowski** (RedHat)---for technical discussions and cooperation;
-   **Martin Hruška** (BUT FIT)---for feedback, and technical
  discussions;
-   **Viktor Malík** (RedHat)---for feedback and support;
-   **Petr Müller** (SAP)---for nice discussion about the project;
-   **Michal Kotoun** (BUT FIT)---for feedback, and having faith in
  this repo;
-   **Hanka Šimková (Pluháčková)** (BUT FIT)---for awesome logo, theoretical
  discussions about statistics, feedback, and lots of ideas;
-   **Adam Rogalewicz** (BUT FIT)---for support, theoretical
  discussions, feedback;
-   **Tomáš Vojnar** (BUT FIT)---for support, theoretical discussions,
  feedback;
-   **Jan Zelený** (Red Hat)---for awesome support, and feedback.
-   **RedHat Research Team**---Martin Ukrop, Nora Haxhidautiová, Kateřina Kozubková, Marek Grác---for support during integrating Perun in RedHat
-   **Eva Růžičková** (Red Hat)---for photoshooting our team, and having patience with bunch of nerds.

Perun tool (and its authors) are or has been supported by several research
projects. We hereby declare, there has been no double funding. In particular, we
acknowledge the following projects.

<p align="center">
  <img src="https://raw.githubusercontent.com/Perfexionists/perun/devel/figs/logo-eu.png">
</p>

Development of this tool has been supported by AQUAS project (Aggregated Quality Assurance for
Systems, https://aquas-project.eu/). This project has received funding from the Electronic Component
Systems for European Leadership Joint Undertaking under grant agreement No 737475. This Joint
Undertaking receives support from the European Union’s Horizon 2020 research and innovation
programme and Spain, France, United Kingdom, Austria, Italy, Czech Republic, Germany.

This tool as well as the information provided on this web page reflects only the author's view and
ECSEL JU is not responsible for any use that may be made of the information it contains.

<p align="center">
  <img src="https://raw.githubusercontent.com/Perfexionists/perun/devel/figs/logo-excel.gif">
</p>

Development of this tool has been supported by the project GA23-06506S, and
GA20-07487S of the Czech Science Foundation.

<p align="center">
  <img src="https://raw.githubusercontent.com/Perfexionists/perun/devel/figs/logo-gacr.jpg">
</p>

Funded by the European Union under Grant Agreement No. 101087529 Views and opinions expressed are however those of the author(s) only and do not necessarily reflect those of the European Union or European Research Executive Agency. Neither the European Union nor the granting authority can be held responsible for them.

<p align="center">
  <img src="https://raw.githubusercontent.com/Perfexionists/perun/devel/figs/logo-chess.png" width="75%">
</p>

Development of this tool has been supported by the Brno Ph.D. Talent Programme.

<p align="center">
  <img src="https://raw.githubusercontent.com/Perfexionists/perun/devel/figs/logo-jcmm.png">
</p>

Development of this tool has been supported by the project FIT-S-23-8151 of the BUT FIT.

<p align="center">
  <img src="https://raw.githubusercontent.com/Perfexionists/perun/devel/figs/logo-but.png" width="75%">
</p>