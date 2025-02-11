from __future__ import annotations

# Standard Imports

# Third-Party Imports

# Perun Imports
from perun.utils.structs.common_structs import DegradationInfo
from perun.utils.structs.common_structs import PerformanceChange as pc


_PREG_EXPECTED_RESULTS = [
    # CONSTANT MODEL
    [
        # CONSTANT
        [
            # ERROR
            {"result": {pc.Degradation}, "type": {"constant"}, "rate": {999}},
            # IMPROVEMENT
            {"result": {pc.Optimization}, "type": {"constant"}, "rate": {-91}},
        ],
        # LINEAR
        [
            # ERROR
            {"result": {pc.Degradation}, "type": {"constant"}, "rate": {5993}},
            # IMPROVEMENT
            {"result": {pc.Optimization}, "type": {"constant"}, "rate": {-98}},
        ],
        # QUADRATIC
        [
            # ERROR
            {
                "result": {pc.Degradation},
                "type": {"linear"},
                "rate": {966206052007956736},
            },
            # IMPROVEMENT
            {"result": {pc.Optimization}, "type": {"linear"}, "rate": {-98}},
        ],
    ],
    # LINEAR MODEL
    [
        # CONSTANT
        [
            # ERROR
            {"result": {pc.Degradation}, "type": {"constant"}, "rate": {55}},
            # IMPROVEMENT
            {"result": {pc.MaybeOptimization}, "type": {"constant"}, "rate": {-24}},
        ],
        # LINEAR
        [
            # ERROR
            # On some systems, it gets classified as constant instead of linear
            {"result": {pc.MaybeDegradation}, "type": {"linear", "constant"}, "rate": {20}},
            # IMPROVEMENT
            {"result": {pc.MaybeOptimization}, "type": {"linear", "constant"}, "rate": {-17}},
        ],
        # QUADRATIC
        [
            # ERROR
            {
                "result": {pc.MaybeDegradation},
                "type": {"linear", "constant"},
                "rate": {7},
            },
            # IMPROVEMENT
            {
                "result": {pc.Optimization},
                "type": {"linear", "constant"},
                "rate": {-33},
            },
        ],
    ],
    # LOGARITHMIC MODEL
    [
        # CONSTANT
        [
            # ERROR
            {"result": {pc.NoChange}, "type": {""}, "rate": {24}},
            # IMPROVEMENT
            {"result": {pc.NoChange}, "type": {""}, "rate": {-19}},
        ],
        # LINEAR
        [
            # ERROR
            {"result": {pc.MaybeDegradation}, "type": {"linear"}, "rate": {20}},
            # IMPROVEMENT
            {"result": {pc.MaybeOptimization}, "type": {"linear"}, "rate": {-17}},
        ],
        # QUADRATIC
        [
            # ERROR
            {"result": {pc.Degradation}, "type": {"linear"}, "rate": {36}},
            # IMPROVEMENT
            {"result": {pc.MaybeOptimization}, "type": {"linear"}, "rate": {57}},
        ],
    ],
    # QUADRATIC MODEL
    [
        # CONSTANT
        [
            # ERROR
            {"result": {pc.Degradation}, "type": {"constant"}, "rate": {27}},
            # IMPROVEMENT
            {"result": {pc.MaybeOptimization}, "type": {"constant"}, "rate": {-21}},
        ],
        # LINEAR
        [
            # ERROR
            {"result": {pc.MaybeDegradation}, "type": {"linear"}, "rate": {19}},
            # IMPROVEMENT
            {"result": {pc.MaybeOptimization}, "type": {"linear"}, "rate": {-16}},
        ],
        # QUADRATIC
        [
            # ERROR
            {"result": {pc.Degradation}, "type": {"linear"}, "rate": {43}},
            # IMPROVEMENT
            {"result": {pc.Optimization}, "type": {"linear"}, "rate": {-28}},
        ],
    ],
    # POWER MODEL
    [
        # CONSTANT
        [
            # ERROR
            {"result": {pc.Degradation}, "type": {"constant"}, "rate": {5219}},
            # IMPROVEMENT
            {"result": {pc.Optimization}, "type": {"constant"}, "rate": {-98}},
        ],
        # LINEAR
        [
            # ERROR
            {"result": {pc.NoChange}, "type": {""}, "rate": {-1.0}},
            # IMPROVEMENT
            {"result": {pc.NoChange}, "type": {""}, "rate": {1.0}},
        ],
        # QUADRATIC
        [
            # ERROR
            {"result": {pc.Optimization}, "type": {"linear"}, "rate": {-99}},
            # IMPROVEMENT
            {"result": {pc.Degradation}, "type": {"linear"}, "rate": {14016}},
        ],
    ],
    # EXPONENTIAL MODEL
    [
        # CONSTANT
        [
            # ERROR
            {"result": {pc.Degradation}, "type": {"constant"}, "rate": {38}},
            # IMPROVEMENT
            {"result": {pc.MaybeOptimization}, "type": {"constant"}, "rate": {-24}},
        ],
        # LINEAR
        [
            # ERROR
            {"result": {pc.MaybeDegradation}, "type": {"linear"}, "rate": {21}},
            # IMPROVEMENT
            {"result": {pc.MaybeOptimization}, "type": {"linear"}, "rate": {-18}},
        ],
        # QUADRATIC
        [
            # ERROR
            {"result": {pc.Degradation}, "type": {"linear"}, "rate": {44}},
            # IMPROVEMENT
            {"result": {pc.Optimization}, "type": {"linear"}, "rate": {-29}},
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
            {"result": {pc.Degradation}, "type": {"linear"}, "rate": {5993}},
            # IMPROVEMENT
            {"result": {pc.Optimization}, "type": {"linear"}, "rate": {-98}},
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
            {"result": {pc.Degradation}, "type": {"linear"}, "rate": {5219}},
            # IMPROVEMENT
            {"result": {pc.Optimization}, "type": {"linear"}, "rate": {-98}},
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
            {"result": {pc.Degradation}, "type": {"linear"}, "rate": {38}},
            # IMPROVEMENT
            {"result": {pc.MaybeOptimization}, "type": {"linear"}, "rate": {-24}},
        ],
        # LINEAR
        _PREG_EXPECTED_RESULTS[5][1],
        # QUADRATIC
        _PREG_EXPECTED_RESULTS[5][2],
    ],
]

INTEGRAL_COMPARISON_RESULTS = [
    DegradationInfo(res=pc.MaybeOptimization, loc="alloc", fb="constant", tt="constant", rd=-0.18),
    DegradationInfo(res=pc.Degradation, loc="ga_grow", fb="constant", tt="constant", rd=1210.03),
    DegradationInfo(res=pc.Degradation, loc="ga_init2", fb="quadratic", tt="quadratic", rd=2.33),
    DegradationInfo(res=pc.Degradation, loc="skipwhite", fb="constant", tt="constant", rd=0.30),
    DegradationInfo(
        res=pc.Degradation,
        loc="test_for_current",
        fb="constant",
        tt="constant",
        rd=0.34,
    ),
    DegradationInfo(
        res=pc.Degradation,
        loc="test_for_static",
        fb="moving_average",
        tt="moving_average",
        rd=1.22,
    ),
    DegradationInfo(
        res=pc.MaybeDegradation,
        loc="test_for_static",
        fb="regressogram",
        tt="regressogram",
        rd=0.11,
    ),
    DegradationInfo(
        res=pc.MaybeDegradation,
        loc="vim_isblankline",
        fb="constant",
        tt="constant",
        rd=0.22,
    ),
    DegradationInfo(
        res=pc.Degradation,
        loc="vim_regexec",
        fb="regressogram",
        tt="regressogram",
        rd=0.27,
    ),
]

LOCAL_STATISTICS_RESULTS = [
    DegradationInfo(
        res=pc.MaybeOptimization,
        loc="alloc",
        fb="constant",
        tt="constant",
        rd=-0.16,
        pi=[(pc.MaybeOptimization, -0.16, 5.45, 5.45)],
    ),
    DegradationInfo(
        res=pc.Degradation,
        loc="ga_grow",
        fb="constant",
        tt="constant",
        rd=1052.44,
        pi=[(pc.Degradation, 1052.44, 2.61, 2.61)],
    ),
    DegradationInfo(
        res=pc.Degradation,
        loc="ga_init2",
        fb="quadratic",
        tt="quadratic",
        rd=2.27,
        pi=[(pc.Degradation, 2.27, 2.71, 2.12)],
    ),
    DegradationInfo(
        res=pc.Degradation,
        loc="test_for_static",
        fb="moving_average",
        tt="moving_average",
        rd=0.82,
        pi=[
            (pc.Degradation, 20.46, 152293.71, 157732.78),
        ],
    ),
    DegradationInfo(
        res=pc.MaybeDegradation,
        loc="test_for_static",
        fb="regressogram",
        tt="regressogram",
        rd=0.15,
        pi=[
            (pc.Degradation, 3.52, 21756.24, 27195.31),
        ],
    ),
    DegradationInfo(
        res=pc.Degradation,
        loc="vim_regexec",
        fb="regressogram",
        tt="regressogram",
        rd=0.41,
        pi=[
            (pc.MaybeDegradation, 0.22, 238226.94, 246167.84),
            (pc.Degradation, 10.13, 301754.12, 309695.02),
            (pc.MaybeOptimization, -0.16, 365281.31, 373222.2),
            (pc.MaybeDegradation, 0.18, 381163.1, 389104.0),
        ],
    ),
]

PARAM_EXPECTED_RESULTS = [
    {"results": _PREG_EXPECTED_RESULTS, "function": "polynomial_regression"},
    {"results": _LREG_EXPECTED_RESULTS, "function": "linear_regression"},
]

NONPARAM_EXPECTED_RESULTS = [
    {"results": INTEGRAL_COMPARISON_RESULTS, "function": "integral_comparison"},
    {"results": LOCAL_STATISTICS_RESULTS, "function": "local_statistics"},
]
