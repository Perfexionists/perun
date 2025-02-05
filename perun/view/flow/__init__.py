"""`Flow graphs` displays resources as classic plots, with moderate
customization possibilities (regarding the sources for axes, or grouping keys).
The output backend of `Flow` is both Bokeh_ and ncurses_ (with limited
possibilities though). Bokeh_ graphs support either the classic display of
resources (graphs will overlap) or in stacked format (graphs of different
groups will be stacked on top of each other).

.. _Bokeh: https://bokeh.pydata.org/en/latest/
.. _ncurses: https://www.gnu.org/software/ncurses/ncurses.html
"""

SUPPORTED_PROFILES = ["memory"]
