"""
Display of the resources in bar format::

                              <graph_title>
                   `
                   -         .::.                ````````
                   `         :&&:                ` # \\  `
                   -   .::.  ::::        .::.    ` @  }->  <by>
                   `   :##:  :##:        :&&:    ` & /  `
   <func>(<of>)    -   :##:  :##:  .::.  :&&:    ````````
                   `   ::::  :##:  :&&:  ::::
                   -   :@@:  ::::  ::::  :##:
                   `   :@@:  :@@:  :##:  :##:
                   +````||````||````||````||````

                                <per>

Bar graphs shows aggregation of resources according to the given criteria. Each bar
displays <func> of resources from <of> key (e.g. sum of amounts, average of amounts, etc.)
per each <per> key (e.g. per each snapshot). Moreover, the graphs can either be (i) stacked,
where the different values of <by> key are shown above each other, or (ii) grouped, where the
different values of <by> key are shown next to each other.

Graphs are displayed using the Bokeh library and can be further customized by adding custom
labels for axis, custom graph title and different graph width. Each graph can be loaded from
the template according to the template file.
"""

SUPPORTED_PROFILES = ['memory']

__author__ = 'Radim Podola'
