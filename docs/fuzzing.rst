.. _fuzzing-overview:

Performance Fuzz-testing
========================

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

.. _fuzing-overview:

Overview
--------

The underdeveloped field of performance fuzz testing has inspired us to
explore this issue more and extend the Perun tool with fuzzing module
that will try to find new workloads (or inputs) that will likely cause
a change in program performance.

  1. **New mutation rules**: The product must offer new, reasonably designed and performance
     affectable rules. The group of rules need to be general, not focusing on the only one type of
     potential performance problem.

  2. **Classic rules**:
     The existing fuzzers have implemented them, and they have achieved
     the success, therefore it is advisable to add some classic generally
     used mutation rules to our collection of rules.

  3. **Perun influence**:
     This means selecting inputs for mutation mainly according to the \ Perun
     results, because it is the main difference from the existing performance
     fuzzers.

  4. **Workload picking based on coverage**:
     Since the fuzzing is a brute-force technique, we do not want to test
     with Perun every workload, just interested in terms of amount of
     executed code. Note that Perun testing would be often unnecessary and
     process of collecting, postprocessing and detection brings
     a considerable overhead.

  5. **Interpretation of workloads**:
     We think that after finishing the fuzz testing, testers primarily want
     to know what workloads are making the troubles to application and how
     they differ from the original files.

  6. **Interpretation of fuzzing**:
     For better imagination of the finished fuzzing process, fuzzer should
     offer visualised information about it that can be helpful for future
     fuzzing.

.. image:: /../figs/excel-fuzzing-overview.*
    :align: center
    :width: 100%

The proposed solution will be modifying *files* (one of the most common
format of program workload). We believe that the \ *mutational* approach
is more suitable in order to create new workloads. Existing projects
inspired us to implement *the feedback loop* with coverage information,
for the purpose of increasing the efficiency and chances to find
the worst-case workloads. Another feedback will be obtained from Perun,
which automatically detects performance changes based on the data
collected within the program runtime.

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

We can collect line coverage only in the presence of source files.
Nevertheless, the fuzzer should provide fuzz testing even without them.
In that case we skip the first (and fast) testing phase and only checks
for possible performance changes. In
Listing [lst:PerformanceFuzzingAlgorithm] is captured an algorithm in
pseudocode, relying only on results of Perun\ ’s detection of
performance change.

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

.. automodule:: perun.fuzz.methods.textfile

.. autofunction:: change_character()
.. autofunction:: delete_character()
.. autofunction:: divide_line()
.. autofunction:: double_line()
.. autofunction:: duplicate_line()
.. autofunction:: delete_line()
.. autofunction:: append_whitespace()
.. autofunction:: insert_whitespace()
.. autofunction:: prepend_whitespace()
.. autofunction:: repeat_whitespace()
.. autofunction:: bloat_words()
.. autofunction:: repeat_word()
.. autofunction:: delete_word()
.. autofunction:: sort_line()
.. autofunction:: sort_line_in_reverse()

.. automodule:: perun.fuzz.methods.binary

.. autofunction:: insert_byte()
.. autofunction:: remove_byte()
.. autofunction:: swap_byte()
.. autofunction:: insert_zero_byte()
.. autofunction:: remove_zero_byte()
.. autofunction:: flip_bit()

.. automodule:: perun.fuzz.methods.xml

.. autofunction:: remove_attribute_value()
.. autofunction:: remove_attribute_name()
.. autofunction:: remove_attribute()
.. autofunction:: remove_tag()

Fuzzer also offers the possibility of adding custom rules. For adding the rules to a mutation
strategy set, one has to launch the fuzzer with a special file in YAML file format containing
the description of these rules. Each rule is represented as an associative array in a form *key:
value*, where both are regular expressions but *key* is a pattern which should be replaced, and
*value* is the replacement.

.. code-block:: yaml

    Back: Front
    del: add
    remove: create
    ([0-9]{6}),([0-9]{2}): \\1.\\2
    (\\w+)=(\\w+): \\2=\\1

If a user wants his custom rules to become a part of the default set of
rules (for certain type of file), it is necessary to implement them and
modify the script ``filetype.py``, which is responsible for selecting
the rules. To add, for example, specific rules for JSON file type, one
just has to create a new script, say ``json.py``, and modify the rules
selection. Note that every rule should contain a brief description,
which will be displayed after fuzzing.

Acquiring Initial Seeds
-----------------------

Workloads can be passed to fuzzer comfortably as an arbitrary mix of files or directories.
Directories are then iteratively walked for all files with reading permissions and optionally name
matching user specified regular expression.  We can fuzz with XML files just with simple regular
expression ``^.*.xml$``. If we want to skip all the files with the name containing string “error” we
can use ``^((?!error).)*$``. Note that the fuzzer should always be launched with just one type of
initial files even if the target application supports more types, since we tune the rules according
to workload file format.

Mutation Methods Selection
--------------------------

It can be further extended by other strategies based on file mime-type as well. We select
corresponding strategies on the beginning, based on the first loaded workload file. Basically, if
this file is a binary, all the rules specific to binaries are added to the set of rules, otherwise
we add all the basic text rules. If the mime type of a file is supported by the fuzzer, we add to
the set of rules mime-specific rules as well as any user-defined rules.

We argue the advantage of fuzzing with one file type rests in its code covering feature. To be more
precise, we are not observing at the overall percentage of code coverage, but how many lines of code
has been executed in total during the run, with an aim to maximise it. Consider an application that
extracts meta-data from different media files, such as WAV, JPEG, PNG, etc. If a PNG image file is
used as a seed to this application, only the parts related to PNG files will be tested. Then testing
with WAV will cause, that completely different parts of the program will be executed, hence total
executed code lines of these two runs cannot compare with each other because reaching higher line
coverage with WAV files would lead to preferring them for fuzzing, and PNG files would be neglected.
Moreover, we are aware that this strategy may miss some performance bugs. Fuzzing multiple
mime-types is current feature work.

Initial Program Testing
-----------------------

Baseline results (i.e. results and measurements of workload corpus) are
essential for detecting performance changes because newly mutated
results have to be compared against some expected behaviour, performance
or value. Hence, initial seeds become test cases and they are used to
collect performance baselines. By default, our initial program testing
as well as testing within the fuzzing loop
interleaves two phases described in more details below: coverage and
performance-guided testing.

In our fuzzer, we use Gcov tool to measure the coverage. The program has
to be build for coverage analysis with GNU Compiler Collection (GCC)
with the option ``--coverage`` (or alternatively a pair of options
``-fprofile-arcs -ftest-coverage``). The resulting file with
the extension ``.gcno`` contains the information about basic block
graphs and assigns source line numbers to blocks. If we execute
the target application a separate ``.gcda`` files are created for each
object file in the project. These files contain arc transition counts,
value profile counts, and additional summary information gcov_.

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
methods.

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
fuzzing from the parents.

Fuzzing Loop
------------

The program can catch SIGINT signal to terminate
the fuzz test when a user decides to quit earlier. Fuzz unit is ready to
receive this signal, however, other Perun units (collectors,
postprocessors) have not implemented handlers for interruption signal,
hence it is not recommended to interrupt during performance testing, but
only in the coverage-guided testing phase. In this section, we described
the main loop of the whole fuzzing process and some of its most
significant parts.

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
very notable. The intuition behind this strategy is to
select the workload for mutation from the best rated parents. From our
experience, selecting only the best rated parent in every iteration does
not led to better results, and other parents are ignored. Hence we do
selection from all the parents, but the parent with better score has
a greater chance to be selected.

.. image:: /../figs/seed_selection.*
   :align: center
   :width: 100%

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

TODO: Add names of the strategies

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
testing are removed.

TODO: Add structure of the output

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

.. image:: /../figs/example_deg_ts.*
    :align: center
    :width: 100%

.. image:: /../figs/example_cov_ts.*
    :align: center
    :width: 100%

Besides visualisation, we create **diff file** for every output file. It
shows the differences between files and the original seed, from which
the file was created by mutation. The file is in HTML format, and
the differences are color-coded for better orientation.

Examples
========

We tested our performance fuzzer on several case studies to measure its
efficiency of generating exhausting mutations. This chapter explores
several performance issues in data structures such as hash table or
unbalanced binary tree, and a group of regular expressions that have
been confirmed as harmful. All the tests ran on a reference machine
Lenovo G580 using 4 cores processor Intel Core i3-3110M with maximum
frequency 2.40GHz, 4GiB memory, and Ubuntu 18.04.2 LTS operating system.

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

.. _fuzzing-cli:

Fuzz-testing CLI
----------------

.. click:: perun.cli:fuzz_cmd
   :prog: perun fuzz