.. _profile-format:

Perun's Profile Format
======================

.. todo::
   Add link to JSON

Format supported by Perun is based on JSON format with several restrictions regarding the keys
needed in the profile. The intuition of usage of JSON-like notation stems from its human readability
and well-established support in leading programming languages (namely Python and JavaScript).

.. image:: /../figs/lifetime-of-profile.*
   :width: 100%
   :align: center

.. _profile-spec:

Specification of Profile Format
-------------------------------

The generic scheme of the format can be simplified in the following regions::

    {
        "origin": "...",
        "header": {...},
        "collector_info": {...},
        "postprocessors": [...],
        "global": [...],
        "snapshots": [...],
        "chunks": {...}
    }

Some of these are optional, and some can be change through the further postprocessing phases,
like e.g. by :ref:`postprocessors-regression-analysis`. In the following we will decribe the
regions in more details.

.. todo::
   Add examples to each of the region.

.. perfreg:: origin

Origin specifies the concrete minor version to which the profile corresponds. This key is present
only, when the profile is not yet assigned in the control system. Before the storage, origin is
removed and only serves as a check, so we do not assign profiles of different origin.

.. perfreg:: header

Header is a key-value dictionary of basic information about the profile, like e.g. the type of the
profile, the command which was used to generate it, its parameters and workloads. The following
keys can be used:

.. perfkey:: type

Specifies the type of the profile. Currently time, mixed and memory is considered.

.. perfkey:: units

Maps types (and subtypes) of resources to their units. Note that the resources should be in the
same units.

.. perfkey:: cmd

Specifies the command which was executed to generate the profile. This can be either some script,
some command, or execution of binary. In general this corresponds to a profiled application. Note
that some collectors are working with their own binaries (like e.g. :ref:`collectors-complexity`
and will thus omit this command; however it can still be used for tagging the profiles)

.. perfkey:: params

Specifies list of arguments or parameters that supplied to the :pkey:`cmd` that was run. This is
used for more fine distinguishing of profiles regarding its parameters (e.g. when we run command
with different optimizations, etc.). Optional, can be empty.

.. perfkey:: workload

Workloads refer to a different inputs that are supplied to profiled command with given arguments.
E.g. when one profiles text processing application, workload will refer to a concrete text files
that are used to profile the application. Optional, can be empty.

.. perfreg:: collector_info

This region contains information about collector, which was used to generate the data.

.. perfkey:: name

Name of the used collector.

.. perfkey:: params

Key-value dictionary of parameters for the given collector.

.. perfreg:: postprocessors

List of postprocessing units with information analogous to :preg:`collector_info`. Order of the
postprocessors info specifies how the postprocessors were applied (since the ordering can have
impact on the resulting data).

.. perfreg:: global

.. todo::
   This needs to be changed in the collectors since we are changing the specification

Global region contains a list of resources corresponding collected by the profiler.

.. perfreg:: chunks

.. todo::
   Add information that this is in proposal only.

Currently in proposal. Chunks are meant to be a look-up table which maps unique identifiers to
a larger portions of JSON region. Since lots of informations are repeated through the profile,
this is meant as an space optimization.

.. _profile-conversion-api:

Profile Conversions API
-----------------------

.. automodule:: perun.profile.convert

.. autofunction:: resources_to_pandas_dataframe

.. autofunction:: to_heap_map_format

.. autofunction:: to_heat_map_format

.. autofunction:: to_flame_graph_format

.. _profile-query-api:

Profile Query API
-----------------

.. automodule:: perun.profile.query

.. autofunction:: all_resources_of

.. autofunction:: all_items_of

.. autofunction:: all_resource_fields_of

.. autofunction:: all_numerical_resource_fields_of

.. autofunction:: unique_resource_values_of

.. autofunction:: all_key_values_of

.. autofunction:: all_models_of

.. autofunction:: unique_model_values_of
