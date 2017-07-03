"""
Display of the resources in flow format.

                        <graph_title>
                `
                -                      ______     ````````
                `                _____/           ` # \\  `
                -               /          __     ` @  }->  <by>
                `          ____/      ____/       ` & /  `
<func>(<of>)    -      ___/       ___/            ````````
                `  ___/    ______/       ____
                -/  ______/        _____/
                `__/______________/
                +````||````||````||````||````

                          <through>

Flow graphs shows the dependency of the values through the other independent variable.
For each group of resources identified by <by> key, a graph of dependency of <of> values
aggregated by <func> depending on the <through> key is depicted. Moreover, the values
can either be accumulated (this way when displaying the value of 'n' on x axis, we accumulate
the sum of all values for all m < n) or stacked, where the graphs are output on each other
and then one can see the overall trend through all the groups and proportions between
each of the group.

Graphs are displayed using the Bokeh library and can be further customized by adding custom
labels for axis, custom graph title and different graph width. Each graph can be loaded from
the template according to the template file.
"""

SUPPORTED_PROFILES = ['memory']

__author__ = 'Radim Podola'
