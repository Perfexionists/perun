============================================================================
Complexity Collector Internal Communication Configuration (CCICC) File Draft
============================================================================

Configuration file format used internally by the c/c++ complexity collector.

Version: 1.0

Obligatory file name: ccicc.conf

File Format
-----------
current CCICC still-under-development format::

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

File Format Description
~~~~~~~~~~~~~~~~~~~~~~~
A brief description of the CCICC file format elements.
 - file-name: specifies the collector output file name
 - storage-init-size (optional): specifies the initial storage size if direct file output is not used
 - runtime-filter (optional): specifies functions that must be filtered at runtime
 - sampling (optional): specifies function that will be sampled

   - func: address of a sampled function
   - sample: specifies the sampling rate (e.g. 5 means that only every 5. function occurance will be recorded)

Possible Future Extensions
~~~~~~~~~~~~~~~~~~~~~~~~~~
A list of features that may be implemented in the future.
 - implement non-deterministic sampling (i.e. random instrumentation record capture)

   - possible format: 'sample': 25%
   - possible issues: collection performance

