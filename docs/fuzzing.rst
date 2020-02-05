.. _fuzzing-overview:

Performance Fuzz-testing
========================

    | *‘Only conducting performance testing at the conclusion of system
      or functional testing is like conducting a diagnostic blood test
      on a patient who is already dead.’*
    | — Scott Barber

The presence of errors causing unexpected behaviour of programs is
undoubtedly an unpleasant and unavoidable part of their development. To
tackle this problem, various types of tools and methodologies have
emerged over the years and their primary goal was to eliminate (or at
least reduce) the occurrence of these defects and to provide support for
programmers during development of more complex and extensive programs.

Nowadays, when talking about software aspects, developers are slowly
shifting their focus more on program performance, particularly in
the case of mission-critical applications such as those deployed within
aerospace, military, medical or financial sectors. Naturally, before
deploying anything to the real world, it is essential to make sure that
it is stable enough to handle the expected load.

Performance bugs are not reported as often as *functional bugs*, because they usually do not cause
crashes, hence detecting them is more difficult. Moreover, they tend to manifest with big inputs
only. But, performance patches are usually not that complex. So the fact that a few lines of code
can significantly improve performance motivates us to pay more attention to catching performance
bugs early in the development process. In development, new versions are frequently released, and
regular performance testing of the latest releases can be a proper way of finding performance issues
early. *Perun: Performance Under Control*, is a lightweight open-source tool which includes
automated performance degradation analysis based on collected performance profile. Moreover, it
manages performance profiles corresponding to different versions of projects, which helps a user in
identifying particular code changes that could introduce performance problems into the project’s
codebase or checking different code versions for subtle, long term performance degradation
scenarios. Unexpected performance issues usually arise when programs are provided with inputs (often
called *workloads*) that exhibit worst-case behaviour. This can lead to serious project failures and
even create security issues. The reason is, that precisely composed inputs send to a program may,
e.g., lead to exhaustion of computing resources *(Denial-of-Service attack)* if the input is
constructed to force the worst case.

Unfortunately, manually created test cases might not detect hidden
performance bugs, because it does not have to cover all cases of inputs.
So in order to avoid this, it is appropriate to adapt more advanced
techniques such as the fuzzing.

*Fuzzing* is a testing technique used to find vulnerabilities in
applications by sending garbled data as an input and then monitoring
the application for crashes. Even just an aggressive random testing is
impressively effective at finding faults and has enjoyed great success
at discovering security-critical bugs as well. Using fuzz testing,
developers and testers can ‘hack’ their systems to detect potential
security threats before attackers can. So why should not we use fuzzing
to discover implementation faults affecting performance?

Currently, there are many projects implementing fuzz testing technique,
but unfortunately, none of them allows to add custom mutation strategies
which could be more adapted for the target program and mainly for
triggering performance bugs. In this work, we propose a modification of
fuzz testing unit that will be specialised for producing inputs greedy
for resources. We propose new mutation strategies inspired by causes of
performance bugs found in real projects and integrating them within
the Perun as a new performance fuzzing technique. We believe that
combining performance versioning and fuzzing could raise the ratio of
successfully found performance bugs early in the process.

Analysis and Design
===================

The underdeveloped field of performance fuzz testing has inspired us to
explore this issue more and extend the Perun tool with fuzzing module
that will try to find new workloads (or inputs) that will likely cause
a change in program performance. We will start with a motivational
example as an introduction to the problem, then we analyse the problem
and finally we will propose the solution together with a short
explanation of the principles.

Often, the overall performance of a program highly depends on its input
data (if it consumes any). Although manually written tests can cover
even 100% of the code, test cases may not reveal hidden vulnerabilities
until the unusual input data are provided.

[ht]

[frame=single, framesep=0pt, framerule=1pt, highlightlines=14, linenos,
numbersep=8pt, highlightcolor=hlcolor]C #include <stdio.h> #include
<stdlib.h> #define DIGITS 2

void doSomething(void) return;

int main(void)

FILE \* fp = fopen(“workload.txt”,“r”); char array[DIGITS]; for(int i=0;
i<DIGITS; i++) array[i] = fgetc(fp);

unsigned number = atoi(array); for(unsigned i=0; i<number; i++)
doSomething();

In Listing [lst:motivation-example] one can see an example program,
which reads two characters from an input file (expecting it contains
numerical values), stores them in an array and then converts the array
to an integer using standard ``atoi``\  [13]_(*array to integer*)
function. The original intention was to avoid large numbers and only
take two digits into account, so the number should be out of interval
:math:`<0,99>`. But, this solution contains hidden vulnerability. On
the highlighted line, the result of converting is assigned to
**unsigned** integer variable, but the return value of ``atoi`` function
is a \ **signed** integer. In case that the input file will contain for
example string ’-1’, ``atoi`` will successfully convert the string to
an integer -1, which is represented as ``0xFFFFFFFF`` in hexadecimal (on
architecture where integers are stored on 4 bytes). Considering that
the variable ``number`` is defined as unsigned integer, the following
loop will call ``doSomething`` function ``UINT_MAX``\ (:math:`2^{32}`-1)
times leading to performance degradation.

Problem Analysis
----------------

Basically, the goal of this work is to generate new input data that
could possibly exercise (i.e. consume as many resources or time as
possible) the target program the most. We believe that employing
the fuzz technique could help create such new input data. We propose
that for the purpose of lightweight fuzz testing mutational methodology
is more preferable. Mutational strategies should be more oriented and
tuned for performance. Although traditional mutation strategies were
built rather for finding functional faults, certainly it is good to
combine them with the performance tuned ones.

In conjunction with Perun tool, the approach of regular performance
testing, the user could find with each new version new workloads that
cause a problem and keep track of the progress of project performance
power over time. After fixing the bug of certain performance issue
revealed by the fuzzer, the user is able to test the target application
performance again either with the worst-case workloads assigned to
earlier versions or by repeatedly performing the fuzz testing. Because
fixing one bug may sometimes create new ones.

Requirements for Fuzz Unit
--------------------------

In this section we briefly summarise the functional requirements and
specifications of the resulting product.

1. New mutation rules.
''''''''''''''''''''''

The product must offer new, reasonably designed and performance
affectable rules. The group of rules need to be general, not focusing on
the only one type of potential performance problem.

2. Classic rules.
'''''''''''''''''

The existing fuzzers have implemented them, and they have achieved
the success, therefore it is advisable to add some classic generally
used mutation rules to our collection of rules.

3. Perun influence.
'''''''''''''''''''

This means selecting inputs for mutation mainly according to the \ Perun
results, because it is the main difference from the existing performance
fuzzers.

4. Workload picking based on coverage.
''''''''''''''''''''''''''''''''''''''

Since the fuzzing is a brute-force technique, we do not want to test
with Perun every workload, just interested in terms of amount of
executed code. Note that Perun testing would be often unnecessary and
process of collecting, postprocessing and detection brings
a considerable overhead.

5. Interpretation of workloads.
'''''''''''''''''''''''''''''''

We think that after finishing the fuzz testing, testers primarily want
to know what workloads are making the troubles to application and how
they differ from the original files.

6. Interpretation of fuzzing.
'''''''''''''''''''''''''''''

For better imagination of the finished fuzzing process, fuzzer should
offer visualised information about it that can be helpful for future
fuzzing.

Design of Performance Fuzzer
----------------------------

We have already described the general fuzz testing in
Section [sec:fuzzing\_phases\_and\_principles]. The described steps must
be implemented accordingly to what the unit should be focused on. In
this work we construct a lightweight *Mutation Based Fuzzing Tool* tuned
for detecting performance changes, i.e. performance optimisations and
degradations.

The proposed solution will be modifying *files* (one of the most common
format of program workload). We believe that the \ *mutational* approach
is more suitable in order to create new workloads. Existing projects
inspired us to implement *the feedback loop* with coverage information,
for the purpose of increasing the efficiency and chances to find
the worst-case workloads. Another feedback will be obtained from Perun,
which automatically detects performance changes based on the data
collected within the program runtime.

General Description of the Algorithm
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In this section we will describe design of performance fuzz tester. Its
main loop is depicted in Listing [lst:FullPerformanceFuzzingAlgorithm].

An inevitable element for starting the fuzzing is to collect suitable
set of sample *seed* inputs (or workloads), also called *input corpus*.
In classical fuzzing methods we work with so called inputs, however, in
this work we will adapt the terminology of Perun, which calls the input
of programs the \ *workloads*. The \ *seeds* should be valid workloads
for the target application, so the application terminates on them and
yields expected performance. Collecting workloads into the corpus is
done by pseudo function ``get_initial_corpus`` within the overall
performance fuzzing algorithm captured in
Listing [lst:FullPerformanceFuzzingAlgorithm]. In our fuzzer, the seeds
will be provided by the user.

For different file types (or those of similar characteristics) we want
to use different groups of mutation methods (function
``choose_rules_according_to_filetype``) as described in
Section [sec:Mutation\_strategies]. The knowledge that *seeds* are text
files, not binaries, allows *fuzzer* to avoid binary-tuned fuzz methods
(e.g. *random removing zero bytes*, …). So, we apply domain-specific
knowledge for certain types of files to trigger the performance change
or find unique errors more quickly.

Before running the target application with newly generated malformed
workloads, it is necessary to first determine the \ *performance
baseline*, i.e. the expected performance of the program, to which future
results (so called targets) will be compared. In initial testing we
first measure code coverage (number of executed lines of code) while
executing each initial seed. The median of measured coverage data is
then considered as the baseline for coverage testing (``base_cov``
variable). Second, Perun is run to collected memory, time or trace
resource records with initial seeds resulting into baseline profiles
(``base_profile``). Practically *performance baseline* is a profile
describing the performance of the program on the given workload corpus.
After the initial testing, the seeds in the corpus are considered as
parents for future mutations and rated by the evaluation function.

Once we assemble initial seeds, we can start the actual fuzzing.
The fuzzing loop itself starts with choosing one individual file from
corpus (function ``choose_parent``) using heuristic described in
Section [sec:Parent\_workload\_selection]. This file is then transformed
into mutations (function ``fuzz``) and their quantity is calculated
using dynamically collected fuzz stats (see Section [sec:data\_mutating]
for more details). We test every mutation file with the goal to achieve
maximum possible code coverage. We first focus on gathering
the interesting workloads, which increase the number of executed lines.
We argue that coverage based testing is fast and can yield satisfying
results. Later we will combine these results with the performance check,
which is slower. In case that, code coverage exceeds the certain
threshold, responsible mutation file joins the corpus and therefore can
be fuzzed in future to intentionally trigger more serious performance
issue. Each parent joining the corpus gets rated, in this phase only
according to reached coverage.

.. code-block:: Python

    results = []
    corpus = get_initial_corpus()
    mutation_rules = choose_rules_according_to_filetype(corpus)
    base_cov = init_cov_test(corpus)
    base_profile = init_performance_test(corpus)
    rate_parents(corpus)
    # Fuzzing loop
    while timeout not reached:
       interesting workloads = []
       # Coverage-guided testing
       while execs_limit not reached and collected_files_limit not reached:
          candidate = choose_parent(corpus)
          muts = fuzz(candidate, mutation_rules, fuzz_stats)
          # Gathering interesting mutations
          interesting_workloads += test_for_cov(muts, base_cov, icovr_ratio)
          corpus += interesting_workloads
          rate_parents(interesting_workloads)
          update_stats(fuzz_stats, interesting_workloads)
       adapt_icovr_ratio(icovr_ratio)
       # Profile-guided testing
       results += test_with_perun(interesting_workloads, base_profile)
       update_rates(results)
       update_stats(fuzz_stats, results)

After gathering the interesting workloads, the fuzzer collects run-time
data (memory, trace, time), transforms the data to a so called target
profile and checks for performance changes by comparing newly generated
target profile with baseline performance profile
(see :ref:`degradation_overview_` for more details about
degradation checks). Then the tested workloads rates have to be
recomputed to include the performance change result (function
``update_rates``). The intuition is, that running coverage testing is
faster than collecting performance data (since it introduces certain
overhead) and collecting performance data only for possibly newly
covered paths could result into more interesting workloads. According to
the number of gathered workloads we adapt the coverage increase ratio,
with an aim to either mitigate or tighten the condition for
classification a workload as an interesting one.

List of results of each testing iteration in the main loop contains
successful mutations and the history of the used rules, that led to
their current form. This information is updated after each test run to
make the best decisions at any time. Moreover, collecting interesting
workloads is limited by two variables: the current number of program
executions (``execs_limit``) and the current number of collected files
(``collected_files_limit``). The first limit guarantees that the loop
will terminate. On the other hand, this limit of executions could be set
to excessively high value, which would lead to a long duration of this
phase, especially if the test program itself is used to run for a longer
time. The second limit ensures the loop will end in reasonable time and
collects reasonable number of workloads.

Absence of Source Files
~~~~~~~~~~~~~~~~~~~~~~~

We can collect line coverage only in the presence of source files.
Nevertheless, the fuzzer should provide fuzz testing even without them.
In that case we skip the first (and fast) testing phase and only checks
for possible performance changes. In
Listing [lst:PerformanceFuzzingAlgorithm] is captured an algorithm in
pseudocode, relying only on results of Perun\ ’s detection of
performance change.

.. code-block:: Python

    results = []
    corpus = get_initial_corpus()
    mutation_rules = choose_rules_according_to_filetype(corpus)
    base_profile = init_performance_test(corpus)
    rate_parents(corpus)
    # Fuzzing loop
    while timeout not reached:
       candidate = choose_parent(corpus)
       muts = fuzz(candidate, mutation_rules, fuzz_stats)
       # Profile-guided testing
       results += test_with_perun(muts, base_profile)
       corpus += results
       rate_parents(results)
       update_stats(fuzz_stats, results)

Mutation Strategies
-------------------

In general, the goal of mutational strategies is to randomly modify
a workload to create a new one. We will present a series of rules
inspired by performance bugs found in real projects, and general
knowledge about used data structures, sorting algorithms, or regular
expressions.

Both the types of workloads and the rules for their modification are
divided into two basic groups: *text* and *binary*. In addition, we
added specific rules for XML format based files. Each rule has its own
label name (T stands for text, B for binary and D for domain-specific),
with a brief description of what it concentrates on and
the demonstration result of its application on some sample data.

Text File Strategies
~~~~~~~~~~~~~~~~~~~~

The following rules are constructed strictly for text files. Suppose
the seed workload for fuzzing is the file with the string:

|  

``the quick brown fox jumps over the lazy dog``.

|  
| **Rule T.1: Double the size of a line**. This rule focuses on possible
  performance issues associated with long lines appearing in files.
  The inspiration comes from the gedit [14]_ text editor, which shows
  signs of performance issues when working with too long lines even in
  small text files. Another potential performance issue that this rule
  could force is a poorly validated regular expression that could be
  forced into lengthy backtracking while trying to match the whole line.

|  
| ``the quick brown fox jumps over the lazy dog``

|  
| **Rule T.2: Duplicate a line.** Similar to the previous rule, but
  instead extends the file vertically. Suppose that there is a line in
  a file that represents a performance vulnerability but does not
  manifest in small sizes, therefore the degradation would not be
  detected. By multiplying the line we can likely trigger
  the vulnerability and this could lead to a decline in performance.

|  
| ``the quick brown fox jumps over the lazy dog ``

|  
| **Rule T.3: Divide a line.** Similarly to Rule T.2, the rule may pose
  a threat to programs, whose performance does not depends so much on
  the length of the line as the number of lines in the workload file.
  Moreover, the rule can be effective for regular expressions matching
  whole lines. The line will be cut, which means it will not contain
  what the regular expression would expect, and could force
  backtracking.

|  
| ``the quick brown fox jumps the lazy dog``

|  

**Rule T.4: Change random character.** This is traditional fuzzing
method since the emergence of fuzzing, which can trigger unexpected
behaviour for various reasons. While this is not a specific rule for
performance, in PerfFuzz :raw-latex:`\cite{perffuzz}` authors found
interesting workloads even with basic mutation rules.

|  
| ``the quck brown fox jumps over the lazy dog``

|  
| **Rule T.5: Repeat random word of a line.** On vulnerabilities, e.g.,
  in a handler when a program is trying to store what has been read and
  the record already exists (hash table, or user registration to
  a database). Further, in situations where the program expects unique
  input data, e.g. sorting algorithm QuickSort reaches its worst-case
  when all the elements are
  the same :raw-latex:`\cite{geeks-quicksort}`.

|  
| ``the quick brown fox jumps over the lazy dog ``

|  
| This pair belongs to the rules that focus mainly on sorting algorithms
  and searches in data structures. According
  to :raw-latex:`\cite{geeks-quicksort}`, QuickSort exhibits worst-case
  :math:`O(n^2)` behaviour also when the elements are sorted or
  reversely sorted. We expect that similar behaviour could hold for
  the other sorting algorithms, searching algorithms (and their
  heuristics), and others which assume randomly sorted workload.
  The result is showing which words change their position within
  the line and which not when sorting in ascended and descended order.

|  
| **Rule T.6: Sort words or numbers of a line.**

|  
| ``over ``

|  
| **Rule T.7: (Reversely) sort words or numbers of a line.**

|  
| ``the ``

|  
| The following rules are focused on the efficiency of the program white
  character handling. The inspiration lies in the well-known
  StackOverflow outage on July 20, 2016. The reason of the outage was
  regular expression ``^[\s\u200c]+|[\s\u200c]+$`` intended to trim
  unicode space from start and end of a line. If the string to be
  matched against contains e.g. 20000 space characters in a row, but
  after the last one there is a different character, Regex engine
  expected a space or the end of the string. Realising it cannot match
  like this it backtracks, and tries matching starting from the second
  space, checking 19,999 characters, then from third space and so
  on :raw-latex:`\cite{stackoverflow}`. Similar deployment of
  the seemingly harmless regular expression could be detected with
  the help of these rules.

|  
| **Rule T.8: Append whitespaces.** Sometimes we want to trim a line,
  i.e. remove the white characters from the front or back. This rule
  simply adds 100 to 1000 whitespaces at the end of the line. The amount
  of whitespaces is chosen from the same interval for every rule in this
  group.

|  
| ``the quick brown fox jumps over the lazy dog``

|  
| **Rule T.9: Prepend whitespaces.** A follow-up rule that adds white
  characters to the beginning of a line.

|  
| ``the quick brown fox jumps over the lazy dog``

|  
| **Rule T.10: Insert whitespaces on a random place.** This mutation can
  split data into multiple parts. For applications relying on CPU
  caching this rule could force load of gaps in the memory (which are
  often useless data), and therefore application may slow down.

|  
| ``the quick brown fox jumps over the lazy dog``

|  
| **Rule T.11: Repeat whitespaces.** Follows the same principle as
  the previous rule, with the difference that spaces will be in the same
  place only larger. If the input has a more strict format, then
  the previous rule will not succeed because it breaks the input data
  format. In this case the spaces will be multiplied and the structure
  may not necessarily be corrupted.

|  
| ``the quick brown fox jumps over thelazy dog``

|  
| **Rule T.12: Remove whitespaces of a line.** This method removes any
  white spacing of a line, and thereby creates continuous data. When
  using a hash table, two complications can occur: (a) the hash function
  could calculate the index for a long time, (b) always new unique data
  could quickly fill the table, and thereby enlarging the hash table.
  A similar case is when a program expects a space after e.g. 10
  characters and it is missing in the file.

|  
| ``thequickbrownfoxjumpsoverthelazydog``

|  
| The traditional rules that deletes random parts of the data are
  inspired by fuzz testing cores. Removing of some elements may lead to,
  e.g., the parser waiting for some character or string or number. This
  rule could also be effective in the case of regular expression
  backtracking, again.

|  
| **Rule T.13: Remove random line.**

|  
| ````

|  
| **Rule T.14: Remove random word.**

|  
| ``the quick brown fox jumps over the  dog``

|  
| **Rule T.15: Remove random character.**

|  
| ``the quick brown fx jumps over the lazy dog``

Binary File Strategies
~~~~~~~~~~~~~~~~~~~~~~

We propose the following rules for binary files. In case of binary files
we cannot apply specific domain knowledge nor can we be inspired by
existing performance issues instead we mostly adapt the classical
fuzzing rules. Let us assume binary file with the following content:

|  

``This is !binary! file.\0``.

|  
| The following two rules are based on the fact, that in C language,
  the string is considered to be a series of characters terminated with
  a NULL character ``’\0’``. Thus, a string cannot contain a NULL
  character and by adding it and then reading can terminate the program
  thinking it reached the end of a string and the read data will be
  incomplete. Removing the zero byte could lead to program
  non-termination or crash reading the whole memory.

|  
| **Rule B.1: Remove random zero byte.**

|  
| ``This is !binary! file.``

|  
| **Rule B.2: Add zero byte to random position.**

|  
| ``This is !binary! file.\0``

|  
| The inspiration for the last binary fuzzing rules is their deployment
  and success in existing fuzzing tools. Although they do not have
  a specific focus on performance, they can often trigger unexpected
  behaviour.

|  
| **Rule B.3: Insert random byte.**

|  
| ``This is !binary! file.\0``

|  
| **Rule B.4: Remove random byte.**

|  
| ``This is !inary! file.\0``

|  
| **Rule B.5: Byte swap.**

|  
| ``This is binary! fil.\0``

|  
| **Rule B.6: Bite flip.**

|  
| ``This is binary! file.\0``

|  

Domain-Specific Strategies
~~~~~~~~~~~~~~~~~~~~~~~~~~

If we have more domain-specific knowledge about the workload format we
can devise specific rules. For the purpose of finding potential
vulnerability more quickly, we want to avoid workload discarding at
the potential initial check. We propose rules for removing tags,
attributes, names or values of attributes used in XML based files (i.e.
.\ ``xml``, ``.svg``, ``.xhtml``, ``.xul``). For example, we can assume
a situation, when fuzzer removes closing tag, which will increase
the nesting. Then a recursively implemented parser will fail to find one
or more of closing brackets (representing recursion stop condition) and
may hit a stack overflow error. Let us assume a sample line of XML file:

|  

``< book id=’bk106’ pages=’457’ >``

|  
| **Rule D.1: Remove an attribute.**

|  
| ``< book id=’bk106’ >``

|  
| **Rule D.2: Remove only attribute name.**

|  
| ``< book id=’bk106’ ’457’ >``

|  
| **Rule D.3: Remove only attribute value.**

|  
| ``< book id=’bk106’ pages=’’ >``

|  
| **Rule D.4: Remove a tag.**

|  
| ````

|  
| We can adapt similar rules for e.g. HTML files or JSON-format. In this
  work we limit ourselves to XML only. The concept of how the individual
  rules are selected, when the rule is preferred and the other is
  neglected (or totally rejected) is described in
  Section [sec:MutationMethodsSelection].

Fuzzer also offers the possibility of adding custom rules. For adding
the rules to a mutation strategy set, one has to launch the fuzzer with
a special file in YAML file format containing the description of these
rules. YAML is chosen because the \ Perun tool already includes
ancillary functions for basic work with YAML files. Each rule is
represented as an associative array in a form *key: value*, where both
are regular expressions but *key* is a pattern which should be replaced,
and *value* is the replacement. An example of how such a file might look
like is shown in Listing [lst:regex\_rules].

.. code-block:: yaml

    Back: Front
    del: add
    remove: create
    ([0-9]{6}),([0-9]{2}): \\1.\\2
    (\\w+)=(\\w+): \\2=\\1

Implementation
==============

In previous chapter we proposed a fuzzer with focus on triggering
performance bugs. This work will be integrated in the \ Perun in Python
3.5. In this chapter, we will describe the options of fuzz unit
incorporating in the \ Perun, and reveal selected implementation details
of the Performance Fuzzing Algorithm from
Listing [lst:FullPerformanceFuzzingAlgorithm]
and [lst:PerformanceFuzzingAlgorithm], respectively, and some other
heuristics and features.

Fuzzer Implementation Structure
-------------------------------

The proposed solution required to split the implementation part into
several logical units. We have broken the functionality of the fuzzer
into the following nine modules:

-  ``coverage.py``: implements functions for coverage-guided testing,

-  ``factory.py``: main module of the project, contains the fuzzing
   loop, controls mutating, rating the parents and so on,

-  ``filesystem.py``: contains functions dedicated for various
   operations over files and directories in file system which are
   helpful for fuzzing process,

-  ``filetype.py``: module for automatic recognising the file type and
   choosing appropriate fuzzing rules, and handling with user defined
   rules,

-  ``interpret.py``: contains a set of functions for interpretation
   the results of fuzzing,

-  methods/\ ``binary.py``: collects general fuzzing rules for binary
   files,

-  methods/\ ``textfile.py``: collects general fuzzing rules for text
   files,

-  methods/\ ``xml.py``: collects fuzzing rules specific for XML files.

If a user wants his custom rules to become a part of the default set of
rules (for certain type of file), it is necessary to implement them and
modify the script ``filetype.py``, which is responsible for selecting
the rules. To add, for example, specific rules for JSON file type, one
just has to create a new script, say ``json.py``, and modify the rules
selection. Note that every rule should contain a brief description,
which will be displayed after fuzzing.

Integration within Perun.
'''''''''''''''''''''''''

The task of proposed fuzzer, as part of the \ Perun tool, is to find
the potential harmful workloads during continuous performance testing.
Integration of fuzz unit within Perun is captured in
Figure [fig:fuzzing\_overview].

.. image:: /../figs/excel-fuzzing-overview.*
    :align: center
    :width: 100%

Acquiring Initial Seeds
-----------------------

We first have to get the set of user-provided initial sample workloads
(i.e. workload corpus): a crucial aspect of mutational fuzzing.
Workloads can be passed to fuzzer comfortably as an arbitrary mix of
files or directories. Directories are then iteratively walked for all
files with reading permissions and optionally name matching user
specified regular expression. For example, consider an application that
works with text files (in format of TXT, XML, HTML) and user has one
large directory with various collection of workloads. We can fuzz with
XML files just with simple regular expression ``^.*.xml$``. If we want
to skip all the files with the name containing string “error” we can use
``^((?!error).)*$``. Note that the fuzzer should always be launched with
just one type of initial files even if the target application supports
more types, since we tune the rules according to workload file format.

Mutation Methods Selection
--------------------------

The resulting fuzzer distinguishes between text and binary files and for
each format defines a set of concrete mutation strategies. It can be
further extended by other strategies based on file mime-type as well. We
select corresponding strategies on the beginning, based on the first
loaded workload file. Basically, if this file is a binary, all the rules
specific to binaries are added to the set of rules, otherwise we add all
the basic text rules. If the mime type of a file is supported by
the fuzzer, we add to the set of rules mime-specific rules as well as
any user-defined rules. Note that the group of currently supported
specific methods for certain types can be further expanded by other file
types.

We argue the advantage of fuzzing with one file type rests in its code
covering feature. To be more precise, we are not observing at
the overall percentage of code coverage, but how many lines of code has
been executed in total during the run, with an aim to maximise it.
Consider an application that extracts meta-data from different media
files, such as WAV, JPEG, PNG, etc. If a PNG image file is used as
a seed to this application, only the parts related to PNG files will be
tested. Then testing with WAV will cause, that completely different
parts of the program will be executed,
hence total executed code lines of these two runs cannot compare with
each other because reaching higher line coverage with WAV files would
lead to preferring them for fuzzing, and PNG files would be neglected
(see Section [sec:Parent\_workload\_selection] for more information
about file preference). Moreover, we are aware that this strategy may
miss some performance bugs. Fuzzing multiple mime-types is current
feature work.

Initial Program Testing
-----------------------

Baseline results (i.e. results and measurements of workload corpus) are
essential for detecting performance changes because newly mutated
results have to be compared against some expected behaviour, performance
or value. Hence, initial seeds become test cases and they are used to
collect performance baselines. By default, our initial program testing
as well as testing within the fuzzing loop (Section [sec:fuzzing\_loop])
interleaves two phases described in more details below: coverage and
performance-guided testing.

Coverage-Guided Testing
~~~~~~~~~~~~~~~~~~~~~~~

If one wants to achieve good results in triggering performance changes
it is generally recommended to monitor the code coverage during
the testing especially tracking coverage of unique paths. The intuition
is that by monitoring how many paths are covered and how often they are
executed, we can more likely encounter a new performance bug.

In our fuzzer, we use Gcov tool to measure the coverage. The program has
to be build for coverage analysis with GNU Compiler Collection (GCC)
with the option ``--coverage`` (or alternatively a pair of options
``-fprofile-arcs -ftest-coverage``). The resulting file with
the extension ``.gcno`` contains the information about basic block
graphs and assigns source line numbers to blocks. If we execute
the target application a separate ``.gcda`` files are created for each
object file in the project. These files contain arc transition counts,
value profile counts, and additional summary information :raw-latex:`\cite{gcov}`.

Gcov uses these files for actual profiling which results into the output
``.gcov`` file. Version 4.9 supports easy-to-parse intermediate text
format using the option ``-i`` when launching the tool. However, older
versions does not support this option, hence before the run, we have to
dynamically check the version and accordingly parse the output files.
The difference between intermediate and standard format of output file
is shown in Listings [lst:intermediate-gcov-format]
and [lst:standard-gcov-format].

Total count of executed code lines through all source files represents
the coverage (and partly also a performance) indicator for the first
testing phase. An increase of the value means that more instructions
have been executed (for example, some loop has been repeated more times)
so we hope that performance degradation was likely triggered as well.
Note that the limitation of this approach is that it does not track
uniquely covered paths, which could trigger performance change as well.
Support of more precise coverage metrics is a future work.

So first the target program is executed with all files from workload
corpus. After each single execution, ``.gcda`` files are filled with
coverage information, which Gcov tool parses and generates output files.
We parse coverage data from the output ``.gcov`` file, sum up line
executions, compare with the current maximum, update the maximum if new
coverage is greater and iterate again. It follows that base coverage is
the maximum count of executed lines reached during testing with seeds.

[H]

[frame=single, framesep=0pt, framerule=1pt, linenos,
highlightlines=4,5,6,7,8,9,10,11, numbersep=8pt,
highlightcolor=hlcolor]text file:motivation-example.c
function:6,10,doSomething function:8,1,main lcount:6,10 lcount:8,1
lcount:10,1 lcount:12,3 lcount:13,2 lcount:15,1 lcount:16,11
lcount:17,10

[H]

[frame=single, framesep=0pt, framerule=1pt, linenos,
highlightlines=11,13,15,17,18,20,21,22, numbersep=8pt,
highlightcolor=hlcolor]text -: 0:Source:motivation-example.c -:
0:Graph:motivation-example.gcno -: 0:Data:motivation-example.gcda -:
0:Runs:1 -: 0:Programs:1 -: 1:#include <stdio.h> -: 2:#include
<stdlib.h> -: 3: -: 4:#define DIGITS 2 -: 5: 10: 6:void doSomething()
return; -: 7: 1: 8:int main(int argc, char \*\* argv) -: 9: 1: 10: FILE
\* fp = fopen(“workload.txt”,“r”); -: 11: char array [DIGITS]; 3: 12:
for(int i=0; i<DIGITS; i++) 2: 13: array[i] = fgetc(fp); -: 14: 1: 15:
unsigned number = atoi(array); 11: 16: for(unsigned i=0; i<number; i++)
10: 17: doSomething(); -: 18:

Profile-Guided Testing
~~~~~~~~~~~~~~~~~~~~~~

While coverage-based testing within fuzzing can give us fast feedback,
it does not serve as an accurate performance indicator. We hence want to
exploit results from Perun. Perun runs the target application with
a given workload, collects performance data about the run (such as
runtime or consumed memory) and stores them as a persistent profile
(i.e. the set of performance records). Analogically to the previous
section, we will need a performance baseline, which will be compared
with newly generated mutations. Profiles measured on fuzzed workloads
(so called *target profiles*) are then compared with a profile
describing the performance of the program on the initial corpus (so
called\ *baseline profiles*). In order to compare the pair of baseline
and target profiles, we use sets of calculated regression models, which
represents the performance using mathematical functions computed by
the least-squares method. We then use the \ Perun internal degradation
methods :raw-latex:`\cite{Perun-Excel-2018}` which work as follows. From
both of these sets we select for each function models with the highest
value of *coefficient of determination* :math:`R^2`. This coefficient
represents how well the model fits the data, and also its corresponding
linear models. For both pairs of best models and linear models, we
compute a set of data points by simple subtraction of these models. Then
we use regression analysis to obtain a set of models for these
subtracted data points. Moreover, for the first set of data points,
corresponding to the best-fit models, we compute the relative error,
which serves as a pretty accurate check of performance change. All of
these regressed models are then given to the concrete classifiers, which
returns detected degradations for each function.

Parents Rating
--------------

Initially, the workload corpus is filled with seeds (given by user),
which will be parents to newly generated mutations (we can also call
these seeds *parent workloads*). While we fuzz, we extend the corpus
with successful mutations which become *parent workloads* too.
The success of every workload is represented by the \ *fitness score*:
a numeric value indicating workload’s point rating. The better rating of
workload leads either to better code coverage (and possibly new explored
paths or iterations) or to newly found performance changes. We calculate
the total score by the following evaluation function:

:math:`score_{workload} = icovr_\text{workload} * (1 + pcr_\text{workload})`.

**Increase coverage rate (icovr)**: This value indicates how much
coverage changed if we run the program with the workload, compared to
the base coverage measured for initial corpus. Basically, it is a ratio
between coverage measured with the mutated workload and the base
coverage:

:math:`icovr_\text{workload} = cov_\text{workload} / cov_\text{base}`.

**Performance change rate (pcr)**: In general, we compare the newly
created profile with the baseline profile (for details see
Section [sec:progile\_guided\_testing]) and the result is a list of
located performance changes (namely *degradations*, *optimisations* and
*no changes*). Performance change rate is then computed as ratio number
of degradations in the result list:

:math:`pcr_\text{workload} = \text{cnt(}degradation\text{, }result\text{)} / \text{len}(result)`

This value plays a large role in the overall ranking of workload,
because it is based on the real data collected from the run. And so
workloads that report performance degradations and not just increases
coverage have better ranking. The computation of
:math:`pcr_\text{workload}` could further be extended by the rate of
degradations, i.e. if two workloads found the same number of
degradations, the workload which contains more serious change would be
ranked better. Optimisations of ranking algorithm is another future
work. This evaluation serves for informed candidate selection for
fuzzing from the parents, described in
the Section [sec:Parent\_workload\_selection].

Fuzzing Loop
------------

This main loop runs for a limited time specified the user. One, however
must take take into account that testing and especially performance
analysis has some overhead and so it may sometimes take longer. On
the other hand, the program can catch SIGINT signal to terminate
the fuzz test when a user decides to quit earlier. Fuzz unit is ready to
receive this signal, however, other Perun units (collectors,
postprocessors) have not implemented handlers for interruption signal,
hence it is not recommended to interrupt during performance testing, but
only in the coverage-guided testing phase. In this section, we described
the main loop of the whole fuzzing process and some of its most
significant parts.

Parent Workload Selection
~~~~~~~~~~~~~~~~~~~~~~~~~

The first task at the beginning of every iteration is to select
the workloads from parents which will be further mutated. All parents
are kept sorted by their scores, and the selection for mutation consists
of dividing the seeds into five intervals such that the seeds with
similar value are grouped together. Five intervals seem to be
appropriate because with fewer intervals parents are in too big groups
and in case of more intervals, parents with similar score are
pointlessly scattered. First, we assign a weight to each interval using
linear distribution. Then we perform a weighted random choice of
interval. Finally, we randomly choose a parent from this interval,
whereas differences between parent’s scores in the same interval are not
very notable. The process of selecting is illustrated in
Figure [fig:SeedSelection]. The intuition behind this strategy is to
select the workload for mutation from the best rated parents. From our
experience, selecting only the best rated parent in every iteration does
not led to better results, and other parents are ignored. Hence we do
selection from all the parents, but the parent with better score has
a greater chance to be selected.

.. image:: /../figs/seed_selection.*
   :align: center
   :width: 100%

Data Mutating
~~~~~~~~~~~~~

Once we have baseline data for workload corpus and choose appropriate
mutation rules for concrete file type, we use fuzzer to gradually apply
the mutations and generate new workloads. However, it is necessary to
determine how many new files (:math:`N`) to generate by rule :math:`f`
in the current iteration of fuzzing loop. If :math:`N` is too big and we
generate mutations for each rule :math:`f` from the set of rules,
the corpus will bloat. On the other hand, if :math:`N` is too low, we
might not trigger any change. Instead we propose to dynamically
calculate the value of :math:`N` according to the statistics of fuzzing
rules during the process. Statistical value of rule :math:`f` is
a function:

:math:`stats_f = (degs_f + icovr_f)`

where :math:`degs_f` represents the number of detected degradations by
applying the rule :math:`f`, and :math:`icovr_f` stands for how many
times the coverage was increased by applying rule :math:`f`. Fuzzer then
calculates the number of new mutations for every rule to be applied in
four possible ways:

#. The case when :math:`N=1`, the fuzzer will generate one mutation per
   each rule. This is a simple heuristic without the usage of
   statistical data and where all the rules are equivalent.

#. The case when :math:`N=min(stats_f+1, FLPR)`, the fuzzer will
   generate mutations proportionally to the statistical value of
   function (i.e. :math:`stats_f`). More mutation workloads are
   generated for more successful rules. In case the rule :math:`f` has
   not caused any change in coverage or performance (i.e.
   :math:`stat_f=0`) yet, the function will ensure the same result as in
   the first strategy. File Limit Per Rule (FLPR) serves to limit
   the maximum number of created mutations per rule and is set to value
   100.

#. | Heuristic that depends on the total number of degradation or
     coverage increases (:math:`total`). The ratio between
     :math:`stats_f` and :math:`total` determines the probability
     :math:`prob_f`, i.e. the probability whether the rule :math:`f`
     should be applied, as follows:

     .. math::

        prob_f =
            \begin{cases}
                1    &  \text{if } total=0 \\
                0.1  &  \text{if } stats_f / total < 0.1\\
                stats_f / total & \text{otherwise}
            \end{cases}
   | and we choose :math:`N` as:

     .. math::

        N =
            \begin{cases}
                1  &  \text{if } random <= prob_f \\
                0  &  \text{otherwise }
            \end{cases}

   Until some change in coverage or performance occurs, (i.e. while
   :math:`total=0`), one new workload is generated by each rule. After
   some iterations, more successful rules have higher probability, and
   so they are applied more often. On contrary rules with a poor ratio
   will be highly ignored. However, since they still may trigger some
   changes we round them to the probability of 10%.

#. The last heuristic is a modified third strategy combined with
   the second one. When the probability is high enough that the rule
   should be applied, the amount of generated workloads is appropriate
   to the statistical value. Probability :math:`prob_f` is calculated
   equally, but the equation for choosing :math:`N` is modified to:

   .. math::

      N =
          \begin{cases}
              min(stats_f+1, FLPR)  &  \text{if } random <= prob_f \\
              0  &  \text{otherwise }
          \end{cases}

    Our fuzzer uses this method by default because in our experience it
   guarantees that it will generate enough new workloads and will filter
   out unsuccessful rules without totally discarding them. In case that
   target program is prone to workload change and the user wants better
   interleaving of testing phases, it is recommended to use the third
   method because the maximum number of all created mutations in one
   iteration is limited by the number of selected mutation rules.

Gathering Interesting Mutations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We usually run fuzzing for a longer period of time trying to trigger as
many changes or faults as possible. To maximise the number of found
changes we try to avoid running the target application with workloads
with a poor chance to succeed.

In the situation, when the workload does not exceed the coverage
threshold, it is not significant, because the estimated instruction path
length is not satisfactory, hence we discard this workload.
The threshold for discarding mutations is multiple of base coverage, set
to 1.5 by default, but it can also be specified by the user. A mutation
is classified as an interesting workload in case two criteria are met:

:math:`cov_{mut} > cov_{threshold} \And cov_{mut} > cov_{parent} `

i.e. it has to exceed the given threshold and achieve a higher number of
executed lines than its predecessor.

In addition, we feel that the user may not know the ideal threshold and
the default value may be too high or too low. Therefore, the constant
which multiplies the base coverage (and thus determines the threshold)
changes dynamically during fuzzing. In case it is problematic to reach
the specified coverage threshold, the value of the constant decreases
and thus gives more chance for further mutations to succeed. Vice versa,
if the mutations have no problem to exceed the threshold, the value of
the constant is probably too low, and hence we increase it.

During the testing, fuzzed workload can cause that target program
terminates with an error (e.g. SIGSEGV, SIGBUS, SIGILL, …) or it hangs
(runs too long). Even though we are not primarily focused on faults,
they can be interesting for us as well because an incorrect internal
program state can contain some degradation and in case of error,
handlers can also contain degradation.

The Final Phase of Iteration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

After the mutation, all the interested workloads are collected and ready
for real testing to detect performance changes. Testing is done
similarly to the initial profile-guided testing
(Section [sec:progile\_guided\_testing]), but instead we test with
fuzzed interesting workloads. If the \ Perun detect some performance
degradation, the particular mutation’s rate is recalculated, fuzzer
update its statistics of mutation rules, and one iteration is at
the end.

.. image:: /../figs/lifetime_of_mutation.*
    :align: center
    :width: 100%

Interpretation of Fuzzing Results
---------------------------------

During the fuzzing, every file executed with the target program, where
the collected runtime data showed a performance drop, joins the set of
*final results*. A tester can then analyse these workloads manually. In
addition, fuzzer also produces files by which program terminated with
an error, or ran too long and these files are stored in specific
folders. Other mutations that have been created while running fuzz
testing are removed. An example of the structure and content of
an output directory is shown in Listing [lst:output\_structure].

In order to interpret the results of fuzzing we propose two
visualisation techniques: time series and workload difference.
The **time series** graphs show the number of found mutations causing
degradation and the maximum recorded number of lines executed per one
run. From these graphs, one can e.g. read the time needed to achieve
sufficient results and estimate orientation time for future testing. In
both graphs are denoted three statistically significant values: first
quartile, second quartile (median) and third quartile from the y-axis
values. The intention is to illustrate at what point in time we have
achieved the individual portion of the result.

For plotting time series graphs we used matplotlib [15]_ library and
difflib [16]_ module helps to calculate deltas between files. Examples
of results interpretation are shown in Figures [fig:example\_deg\_ts]
and [fig:example\_cov\_ts].

.. image:: /../figs/example_deg_ts.*
    :align: center
    :width: 100%

.. image:: /../figs/example_cov_ts.*
    :align: center
    :width: 100%

Besides visualisation, we create **diff file** for every output file. It
shows the differences between files and the original seed, from which
the file was created by mutation. The file is in HTML format, and
the differences are color-coded for better orientation. Example of diff
file is shown in Listing [lst:diff].

[H]

[escapeinside=\|\|, frame=single, framesep=5pt, framerule=1pt, linenos,
numbersep=8pt]text — +++ @@ -1 +1 @@ \|\| \|\|

[H]

[escapeinside=@@, frame=single, framesep=5pt, framerule=1pt, linenos,
numbersep=8pt]text @@ \|— @@ \|—
medium\_words-02000b239d024dbe933684b6c740512e-diff.html \|—
medium\_words-389d4162ad6641d187dc405000b8d50a-diff.html \|—
medium\_words-39b5d7aa55fd404aa4d31422c6513e2c-diff.html \|— @@ \|—
medium\_words-389d4162ad6641d187dc405000b8d50a.txt \|— @@ \|—
coverage\_ts.pdf \|— degradations\_ts.pdf \|— @@ \|—
medium\_words-39b5d7aa55fd404aa4d31422c6513e2c.txt \|— @@ \|—
coverage\_plot\_data.txt \|— degradation\_plot\_data.txt \|—
results\_data.txt \|— medium\_words-02000b239d024dbe933684b6c740512e.txt

Experimental Evaluation
=======================

We tested our performance fuzzer on several case studies to measure its
efficiency of generating exhausting mutations. This chapter explores
several performance issues in data structures such as hash table or
unbalanced binary tree, and a group of regular expressions that have
been confirmed as harmful. All the tests ran on a reference machine
Lenovo G580 using 4 cores processor Intel Core i3-3110M with maximum
frequency 2.40GHz, 4GiB memory, and Ubuntu 18.04.2 LTS operating system.

Sorting Vulnerabilities
-----------------------

Unbalanced Binary Tree (UBT).
'''''''''''''''''''''''''''''

Time consumption of inserting to an unbalanced binary tree highly
depends on the order of insertion. Even though it is expected to consume
:math:`O(n.log(n))` time when inserting :math:`n` elements, if
the elements are sorted beforehand, the tree will degenerate to a linked
list, and so it will take :math:`O(n^2)` time to insert all :math:`n`
elements.

First, we constructed files with randomly generated 1000 integers in
the range of <0, 1000> and 10000 integers in the range of <0, 10000>,
and we used them as initial seeds (:math:`seed_1`, :math:`seed_2`) to
a program that creates an UBT, iteratively inserts elements, and at
the end prints the created UBT. We expected that the program performance
will highly depend on the amount of workload data, so with the aim to
avoid large files we limited the maximum size of mutations.

| l\|r\|r\|r\|r & **size [B]** & **runtime [s]** & **executed LOC
  ratio** & **tree height**
| :math:`seed_1` & 3879 & 0.011 & 1.00 & 21
| :math:`worst`-:math:`case_{11}` & 1939 & 0.033 & 5.94 & 309
| :math:`worst`-:math:`case_{12}` & 3879 & 0.110 & 24.46 & 625

| :math:`seed_2` & 48913 & 0.109 & 1.00 & 26
| :math:`worst`-:math:`case_{21}` & 24456 & **2.927** & 49.34 & 3253
| :math:`worst`-:math:`case_{22}` & 48912 & **11.014** & 187.36 & 6346

Analysis of worst-case mutations confirmed that unbalanced binary tree
degenerates to a linked list when a sorted list is inserted.
Table [tbl:UBT] presents the results of the program run with
the worst-case workloads from each testing. The rules applied on
the most exhausting workloads are listed in Table [tbl:UBT\_rules].

+-----------------------------------+----------------------------------+
|                                   | **used mutation rules**          |
+===================================+==================================+
| :math:`worst`-:math:`case_{11}`   | [T.7, T.6, T.3, T.6, T.2, T.6]   |
+-----------------------------------+----------------------------------+
| :math:`worst`-:math:`case_{12}`   | [T.7, T.6, T.1, T.7, T.4]        |
+-----------------------------------+----------------------------------+
| :math:`worst`-:math:`case_{21}`   | [T.6]                            |
+-----------------------------------+----------------------------------+
| :math:`worst`-:math:`case_{22}`   | [T.7]                            |
+-----------------------------------+----------------------------------+

Table: Table shows the sequence of mutation rules that transformed
the seeds into worst-case workloads. Each rule is identified by a label,
as defined in Section [sec:Mutation\_strategies]. One can see that rules
for sorting were more frequently used and thus more successful in
mutation.

std::list + std:find.
'''''''''''''''''''''

In our second experiment, we tested the standard library list
(``std::list``\  [17]_) which is usually implemented as a doubly-linked
list, and we performed a search with ``std::find``\  [18]_ function.
The tested program reads strings from a file, saves them to list and
subsequently performs a search for each of them. First initial seed
contained 5000 random english words (:math:`seed_1`), and in the second
set of tests the initial seed contained 10000 random english words
(:math:`seed_2`). For each seed the program run for 266 milliseconds,
and 524 milliseconds respectively in average to fill the list and then
find every word. In first experiments, we set the maximum size of
generated workload to the value of initial seed and in the second one to
double of the value. After testing we collect the worst-case workloads
and their impact on program is shown in Table [tbl:find\_testing].
The rules that led to transformation of the seeds into the worst-case
workloads are listed in Table [tbl:find\_rules].

+-----------------------------------+----------------+-------------------+--------------------------+-------------+
|                                   | **size [B]**   | **runtime [s]**   | **executed LOC ratio**   | **words**   |
+===================================+================+===================+==========================+=============+
| :math:`seed_1`                    | 37459          | 0.266             | 1.00                     | 5000        |
+-----------------------------------+----------------+-------------------+--------------------------+-------------+
| :math:`worst`-:math:`case_{11}`   | 37458          | 0.485             | 1.88                     | 5003        |
+-----------------------------------+----------------+-------------------+--------------------------+-------------+
| :math:`worst`-:math:`case_{12}`   | 74918          | **1.860**         | 7.53                     | 10011       |
+-----------------------------------+----------------+-------------------+--------------------------+-------------+
| :math:`seed_2`                    | 74915          | 0.524             | 1.00                     | 10000       |
+-----------------------------------+----------------+-------------------+--------------------------+-------------+
| :math:`worst`-:math:`case_{21}`   | 74897          | 1.876             | 3.78                     | 10041       |
+-----------------------------------+----------------+-------------------+--------------------------+-------------+
| :math:`worst`-:math:`case_{22}`   | 149830         | **7.278**         | 15.05                    | 20024       |
+-----------------------------------+----------------+-------------------+--------------------------+-------------+

Table: The most greedy generated workloads compared to initial workload.
Processing the worst-case workload, which was the same size as the seed,
took program slightly more time to process, roughly in similar
proportion as executed LOC ratio. By inspection of these workloads we
noticed, that the parts of them are sorted. As one can see, the greater
performance change was discovered when the seed containing around
10000 words, which was expected. Note that worst-case file is two times
bigger, contains two times more words, but incur one order of magnitude
degradation. In comparison, the execution with a file contained the same
words as :math:`worst`-:math:`case_{22}`, but randomly shuffled, took
only 2.102 seconds in average.

+-----------------------------------+-------------------------------------------------+
|                                   | **used mutation rules**                         |
+===================================+=================================================+
| :math:`worst`-:math:`case_{11}`   | [T.3, T.7, T.6, T.2, T.6, T.6]                  |
+-----------------------------------+-------------------------------------------------+
| :math:`worst`-:math:`case_{12}`   | [T.2, T.7, T.1, T.8, T.1, T.6, T.1]             |
+-----------------------------------+-------------------------------------------------+
| :math:`worst`-:math:`case_{21}`   | [T.7, T.3, T.3, T.3, T.3, T.3, T.3, T.3, T.3]   |
+-----------------------------------+-------------------------------------------------+
| :math:`worst`-:math:`case_{22}`   | [T.7, T.1, T.6]                                 |
+-----------------------------------+-------------------------------------------------+

Table: Table lists history of applied rules for worst-case mutations.
Notice, that rules providing sort of the elements (T.6 and T.7) appear
in the history of every mutation.

Regular Expression Denial of Service (ReDoS).
---------------------------------------------

In this case study, we tested artificial programs which use
``std::regex_search``\  [19]_ with regular expressions inspired by
existing ReDoS attacks. ReDoS is an attack based on algorithmic
complexity where regular expression are forced to take long time to
evaluate, mostly because of backtracking algorithm, and leads to
the denial of service.

StackOverflow trim regex.
'''''''''''''''''''''''''

The first experiment is the regular expression that caused an outage of
StackOverflow in July, 2016 :raw-latex:`\cite{stackoverflow}`.
An artificial program reads every line and search for match with
the regular expression. We used simple source code in C performing
parallel grep as an initial seed, written in 150 lines. With only two
tests, we could force the vulnerability, as we show in
Table [tbl:stackoverflow]. Which rule is responsible for revealing
the weakness can be found in Table [tbl:stackoverflow\_rules].

| l\|r\|r\|r\|r\|r & **size [B]** & **runtime [s]** & **executed LOC
  ratio** & **lines** & **whitespaces**
| :math:`seed` & 3535 & 0.096 & 1.00 & 150 & 306

| :math:`worst`-:math:`case_1` & 5000 & **1.566** & 24.32 & 5 & 4881

:math:`worst`-:math:`case_2` & 10000 & **2.611** & 41.38 & 17 & 9603

+----------------------------------+----------------------------------+
|                                  | **used mutation rules**          |
+==================================+==================================+
| :math:`worst`-:math:`case_{1}`   | [T.10, T.10, T.10, T.10]         |
+----------------------------------+----------------------------------+
| :math:`worst`-:math:`case_{2}`   | [T.10, T.10, T.10, T.10, T.10]   |
+----------------------------------+----------------------------------+

Table: Multiple uses of rule that inserts whitespaces to random position
result into big gaps not ending with end of line: the weakness of tested
regular expression.

Email validation regex.
'''''''''''''''''''''''

This regular expression is part of the Regular Expression Library [20]_
and is marked as malicious and triggering ReDoS. We constructed
a program that takes an email address from a file and tries to find
a match with this regular expression. As an initial seed we used a file
containing valid email address ’spse1po@gmail.com’. We ran two tests, in
the first case with an email that must contain the same count of
characters as the seed, and in the second case it can contain twice
the size. We present the results in Table [tbl:email] and rules that
were used on these mutations are listed in Table [tbl:email\_rules].

| l\|r\|r\|r & **size [B]** & **runtime [s]** & **executed LOC ratio**
| :math:`seed` & 18 & 0.016 & 1.00

| :math:`worst`-:math:`case_1` & 18 & 0.176 & 70.83

| :math:`worst`-:math:`case_2` & 25 & **10.098** & 4470.72

| :math:`worst`-:math:`case_{2hang}` & 36 & **>5 hours** &
  :math:`\infty`

+--------------------------------------+---------------------------+
|                                      | **used mutation rules**   |
+======================================+===========================+
| :math:`worst`-:math:`case_1`         | [T.15, T.8, T.15, T.1]    |
+--------------------------------------+---------------------------+
| :math:`worst`-:math:`case_2`         | [T.15, T.15, T.1]         |
+--------------------------------------+---------------------------+
| :math:`worst`-:math:`case_{2hang}`   | [T.15, T.15, T.1]         |
+--------------------------------------+---------------------------+

Table: Two rules, namely removing random character and extending a size
of line, were mostly encouraged in the generation of the presented
workloads.

In the following we list the most greedy workloads from each testing and
their **content**:

-  :math:`worst`-:math:`case_1`: ``spse1pogailcspse1p``

-  :math:`worst`-:math:`case_2`: ``spse1poailcospse1poailco``

-  :math:`worst`-:math:`case_{2hang}`:
   ``spse1poailcospse1poailcospse1poailco``

Java Classname validation regex.
''''''''''''''''''''''''''''''''

This vulnerable regular expression for validation of Java class names
appeared in OWASP Validation Regex Repository [21]_. The testing program
was similar to the previous one: reads a class name from a file and
tries to find a match with this regular expression. Initial file had one
line with string ’myAwesomeClassName’. To avoid the large lines, first
we set a size limit for mutations to the size of the initial seed
(19 bytes), then to double and finally to quadruple of the size. We
present the results of these three tests in Table [tbl:java]. In
addition, Table [tbl:java\_rules] shows the order of rules used to
mutate the initial seeds.

+--------------------------------------+----------------+-------------------+--------------------------+
|                                      | **size [B]**   | **runtime [s]**   | **executed LOC ratio**   |
+======================================+================+===================+==========================+
| :math:`seed`                         | 19             | 0.005             | 1.00                     |
+--------------------------------------+----------------+-------------------+--------------------------+
| :math:`worst`-:math:`case_1`         | 19             | 0.016             | 14.31                    |
+--------------------------------------+----------------+-------------------+--------------------------+
| :math:`worst`-:math:`case_2`         | 36             | 1.587             | 2383.99                  |
+--------------------------------------+----------------+-------------------+--------------------------+
| :math:`worst`-:math:`case_3`         | 78             | **3.344**         | 5056.67                  |
+--------------------------------------+----------------+-------------------+--------------------------+
| :math:`worst`-:math:`case_{3hang}`   | 78             | :math:`\infty`    | :math:`\infty`           |
+--------------------------------------+----------------+-------------------+--------------------------+

Table: We detected two orders of magnitude degradation within run of
program with the worst-case from the last test case
(:math:`worst`-:math:`case_3`). The fuzzer generates and stores another
26 files that was classified as hangs. By additional testing we found
the \ :math:`worst`-:math:`case_{3hang}` workload which had enormous
impact on program performance, and program did not terminate even after
13 hours lasting run.

+--------------------------------------+-----------------------------------------------------+
|                                      | **used mutation rules**                             |
+======================================+=====================================================+
| :math:`worst`-:math:`case_1`         | [T.8, T.15, T.8, T.15, T.15, T.1, T.12, T.8, T.1]   |
+--------------------------------------+-----------------------------------------------------+
| :math:`worst`-:math:`case_2`         | [T.8, T.15, T.15, T.2, T.8, T.15]                   |
+--------------------------------------+-----------------------------------------------------+
| :math:`worst`-:math:`case_3`         | [T.8, T.15, T.1, T.4, T.2]                          |
+--------------------------------------+-----------------------------------------------------+
| :math:`worst`-:math:`case_{3hang}`   | [T.8, T.15, T.1, T.15, T.2]                         |
+--------------------------------------+-----------------------------------------------------+

Table: Table lists the rules in order they was applied on the initial
seeds and created malicious workloads. Removing characters together with
data duplicating, appending whitespaces and other rules collaborated on
generation of the worst-case mutations for this case study.

We again list the \ **content** of generated mutations:

-  :math:`worst`-:math:`case_1`: ``mywesomelassamemywm``

-  :math:`worst`-:math:`case_2`: ``mywesomelassamemywesomelassam``

-  :math:`worst`-:math:`case_3`:
   ``ssammyAwesomelassammyAweiomelassaVmyAwes×melassammmyAwesome lassammyAweomel``

-  :math:`worst`-:math:`case_{3hang}`:
   ``laalaalaalaalaalaalaalaalaalaalaalaalaalaalaalaalaalaala alaalaalaalaalaalaal``

We also tested other regular expressions, which can be forced to
an unlucky backtracking, e.g., expressions to validate a HTML file,
search for a specific expression in CSV files or validation of a person
name from OWASP Validation Regex Repository. Some of them are part of
the evaluation in an article presented at Excel@FIT’19
conference :raw-latex:`\cite{PerunFuzz-Excel-2019}`.

Hash Collisions
---------------

Finally, we tried our fuzzer on a simple word frequency counting
program, which uses hash table with a fixed number of buckets
(12289 exactly) and the maximum length of the word limited to 127.
The distribution of the words in the table is ensured by the hash
function. It computes a hash, which is then used as an index to
the table. Java 1.1 string library used a hash function that only
examined 8-9 evenly spaced characters, which can result into collisions
for long strings :raw-latex:`\cite{hashing}`. We have implemented this
behaviour into an artificial program. The likely intention of
the developers was to save the function from going through the whole
string if it is longer. Therefore, for fuzzing, we initially generated
a seed with 10000 words of 20 characters and started fuzzing. To compare
the results we chose the DJB hash function [22]_, as one of the most
efficient hash functions. Tables [tbl:hash] and [tbl:hash\_rules] show
the result of this last experiment.

+--------------------------------+-----------------+--------------------+-----------------+--------------------+--------+
|                                |                 |                    |                 |                    |        |
+--------------------------------+-----------------+--------------------+-----------------+--------------------+--------+
|                                | **size [kB]**   | **runtime [ms]**   | **LOC ratio**   | **runtime [ms]**   |        |
+--------------------------------+-----------------+--------------------+-----------------+--------------------+--------+
| :math:`seed`                   | 210             | 26                 | 1.0             | 13                 | 1.0    |
+--------------------------------+-----------------+--------------------+-----------------+--------------------+--------+
| :math:`worst`-:math:`case_1`   | 458             | ****               | 3.48            | ****               | 2.19   |
+--------------------------------+-----------------+--------------------+-----------------+--------------------+--------+
| :math:`worst`-:math:`case_2`   | 979             | ****               | 7.88            | ****               | 4.12   |
+--------------------------------+-----------------+--------------------+-----------------+--------------------+--------+

Table: After only 10 minutes of fuzzing each test case was able to find
interesting mutations. We then compared the run by replacing the hash
function in early Java version with DJB hash function, which computes
hash from every character of a string. Table shows, that worst-case
workloads have much more impact on performance of the hash table and
less stable times using Java hash function, compared to DJB. With such
a simple fuzz testing developers could avoid similar implementation
bugs.

+--------------------------------+---------------------------------------------------------+
|                                | **used mutation rules**                                 |
+================================+=========================================================+
| :math:`worst`-:math:`case_1`   | [T.2, T.3, T.15, T.15, T.11, T.15]                      |
+--------------------------------+---------------------------------------------------------+
| :math:`worst`-:math:`case_2`   | [T.2, T.3, T.4, T.15, T.9, T.4, T.2, T.3, T.15, T.15]   |
+--------------------------------+---------------------------------------------------------+

Table: Table shows the sequence of mutation rules that transformed
the seed into worst-case workloads. In this experiment the rules that
duplicates data (T.2), increases number of lines (T.3), changes and
removes random characters (T.4 and T.15) were the most frequent.

We also tried our solution on projects that worked with binary and XML
files. Since they did not incur any changes in performance, they are not
part of the experimental evaluation. Therefore, improving the existing
binary and domain-specific rules together with designing new ones is one
of our future goals.

.. [1]
   Clone of fuzz and ptyjig — https://github.com/alipourm/fuzz

.. [2]
   Testing without peering into the internal structure of the component
   or system

.. [3]
   signal — http://man7.org/linux/man-pages/man7/signal.7.html

.. [4]
   ptrace — http://man7.org/linux/man-pages/man2/ptrace.2.html

.. [5]
   strace — http://man7.org/linux/man-pages/man1/strace.1.html

.. [6]
   clang — https://clang.llvm.org/

.. [7]
   Testing with knowledge about the internal structure of the component
   or system

.. [8]
   AS — the portable GNU assembler —
   http://man7.org/linux/man-pages/man1/as.1.html

.. [9]
   systems that records changes of source code files over the time so
   that one can recall specific version later

.. [10]
   JavaScript Object Notation — https://www.json.org/

.. [11]
   SystemTap — https://sourceware.org/systemtap/documentation.html

.. [12]
   graphical representation of data which values contained in a matrix
   are represented by colours

.. [13]
   atoi — https://en.cppreference.com/w/cpp/string/byte/atoi

.. [14]
   gedit — https://wiki.gnome.org/Apps/Gedit

.. [15]
   matplotlib — https://matplotlib.org/

.. [16]
   difflib — https://docs.python.org/3/library/difflib.html

.. [17]
   std::list — https://en.cppreference.com/w/cpp/container/list

.. [18]
   std::find — https://en.cppreference.com/w/cpp/algorithm/find

.. [19]
   std::regex\_search —
   https://en.cppreference.com/w/cpp/regex/regex_search

.. [20]
   http://regexlib.com/REDetails.aspx?regexp_id=1757

.. [21]
   https://www.owasp.org/index.php/OWASP_Validation_Regex_Repository

.. [22]
   http://www.partow.net/programming/hashfunctions/#DJBHashFunction

.. _fuzzing-cli:

Fuzz-testing CLI
----------------

.. click:: perun.cli:fuzz_cmd
   :prog: perun fuzz