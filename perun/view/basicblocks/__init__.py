"""`Basic Blocks` - displays information about basic blocks as a sunburst graph.

Displays the percentage of time spent exclusively in visualized functions as 
well as time spent in the top basic blocks from each of these functions, which 
helps to point out the most demanding functions and also basic blocks. this 
visualization also provides ability to modify its output by filtering how many 
functions or basic blocks to display. Besides the time metrics, similar 
information about number of executions is displayed as well.

.. _Bokeh: http://docs.bokeh.org/en/0.12.6/docs/gallery/burtin.html
"""

SUPPORTED_PROFILES = ['mixed']


__author__ = 'Peter Močáry'
