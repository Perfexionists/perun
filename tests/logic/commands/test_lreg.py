"""Basic tests for detection method which using linear regression.

Tests whether the change is correctly detected and classified. All types of models 
are tested to the three types of changes.
"""

import os

import perun.profile.factory as factory
import perun.check as check
import perun.check.average_amount_threshold as aat
import perun.check.best_model_order_equality as bmoe
import perun.check.linear_regression as lreg
import perun.check.fast_check as fast

def test_degradation_with_method(pcs_with_degradations, capsys):
    """Set of basic tests for testing degradation between profiles

    Expects correct behaviour
    """
    
    # loading the profiles
    pool_path = os.path.join(os.path.split(__file__)[0], 'degradation_profiles')
    profiles = [
        factory.load_profile_from_file(os.path.join(pool_path, 'const1.perf'), True),
        factory.load_profile_from_file(os.path.join(pool_path, 'const2.perf'), True),
        factory.load_profile_from_file(os.path.join(pool_path, 'const3.perf'), True),
        factory.load_profile_from_file(os.path.join(pool_path, 'const4.perf'), True),
        factory.load_profile_from_file(os.path.join(pool_path, 'lin1.perf'), True),
        factory.load_profile_from_file(os.path.join(pool_path, 'lin2.perf'), True),
        factory.load_profile_from_file(os.path.join(pool_path, 'lin3.perf'), True),
        factory.load_profile_from_file(os.path.join(pool_path, 'lin4.perf'), True),
        factory.load_profile_from_file(os.path.join(pool_path, 'log1.perf'), True),
        factory.load_profile_from_file(os.path.join(pool_path, 'log2.perf'), True),
        factory.load_profile_from_file(os.path.join(pool_path, 'log3.perf'), True),
        factory.load_profile_from_file(os.path.join(pool_path, 'log4.perf'), True),       
        factory.load_profile_from_file(os.path.join(pool_path, 'quad1.perf'), True),
        factory.load_profile_from_file(os.path.join(pool_path, 'quad2.perf'), True),
        factory.load_profile_from_file(os.path.join(pool_path, 'quad3.perf'), True),
        factory.load_profile_from_file(os.path.join(pool_path, 'quad4.perf'), True),
        factory.load_profile_from_file(os.path.join(pool_path, 'pow1.perf'), True),
        factory.load_profile_from_file(os.path.join(pool_path, 'pow2.perf'), True),
        factory.load_profile_from_file(os.path.join(pool_path, 'pow3.perf'), True),
        factory.load_profile_from_file(os.path.join(pool_path, 'pow4.perf'), True),        
        factory.load_profile_from_file(os.path.join(pool_path, 'exp1.perf'), True),
        factory.load_profile_from_file(os.path.join(pool_path, 'exp2.perf'), True),
        factory.load_profile_from_file(os.path.join(pool_path, 'exp3.perf'), True),
        factory.load_profile_from_file(os.path.join(pool_path, 'exp4.perf'), True)
    ]

    # CONSTANT MODEL -------------------------------------------- CONSTANT MODEL

    # CONSTANT ERROR
    result = list(lreg.linear_regression(profiles[0], profiles[1]))
    assert check.PerformanceChange.Degradation in [r.result for r in result]
    assert 'CONSTANT ERROR' in [r.type for r in result] #
    assert 999 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # CONSTANT IMPROVEMENT
    result = list(lreg.linear_regression(profiles[1], profiles[0]))
    assert check.PerformanceChange.Optimization in [r.result for r in result]
    assert 'CONSTANT IMPROVEMENT' in [r.type for r in result] #
    assert -91 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # LINEAR ERROR
    result = list(lreg.linear_regression(profiles[0], profiles[2]))
    assert check.PerformanceChange.Degradation in [r.result for r in result]
    assert 'LINEAR ERROR' in [r.type for r in result] #
    assert 5993 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # LINEAR IMPROVEMENT
    result = list(lreg.linear_regression(profiles[2], profiles[0]))
    assert check.PerformanceChange.Optimization in [r.result for r in result]
    assert 'LINEAR IMPROVEMENT' in [r.type for r in result] #
    assert -98 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # QUADRATIC ERROR
    result = list(lreg.linear_regression(profiles[0], profiles[3]))
    assert check.PerformanceChange.Degradation in [r.result for r in result]
    assert 'LINEAR ERROR' in [r.type for r in result] #
    assert 966206052007956736 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # QUADRATIC IMPROVEMENT
    result = list(lreg.linear_regression(profiles[3], profiles[0]))
    assert check.PerformanceChange.Optimization in [r.result for r in result]
    assert 'LINEAR IMPROVEMENT' in [r.type for r in result] #
    assert -98 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # LINEAR MODEL -------------------------------------------- LINEAR MODEL

    # CONSTANT ERROR
    result = list(lreg.linear_regression(profiles[4], profiles[5]))
    assert check.PerformanceChange.Degradation in [r.result for r in result]
    assert 'CONSTANT ERROR' in [r.type for r in result] #
    assert 55 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # CONSTANT IMPROVEMENT
    result = list(lreg.linear_regression(profiles[5], profiles[4]))
    assert check.PerformanceChange.MaybeOptimization in [r.result for r in result]
    assert 'CONSTANT IMPROVEMENT' in [r.type for r in result] #
    assert -24 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # LINEAR ERROR
    result = list(lreg.linear_regression(profiles[4], profiles[6]))
    assert check.PerformanceChange.MaybeDegradation in [r.result for r in result]
    assert 'LINEAR ERROR' in [r.type for r in result] #
    assert 20 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # LINEAR IMPROVEMENT
    result = list(lreg.linear_regression(profiles[6], profiles[4]))
    assert check.PerformanceChange.MaybeOptimization in [r.result for r in result]
    assert 'LINEAR IMPROVEMENT' in [r.type for r in result] #
    assert -17 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # QUADRATIC ERROR
    result = list(lreg.linear_regression(profiles[4], profiles[7]))
    assert check.PerformanceChange.MaybeDegradation in [r.result for r in result]
    assert 'LINEAR ERROR' in [r.type for r in result] #
    assert 7 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # QUADRATIC IMPROVEMENT
    result = list(lreg.linear_regression(profiles[7], profiles[4]))
    assert check.PerformanceChange.Optimization in [r.result for r in result]
    assert 'LINEAR IMPROVEMENT' in [r.type for r in result] #
    assert -33 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # LOGARITHMIC MODEL -------------------------------------------- LOGARITHMIC MODEL

    # CONSTANT ERROR
    result = list(lreg.linear_regression(profiles[8], profiles[9]))
    assert check.PerformanceChange.NoChange in [r.result for r in result]

    # CONSTANT IMPROVEMENT
    result = list(lreg.linear_regression(profiles[9], profiles[8]))
    assert check.PerformanceChange.NoChange in [r.result for r in result]

    # LINEAR ERROR
    result = list(lreg.linear_regression(profiles[8], profiles[10]))
    assert check.PerformanceChange.MaybeDegradation in [r.result for r in result]
    assert 'LINEAR ERROR' in [r.type for r in result] #
    assert 20 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # LINEAR IMPROVEMENT
    result = list(lreg.linear_regression(profiles[10], profiles[8]))
    assert check.PerformanceChange.MaybeOptimization in [r.result for r in result]
    assert 'LINEAR IMPROVEMENT' in [r.type for r in result] #
    assert -17 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # QUADRATIC ERROR
    result = list(lreg.linear_regression(profiles[8], profiles[11]))
    assert check.PerformanceChange.Degradation in [r.result for r in result]
    assert 'LINEAR ERROR' in [r.type for r in result] #
    assert 36 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # QUADRATIC IMPROVEMENT
    result = list(lreg.linear_regression(profiles[11], profiles[8]))
    assert check.PerformanceChange.MaybeOptimization in [r.result for r in result]
    assert 'LINEAR IMPROVEMENT' in [r.type for r in result] #
    assert 57 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # QUADRATIC MODEL -------------------------------------------- QUADRATIC MODEL

    # CONSTANT ERROR
    result = list(lreg.linear_regression(profiles[12], profiles[13]))
    assert check.PerformanceChange.Degradation in [r.result for r in result]
    assert 'CONSTANT ERROR' in [r.type for r in result] #
    assert 27 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # CONSTANT IMPROVEMENT
    result = list(lreg.linear_regression(profiles[13], profiles[12]))
    assert check.PerformanceChange.MaybeOptimization in [r.result for r in result]
    assert 'CONSTANT IMPROVEMENT' in [r.type for r in result] #
    assert -21 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # LINEAR ERROR
    result = list(lreg.linear_regression(profiles[12], profiles[14]))
    assert check.PerformanceChange.MaybeDegradation in [r.result for r in result]
    assert 'LINEAR ERROR' in [r.type for r in result] #
    assert 19 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # LINEAR IMPROVEMENT
    result = list(lreg.linear_regression(profiles[14], profiles[12]))
    assert check.PerformanceChange.MaybeOptimization in [r.result for r in result]
    assert 'LINEAR IMPROVEMENT' in [r.type for r in result] #
    assert -16 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # QUADRATIC ERROR
    result = list(lreg.linear_regression(profiles[12], profiles[15]))
    assert check.PerformanceChange.Degradation in [r.result for r in result]
    assert 'LINEAR ERROR' in [r.type for r in result] #
    assert 43 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # QUADRATIC IMPROVEMENT
    result = list(lreg.linear_regression(profiles[15], profiles[12]))
    assert check.PerformanceChange.Optimization in [r.result for r in result]
    assert 'LINEAR IMPROVEMENT' in [r.type for r in result] #
    assert -28 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)
    
    # POWER MODEL -------------------------------------------- POWER MODEL

    # CONSTANT ERROR
    result = list(lreg.linear_regression(profiles[16], profiles[17]))
    assert check.PerformanceChange.Degradation in [r.result for r in result]
    assert 'LINEAR ERROR' in [r.type for r in result] #
    assert 5219 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # CONSTANT IMPROVEMENT
    result = list(lreg.linear_regression(profiles[17], profiles[16]))
    assert check.PerformanceChange.Optimization in [r.result for r in result]
    assert 'LINEAR IMPROVEMENT' in [r.type for r in result] #
    assert -98 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # LINEAR ERROR
    result = list(lreg.linear_regression(profiles[16], profiles[18]))
    assert check.PerformanceChange.NoChange in [r.result for r in result]

    # LINEAR IMPROVEMENT
    result = list(lreg.linear_regression(profiles[18], profiles[16]))
    assert check.PerformanceChange.NoChange in [r.result for r in result]

    # QUADRATIC ERROR
    result = list(lreg.linear_regression(profiles[19], profiles[16]))
    assert check.PerformanceChange.Degradation in [r.result for r in result]
    assert 'LINEAR ERROR' in [r.type for r in result] #
    assert 14016 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # QUADRATIC IMPROVEMENT
    result = list(lreg.linear_regression(profiles[16], profiles[19]))
    assert check.PerformanceChange.Optimization in [r.result for r in result]
    assert 'LINEAR IMPROVEMENT' in [r.type for r in result] #
    assert -99 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # EXPONENTIAL MODEL -------------------------------------------- EXPONENTIAL MODEL

    # CONSTANT ERROR
    result = list(lreg.linear_regression(profiles[20], profiles[21]))
    assert check.PerformanceChange.Degradation in [r.result for r in result]
    assert 'LINEAR ERROR' in [r.type for r in result] #
    assert 38 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # CONSTANT IMPROVEMENT
    result = list(lreg.linear_regression(profiles[21], profiles[20]))
    assert check.PerformanceChange.MaybeOptimization in [r.result for r in result]
    assert 'LINEAR IMPROVEMENT' in [r.type for r in result] #
    assert -24 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # LINEAR ERROR
    result = list(lreg.linear_regression(profiles[20], profiles[22]))
    assert check.PerformanceChange.MaybeDegradation in [r.result for r in result]
    assert 'LINEAR ERROR' in [r.type for r in result] #
    assert 21 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # LINEAR IMPROVEMENT
    result = list(lreg.linear_regression(profiles[22], profiles[20]))
    assert check.PerformanceChange.MaybeOptimization in [r.result for r in result]
    assert 'LINEAR IMPROVEMENT' in [r.type for r in result] #
    assert -18 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # QUADRATIC ERROR
    result = list(lreg.linear_regression(profiles[20], profiles[23]))
    assert check.PerformanceChange.Degradation in [r.result for r in result]
    assert 'LINEAR ERROR' in [r.type for r in result] #
    assert 44 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)

    # QUADRATIC IMPROVEMENT
    result = list(lreg.linear_regression(profiles[23], profiles[20]))
    assert check.PerformanceChange.Optimization in [r.result for r in result]
    assert 'LINEAR IMPROVEMENT' in [r.type for r in result] #
    assert -29 in [round(r.rate_degradation) for r in result]
    for deg in result:
        check.print_degradation_results(deg)