"""
Flame graph shows the relative and inclusive presence of the resources according to the stack
depth. This visualization uses the awesome script made by © Brendan Gregg!

                           `
                           -                         .
                           `                         |
                           -              ..         |     .
                           `              ||         |     |
                           -              ||        ||    ||
                           `            |%%|       |--|  |!|
                           -     |## g() ##|     |#g()#|***|
                           ` |&&&& f() &&&&|===== h() =====|
                           +````||````||````||````||````||````

Flame graph allows one to quickly identify hotspots, that are the source of the resource
consumption complexity. On X axis, a relative consumption of the data is depicted, while on
    Y axis a stack depth is displayed. The wider the bars are on the X axis are, the more the
function consumed resources relative to others.

Acknowledgements: Big thanks to Brendan Gregg for creating the original perl script for creating
flame graphs out of simple format. If you like this visualization technique, please check out
this guy's site (http://brendangregg.com) for more information about performance, profiling and
useful talks and visualization techniques!
"""

SUPPORTED_PROFILES = ['memory']

__author__ = 'Radim Podola'
