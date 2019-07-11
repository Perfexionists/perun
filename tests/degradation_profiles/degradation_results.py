import perun.check.linear_regression as lreg
import perun.check.polynomial_regression as preg
from perun.utils.structs import PerformanceChange


_PREG_EXPECTED_RESULTS = [
    # CONSTANT MODEL
    [
        # CONSTANT
        [
            # ERROR
            {'result': PerformanceChange.Degradation, 'type': 'constant', 'rate': 999},
            # IMPROVEMENT
            {'result': PerformanceChange.Optimization, 'type': 'constant', 'rate': -91},
        ],
        # LINEAR
        [
            # ERROR
            {'result': PerformanceChange.Degradation, 'type': 'constant', 'rate': 5993},
            # IMPROVEMENT
            {'result': PerformanceChange.Optimization, 'type': 'constant', 'rate': -98},
        ],
        # QUADRATIC
        [
            # ERROR
            {'result': PerformanceChange.Degradation, 'type': 'linear',
             'rate': 966206052007956736},
            # IMPROVEMENT
            {'result': PerformanceChange.Optimization, 'type': 'linear', 'rate': -98},
        ],
    ],
    # LINEAR MODEL
    [
        # CONSTANT
        [
            # ERROR
            {'result': PerformanceChange.Degradation, 'type': 'constant', 'rate': 55},
            # IMPROVEMENT
            {'result': PerformanceChange.MaybeOptimization, 'type': 'constant', 'rate': -24},
        ],
        # LINEAR
        [
            # ERROR
            {'result': PerformanceChange.MaybeDegradation, 'type': 'linear', 'rate': 20},
            # IMPROVEMENT
            {'result': PerformanceChange.MaybeOptimization, 'type': 'linear', 'rate': -17},
        ],
        # QUADRATIC
        [
            # ERROR
            {'result': PerformanceChange.MaybeDegradation, 'type': 'linear', 'rate': 7},
            # IMPROVEMENT
            {'result': PerformanceChange.Optimization, 'type': 'linear', 'rate': -33},
        ],
    ],
    # LOGARITHMIC MODEL
    [
        # CONSTANT
        [
            # ERROR
            {'result': PerformanceChange.NoChange, 'type': '', 'rate': 24},
            # IMPROVEMENT
            {'result': PerformanceChange.NoChange, 'type': '', 'rate': -19},
        ],
        # LINEAR
        [
            # ERROR
            {'result': PerformanceChange.MaybeDegradation, 'type': 'linear', 'rate': 20},
            # IMPROVEMENT
            {'result': PerformanceChange.MaybeOptimization, 'type': 'linear', 'rate': -17},
        ],
        # QUADRATIC
        [
            # ERROR
            {'result': PerformanceChange.Degradation, 'type': 'linear', 'rate': 36},
            # IMPROVEMENT
            {'result': PerformanceChange.MaybeOptimization, 'type': 'linear', 'rate': 57},
        ],
    ],
    # QUADRATIC MODEL
    [
        # CONSTANT
        [
            # ERROR
            {'result': PerformanceChange.Degradation, 'type': 'constant', 'rate': 27},
            # IMPROVEMENT
            {'result': PerformanceChange.MaybeOptimization, 'type': 'constant', 'rate': -21},
        ],
        # LINEAR
        [
            # ERROR
            {'result': PerformanceChange.MaybeDegradation, 'type': 'linear', 'rate': 19},
            # IMPROVEMENT
            {'result': PerformanceChange.MaybeOptimization, 'type': 'linear', 'rate': -16},
        ],
        # QUADRATIC
        [
            # ERROR
            {'result': PerformanceChange.Degradation, 'type': 'linear', 'rate': 43},
            # IMPROVEMENT
            {'result': PerformanceChange.Optimization, 'type': 'linear', 'rate': -28},
        ],
    ],
    # POWER MODEL
    [
        # CONSTANT
        [
            # ERROR
            {'result': PerformanceChange.Degradation, 'type': 'constant', 'rate': 5219},
            # IMPROVEMENT
            {'result': PerformanceChange.Optimization, 'type': 'constant', 'rate': -98},
        ],
        # LINEAR
        [
            # ERROR
            {'result': PerformanceChange.NoChange, 'type': '', 'rate': -1.0},
            # IMPROVEMENT
            {'result': PerformanceChange.NoChange, 'type': '', 'rate': 1.0},
        ],
        # QUADRATIC
        [
            # ERROR
            {'result': PerformanceChange.Optimization, 'type': 'linear', 'rate': -99},
            # IMPROVEMENT
            {'result': PerformanceChange.Degradation, 'type': 'linear', 'rate': 14016},
        ],
    ],
    # EXPONENTIAL MODEL
    [
        # CONSTANT
        [
            # ERROR
            {'result': PerformanceChange.Degradation, 'type': 'constant', 'rate': 38},
            # IMPROVEMENT
            {'result': PerformanceChange.MaybeOptimization, 'type': 'constant', 'rate': -24},
        ],
        # LINEAR
        [
            # ERROR
            {'result': PerformanceChange.MaybeDegradation, 'type': 'linear', 'rate': 21},
            # IMPROVEMENT
            {'result': PerformanceChange.MaybeOptimization, 'type': 'linear', 'rate': -18},
        ],
        # QUADRATIC
        [
            # ERROR
            {'result': PerformanceChange.Degradation, 'type': 'linear', 'rate': 44},
            # IMPROVEMENT
            {'result': PerformanceChange.Optimization, 'type': 'linear', 'rate': -29},
        ],
    ],
]

_LREG_EXPECTED_RESULTS = [
    # CONSTANT MODEL
    [

        # CONSTANT
        _PREG_EXPECTED_RESULTS[0][0],
        # LINEAR
        [
            # ERROR
            {'result': PerformanceChange.Degradation, 'type': 'linear', 'rate': 5993},
            # IMPROVEMENT
            {'result': PerformanceChange.Optimization, 'type': 'linear', 'rate': -98},
        ],
        # QUADRATIC
        _PREG_EXPECTED_RESULTS[0][2],
    ],
    # LINEAR MODEL
    _PREG_EXPECTED_RESULTS[1],
    # LOGARITHMIC MODEL
    _PREG_EXPECTED_RESULTS[2],
    # QUADRATIC MODEL
    _PREG_EXPECTED_RESULTS[3],
    # POWER MODEL
    [
        # CONSTANT
        [
            # ERROR
            {'result': PerformanceChange.Degradation, 'type': 'linear', 'rate': 5219},
            # IMPROVEMENT
            {'result': PerformanceChange.Optimization, 'type': 'linear', 'rate': -98},
        ],
        # LINEAR
        _PREG_EXPECTED_RESULTS[4][1],
        # QUADRATIC
        _PREG_EXPECTED_RESULTS[4][2],
    ],
    # EXPONENTIAL MODEL
    [
        # CONSTANT
        [
            # ERROR
            {'result': PerformanceChange.Degradation, 'type': 'linear', 'rate': 38},
            # IMPROVEMENT
            {'result': PerformanceChange.MaybeOptimization, 'type': 'linear', 'rate': -24},
        ],
        # LINEAR
        _PREG_EXPECTED_RESULTS[5][1],
        # QUADRATIC
        _PREG_EXPECTED_RESULTS[5][2],

    ],
]

EXPECTED_RESULTS = [
    {'results': _PREG_EXPECTED_RESULTS, 'function': preg.polynomial_regression},
    {'results': _LREG_EXPECTED_RESULTS, 'function': lreg.linear_regression}
]
