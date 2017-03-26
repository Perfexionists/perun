============================================================================
ComplexityCollector Internal Runtime Configuration (CIRC) File Draft
============================================================================

Configuration file format used internally by the c/c++ complexity collector.

Version: 1.1

Obligatory file name: circ.conf

File Format
===========
Current CIRC still-under-development format::

  CIRC = {
    "file-name": "trace.log",
    "storage-init-size": 20000,
    "runtime-filter": [
      4198356,
      4197960
    ],
    "sampling": [
      {
        "func": 4198008,
        "sample": 5
      },
      {
        "func": 4198590,
        "sample": 3
      }
    ]
  }

File Format Types Specification
-------------------------------
Description of the various types used in the CIRC file.

Magic code
~~~~~~~~~~
The CIRC magic code::

  CIRC = {
    ...
  }

must be always present.

Text element
~~~~~~~~~~~~
The text element is always enclosed in a pair of double quotes::

  "text-element"

Number element
~~~~~~~~~~~~~~
The number element is interpreted as a decimal value and thus must strictly consist of only decimal characters (0 - 9).
Negative values are not supported (nor needed). Number elements must not have a leading zeros::

  25000

File Format Description
-----------------------
A brief description of the CIRC file format elements.

 - file-name: specifies the collector output file name, default value: "trace.log"
 - storage-init-size (optional): specifies the initial storage size if direct file output is not used
 - runtime-filter (optional): specifies functions that must be filtered at runtime
 - sampling (optional): specifies function that will be sampled

   - func: address of a sampled function
   - sample: specifies the sampling rate (e.g. 5 means that only every 5. function occurance will be recorded)

Possible Future Extensions
--------------------------
A list of features that may be implemented in the future.

 - implement non-deterministic sampling (i.e. random instrumentation record capture)

   - possible format: 'sample': 25%
   - possible issues: collection performance


Changelog
---------
Changelog reflecting the development

 - 1.0: 

   - Added
 - 1.1: 

   - The address element removed, all such elements changed to number elements instead. 
   - Changed the syntax to be more JSON-like.
 - 1.2:

   - Renamed to the ComplexityCollector Internal Runtime Configuration (CIRC)

