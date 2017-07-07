"""
Memstat is a set of simple queries over memory profiles, with collected allocation info.

#1 `'`'`'`'``'`
  -'```-``-``-
    -```'`'```-``'`'

#2 ''``'`'`-'`""-'''
  - ''`'`'`'`'`'

Memstat contains several predefined functions for aggregated basic information about allocations
within the profile---list of allocations, tops, sums, etc.---and serves as a base for future.
"""

SUPPORTED_PROFILES = ['memory']

__author__ = 'Radim Podola'
