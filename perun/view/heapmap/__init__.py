"""
`Heap map` is a visualization of underlying memory address map that links
chunks of allocated memory to corresponding allocation sources.  This is mostly
for showing utilization of memory, where objects were allocated, how often, and
how the objects are fragmented in the memory. Heap map visualization is
interactive and is implemented using ncurses library.
"""

SUPPORTED_PROFILES = ['memory']

__author__ = 'Radim Podola'
