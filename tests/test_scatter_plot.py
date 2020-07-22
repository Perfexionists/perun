""" Basic tests for scatter plot visualization """

import os
import operator

from click.testing import CliRunner

import perun.cli as cli
import perun.view.scatter.factory as scatter

import tests.testing.asserts as asserts

__author__ = 'Jiri Pavela'


def test_scatter_plot_regression_models(postprocess_profiles):
    """ Test the scatter plot on complexity profiles with regression models.

    Expecting no errors or exceptions.
    """
    # Filter the postprocess profiles with regression models
    tested_profiles = [p for p in list(postprocess_profiles) if 'computation' in p[0]]
    assert len(tested_profiles) == 5

    for profile in tested_profiles:
        # Create graphs from one profile
        graphs = scatter.create_from_params(profile[1], 'amount', 'structure-unit-size',
                                            'structure-unit-size', 'amount [us]',
                                            "Plot of 'amount' per 'structure-unit-size'")
        results = list(map(operator.itemgetter(0), graphs))

        # Check if scatter plot generated expected amount of graphs for each profile
        if ('full_computation.perf' in profile[0] or 'initial_guess_computation.perf' in profile[0]
                or 'iterative_computation.perf' in profile[0]):
            assert len(results) == 2
        elif 'bisection_computation.perf' in profile[0]:
            assert len(results) == 4
        elif 'interval_computation.perf' in profile[0]:
            assert len(results) == 6


def test_scatter_plot_non_param_methods(postprocess_profiles):
    """ Test the scatter plot on complexity profiles with regressogram.

    Expecting no errors or exceptions.
    """
    # Filter the postprocess profiles with regressogram
    tested_profiles = [p for p in list(postprocess_profiles) if 'rg_ma_kr' in p[0]]
    assert len(tested_profiles) == 3

    for profile in tested_profiles:
        # Create graphs from one profile
        graphs = scatter.create_from_params(profile[1], 'amount', 'structure-unit-size',
                                            'structure-unit-size', 'amount [us]',
                                            'Plot of "amount" per "structure-unit-size"')
        results = list(map(operator.itemgetter(0), graphs))

        # Check if scatter plot generated expected amount of graphs for each profile
        if 'exp_datapoints_rg_ma_kr.perf' in profile[0] or \
                'pow_datapoints_rg_ma_kr.perf' in profile[0]:
            assert len(results) == 3
        elif 'lin_datapoints_rg_ma_kr.perf' in profile[0]:
            assert len(results) == 2


def test_scatter_plot_no_models(full_profiles):
    """ Test the scatter plot on complexity profiles without models.

    Expecting no errors or exceptions.
    """
    # Filter the full profiles, only the complexity one is needed
    complexity_prof = [p for p in list(full_profiles) if 'prof-2-complexity-2017' in p[0]]
    assert len(complexity_prof) == 1
    profile = complexity_prof[0]

    # Create graphs from one profile without models
    graphs = scatter.create_from_params(profile[1], 'amount', 'structure-unit-size',
                                        'structure-unit-size', 'amount [us]',
                                        "Plot of 'amount' per 'structure-unit-size'")
    results = list(map(operator.itemgetter(0), graphs))

    # Graphs for two functions should be generated
    assert len(results) == 2


def test_scatter_plot_cli(pcs_full, postprocess_profiles):
    """ Test creating bokeh scatter plot from the cli

    Expecting no errors and created scatter_plot_result0.html, scatter_plot_result1.html files
    """
    # Filter the postprocess profiles, test only on the full computation
    tested_profiles = [p for p in list(postprocess_profiles) if 'full_computation' in p[0]]
    assert len(tested_profiles) == 1
    profile = tested_profiles[0]

    # Run the cli on the given profile
    runner = CliRunner()
    result = runner.invoke(cli.show, [profile[0], 'scatter', '--of=amount',
                                      '--per=structure-unit-size', '--filename=scatter',
                                      '-xl=structure-unit-size', '-yl=amount [us]'])

    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert 'scatter_SLList_insert(SLList_,_int).html' in os.listdir(os.getcwd())
    assert 'scatter_SLListcls__Insert(int).html' in os.listdir(os.getcwd())


def test_scatter_plot_cli_errors(pcs_full, postprocess_profiles):
    """ Test creating bokeh scatter plot from the cli with invalid inputs

    Expecting to fail all commands and not create any graph files.
    """
    # Filter the postprocess profiles, test only on the full computation
    tested_profiles = [p for p in list(postprocess_profiles) if 'full_computation' in p[0]]
    assert len(tested_profiles) == 1
    profile = tested_profiles[0]

    runner = CliRunner()
    # Try invalid view argument
    result = runner.invoke(cli.show, [profile[0], 'scatterr', '--of=amount',
                                      '--per=structure-unit-size'])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, 'No such command' in result.output)
    asserts.predicate_from_cli(result, 'scatterr' in result.output)

    # Try invalid --of value
    result = runner.invoke(cli.show, [profile[0], 'scatter', '--of=amou',
                                      '--per=structure-unit-size'])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, 'invalid choice: amou' in result.output)

    # Try invalid --per value
    result = runner.invoke(cli.show, [profile[0], 'scatter', '--of=amount',
                                      '--per=struct'])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, 'invalid choice: struct' in result.output)
