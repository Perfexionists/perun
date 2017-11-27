.. _example:

Case Study: Complexity Analyais
===============================

.. todo::
   Add examples of outputs for each of the visualization

.. _example-init:

Step 1: Initialize the Repo
---------------------------

    1. Clone the complexity repo?
       git clone etc.
    2. Initialize the stuff (but there should be perun checked out already, right?
       perun init
    3. Fill the matrix
       perun config --edit
    4. Show git log + perun status

.. _example-baseline:

Step 2: Generate Baseline Profiles
----------------------------------

    1. Run perun matrix
    2. Run perun add
    3. Show output of Perun status

.. _example-changes:

Step 3: Change the Project
--------------------------

    1. Use a patch to get different version
    2. Make commit
    3. Recompile
    4. Show git log

.. _example-newhead:

Step 4: Generate Profiles for New Head
--------------------------------------

    1. Run perun matrix
    2. Run perun add
    3. Show output of Perun status for HEAD and HEAD~1

.. _example-interpret:

Step 5: Interpret the Results
-----------------------------

    1. Run perun show scatter for baseline
    2. Run perun show scatter for new head
    3. Discuss the differences
