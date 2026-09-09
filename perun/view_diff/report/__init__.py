"""A comprehensive HTML difference report of baseline-target profiles.

The report calculates a number of difference metrics for both inclusive and exclusive resource
consumption:

    - proportional diff (prop_diff): reports the difference between the relative resource
      consumption proportionally to the total baseline and target consumption change. For example,
      if the baseline and target consumed 2M and 1M CPU cycles in total, respectively, and a
      function 'foo' consumed 100K cycles in both cases, the proportional difference is +5% as 'foo'
      now consumes 10% total resources up from 5%.
    - absolute diff (abs_diff): reports the difference of Target - Baseline resource consumption.
      For example, if the baseline and target consumed 2M and 1M CPU cycles in total, respectively,
      and a function 'foo' consumed 100K and 75K cycles in baseline, resp. target, the absolute
      difference is -25K.
    - relative diff (rel_diff): reports the difference of Target - Baseline resource consumption in
      relative terms. For example, if the baseline and target consumed 2M and 1M CPU cycles in
      total, respectively, and a function 'foo' consumed 100K and 80K cycles in baseline, resp.
      target, the relative difference is -25%.
"""

import lazy_loader as lazy

__getattr__, __dir__, __all__ = lazy.attach_stub(__name__, __file__)
