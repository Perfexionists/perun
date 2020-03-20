import numpy as np

import perun.check.integral_comparison as int_cmp
import perun.check.linear_regression as lreg
import perun.check.local_statistics as loc_stat
import perun.check.polynomial_regression as preg
from perun.utils.structs import DegradationInfo
from perun.utils.structs import PerformanceChange as pc


_PREG_EXPECTED_RESULTS = [
    # CONSTANT MODEL
    [
        # CONSTANT
        [
            # ERROR 
            {'result': pc.Degradation, 'type': 'constant', 'rate': 999},
            # IMPROVEMENT
            {'result': pc.Optimization, 'type': 'constant', 'rate': -91},
        ],
        # LINEAR
        [
            # ERROR
            {'result': pc.Degradation, 'type': 'constant', 'rate': 5993},
            # IMPROVEMENT
            {'result': pc.Optimization, 'type': 'constant', 'rate': -98},
        ],
        # QUADRATIC
        [
            # ERROR
            {'result': pc.Degradation, 'type': 'linear',
             'rate': 966206052007956736},
            # IMPROVEMENT
            {'result': pc.Optimization, 'type': 'linear', 'rate': -98},
        ],
    ],
    # LINEAR MODEL
    [
        # CONSTANT
        [
            # ERROR
            {'result': pc.Degradation, 'type': 'constant', 'rate': 55},
            # IMPROVEMENT
            {'result': pc.MaybeOptimization, 'type': 'constant', 'rate': -24},
        ],
        # LINEAR
        [
            # ERROR
            {'result': pc.MaybeDegradation, 'type': 'linear', 'rate': 20},
            # IMPROVEMENT
            {'result': pc.MaybeOptimization, 'type': 'linear', 'rate': -17},
        ],
        # QUADRATIC
        [
            # ERROR
            {'result': pc.MaybeDegradation, 'type': 'linear', 'rate': 7},
            # IMPROVEMENT
            {'result': pc.Optimization, 'type': 'linear', 'rate': -33},
        ],
    ],
    # LOGARITHMIC MODEL
    [
        # CONSTANT
        [
            # ERROR
            {'result': pc.NoChange, 'type': '', 'rate': 24},
            # IMPROVEMENT
            {'result': pc.NoChange, 'type': '', 'rate': -19},
        ],
        # LINEAR
        [
            # ERROR
            {'result': pc.MaybeDegradation, 'type': 'linear', 'rate': 20},
            # IMPROVEMENT
            {'result': pc.MaybeOptimization, 'type': 'linear', 'rate': -17},
        ],
        # QUADRATIC
        [
            # ERROR
            {'result': pc.Degradation, 'type': 'linear', 'rate': 36},
            # IMPROVEMENT
            {'result': pc.MaybeOptimization, 'type': 'linear', 'rate': 57},
        ],
    ],
    # QUADRATIC MODEL
    [
        # CONSTANT
        [
            # ERROR
            {'result': pc.Degradation, 'type': 'constant', 'rate': 27},
            # IMPROVEMENT
            {'result': pc.MaybeOptimization, 'type': 'constant', 'rate': -21},
        ],
        # LINEAR
        [
            # ERROR
            {'result': pc.MaybeDegradation, 'type': 'linear', 'rate': 19},
            # IMPROVEMENT
            {'result': pc.MaybeOptimization, 'type': 'linear', 'rate': -16},
        ],
        # QUADRATIC
        [
            # ERROR
            {'result': pc.Degradation, 'type': 'linear', 'rate': 43},
            # IMPROVEMENT
            {'result': pc.Optimization, 'type': 'linear', 'rate': -28},
        ],
    ],
    # POWER MODEL
    [
        # CONSTANT
        [
            # ERROR
            {'result': pc.Degradation, 'type': 'constant', 'rate': 5219},
            # IMPROVEMENT
            {'result': pc.Optimization, 'type': 'constant', 'rate': -98},
        ],
        # LINEAR
        [
            # ERROR
            {'result': pc.NoChange, 'type': '', 'rate': -1.0},
            # IMPROVEMENT
            {'result': pc.NoChange, 'type': '', 'rate': 1.0},
        ],
        # QUADRATIC
        [
            # ERROR
            {'result': pc.Optimization, 'type': 'linear', 'rate': -99},
            # IMPROVEMENT
            {'result': pc.Degradation, 'type': 'linear', 'rate': 14016},
        ],
    ],
    # EXPONENTIAL MODEL
    [
        # CONSTANT
        [
            # ERROR
            {'result': pc.Degradation, 'type': 'constant', 'rate': 38},
            # IMPROVEMENT
            {'result': pc.MaybeOptimization, 'type': 'constant', 'rate': -24},
        ],
        # LINEAR
        [
            # ERROR
            {'result': pc.MaybeDegradation, 'type': 'linear', 'rate': 21},
            # IMPROVEMENT
            {'result': pc.MaybeOptimization, 'type': 'linear', 'rate': -18},
        ],
        # QUADRATIC
        [
            # ERROR
            {'result': pc.Degradation, 'type': 'linear', 'rate': 44},
            # IMPROVEMENT
            {'result': pc.Optimization, 'type': 'linear', 'rate': -29},
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
            {'result': pc.Degradation, 'type': 'linear', 'rate': 5993},
            # IMPROVEMENT
            {'result': pc.Optimization, 'type': 'linear', 'rate': -98},
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
            {'result': pc.Degradation, 'type': 'linear', 'rate': 5219},
            # IMPROVEMENT
            {'result': pc.Optimization, 'type': 'linear', 'rate': -98},
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
            {'result': pc.Degradation, 'type': 'linear', 'rate': 38},
            # IMPROVEMENT
            {'result': pc.MaybeOptimization, 'type': 'linear', 'rate': -24},
        ],
        # LINEAR
        _PREG_EXPECTED_RESULTS[5][1],
        # QUADRATIC
        _PREG_EXPECTED_RESULTS[5][2],

    ],
]

INTEGRAL_COMPARISON_RESULTS = [
    DegradationInfo(
        res=pc.MaybeOptimization, loc='alloc', fb='constant', tt='constant', rd=-0.18
    ),
    DegradationInfo(
        res=pc.MaybeDegradation, loc='alloc', fb='regressogram', tt='regressogram', rd=0.16
    ),
    DegradationInfo(
        res=pc.Degradation, loc='ga_grow', fb='constant', tt='constant', rd=1210.03
    ),
    DegradationInfo(
        res=pc.Degradation, loc='ga_init2', fb='quadratic', tt='quadratic', rd=2.33
    ),
    DegradationInfo(
        res=pc.Degradation, loc='skipwhite', fb='constant', tt='constant', rd=0.30
    ),
    DegradationInfo(
        res=pc.Degradation, loc='skipwhite', fb='moving_average', tt='moving_average', rd=0.30
    ),
    DegradationInfo(
        res=pc.Degradation, loc='skipwhite', fb='regressogram', tt='regressogram', rd=0.30
    ),
    DegradationInfo(
        res=pc.Degradation, loc='test_for_current', fb='constant', tt='constant', rd=0.34
    ),
    DegradationInfo(
        res=pc.Degradation, loc='test_for_current',
        fb='moving_average', tt='moving_average', rd=0.35
    ),
    DegradationInfo(
        res=pc.MaybeDegradation, loc='vim_isblankline', fb='constant', tt='constant', rd=0.22
    ),
    DegradationInfo(
        res=pc.MaybeDegradation, loc='vim_isblankline',
        fb='moving_average', tt='moving_average', rd=0.22
    ),
    DegradationInfo(
        res=pc.MaybeDegradation, loc='vim_isblankline',
        fb='regressogram', tt='regressogram', rd=0.22
    ),
]

LOCAL_STATISTICS_RESULTS = [
    DegradationInfo(
        res=pc.MaybeOptimization, loc='alloc', fb='constant', tt='constant', rd=-0.16,
        pi=[(pc.MaybeOptimization, -0.16, 5.45, 5.45)]
    ),
    DegradationInfo(
        res=pc.MaybeDegradation, loc='alloc', fb='regressogram', tt='regressogram', rd=0.11,
        pi=[(pc.MaybeDegradation, 0.11, 0.0, 275.0)]
    ),
    DegradationInfo(
        res=pc.Degradation, loc='ga_grow', fb='constant', tt='constant', rd=1052.44,
        pi=[(pc.Degradation, 1052.44, 2.61, 2.61)]
    ),
    DegradationInfo(
        res=pc.Degradation, loc='ga_init2', fb='quadratic', tt='quadratic', rd=2.27,
        pi=[(pc.Degradation, 2.27, 2.71, 2.12)]
    ),
    DegradationInfo(
        res=pc.MaybeDegradation, loc='parse_tag_line', fb='moving_average', tt='moving_average',
        rd=0.14, pi=[(pc.MaybeDegradation, 0.12, 235062.0, 391764.0)]
    ),
    DegradationInfo(
        res=pc.MaybeDegradation, loc='parse_tag_line', fb='regressogram', tt='regressogram',
        rd=0.1, pi=[(pc.MaybeDegradation, 0.13, 235044.16, 391722.86)]
    ),
    DegradationInfo(
        res=pc.Degradation, loc='skipwhite', fb='moving_average', tt='moving_average', rd=0.29,
        pi=[
            (pc.MaybeDegradation, 0.14, 116904.0, 233804.0),
            (pc.Degradation, 0.86, 233808.0, 253288.0),
            (pc.MaybeDegradation, 0.36, 253292.0, 272772.0),
            (pc.Degradation, 0.59, 272776.0, 389720.0),
        ]
    ),
    DegradationInfo(
        res=pc.Degradation, loc='skipwhite', fb='regressogram', tt='regressogram', rd=0.3,
        pi=[
            (pc.MaybeDegradation, 0.12, 116826.38, 136279.87),
            (pc.Degradation, 0.2, 175239.57, 214164.12),
            (pc.MaybeDegradation, 0.18, 214181.69, 233635.18),
            (pc.Degradation, 0.62, 233652.75, 389720.0),
        ]
    ),
    DegradationInfo(
        res=pc.Degradation, loc='test_for_current', fb='moving_average', tt='moving_average',
        rd=0.34, pi=[
            (pc.MaybeDegradation, 0.12, 26648.0, 33308.0),
            (pc.Degradation, 0.24, 33310.0, 39970.0),
            (pc.MaybeDegradation, 0.17, 39972.0, 46632.0),
            (pc.Degradation, 0.46, 46634.0, 133256.0),
        ]
    ),
    DegradationInfo(
        res=pc.MaybeDegradation, loc='test_for_static', fb='moving_average', tt='moving_average',
        rd=0.1, pi=[
            (pc.MaybeDegradation, 0.12, 53292.0, 133227.0),
            (pc.MaybeOptimization, -0.12, 173199.0, 186519.0),
            (pc.MaybeDegradation, 0.29, 266460.0, 266514.0),
        ]
    ),
    DegradationInfo(
        res=pc.MaybeDegradation, loc='vim_isblankline', fb='moving_average', tt='moving_average',
        rd=0.2, pi=[
            (pc.MaybeDegradation, 0.12, 175104.0, 214012.0),
            (pc.Degradation, 0.37, 214016.0, 389140.0),
        ]
    ),
    DegradationInfo(
        res=pc.MaybeDegradation, loc='vim_isblankline', fb='regressogram', tt='regressogram',
        rd=0.21, pi=[
            (pc.MaybeDegradation, 0.15, 175057.65, 233392.63),
            (pc.Degradation, 0.43, 233410.2, 389140.0),
        ]
    ),
    DegradationInfo(
        res=pc.Degradation, loc='vim_regexec', fb='moving_average', tt='moving_average',
        rd=0.27, pi=[
            (pc.MaybeDegradation, 0.1, 233424.0, 369584.0),
            (pc.Degradation, 0.22, 389040.0, 389104.0)
        ]
    ),
    DegradationInfo(
        res=pc.MaybeDegradation, loc='vim_regexec', fb='regressogram', tt='regressogram',
        rd=0.14, pi=[(pc.MaybeDegradation, 0.12, 233409.69, 389104.0)]
    ),
]

PARAM_EXPECTED_RESULTS = [
    {'results': _PREG_EXPECTED_RESULTS, 'function': preg.polynomial_regression},
    {'results': _LREG_EXPECTED_RESULTS, 'function': lreg.linear_regression}
]

NONPARAM_EXPECTED_RESULTS = [
    {'results': INTEGRAL_COMPARISON_RESULTS, 'function': int_cmp.integral_comparison},
    {'results': LOCAL_STATISTICS_RESULTS, 'function': loc_stat.local_statistics}
]
