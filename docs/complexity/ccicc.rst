============================================================================
Complexity Collector Internal Configuration Communication (CCICC) File Draft
============================================================================

Configuration file format used internally by the c/c++ complexity collector.

Version: 1.0

Obligatory file name: ccicc.conf

File Format
===========
Current CCICC still-under-development format::

  CCICC = {
    'file-name': 'trace.log',
    'storage-init-size': 20000,
    'runtime-filter': [
      0x4017ed,
      0x4016fc
    ],
    'sampling': [
      {'func': 0x4015cd, 'sample': 5},
      {'func': 0x4013fa, 'sample': 3}
    ]
  }

File Format Types Specification
-------------------------------
Description of the various types used in the CCICC file.

Magic code
~~~~~~~~~~
The CCICC magic code::

  CCICC = {
    ...
  }

must be always present.

Text element
~~~~~~~~~~~~
The text element is always enclosed in a pair of apostrophes::

  'text-element'

Number element
~~~~~~~~~~~~~~
The number element is interpreted as a decimal value and thus must strictly consist of only decimal characters (0 - 9).
Negative values are not supported (nor needed). Number elements must not have a leading zeros::

  25000

Address element
~~~~~~~~~~~~~~~
The address element is interpreted as a hexadecimal value (thus only 0 - 9, a - f symbols are permitted) with 0x leading sequence::

  0x4010fe

File Format Description
-----------------------
A brief description of the CCICC file format elements.
 - file-name: specifies the collector output file name
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

