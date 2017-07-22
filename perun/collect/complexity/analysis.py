"""Wrapper for regression analysis and visualization of collected data for easier usage.

The module consists of wrapper function for each implemented regression method. Every functions
takes care of analysis and visualisation and thus connecting the various modules.

"""

import perun.collect.complexity.regression_analysis.methods as reg
from perun.collect.complexity.regression_analysis.regression_models import Models
import perun.collect.complexity.visualizer.interface as Ivisualization
import perun.collect.complexity.visualizer.utils as vis_utils

# The color used for each model plotting
_model_colors = {
    'linear': 'GreenYellow',
    'logarithmic': 'Aqua',
    'power': 'DarkMagenta',
    'exponential': 'LimeGreen',
    'quadratic': 'MediumBlue'
}

_scatter_colors = [
    {'color': '#ff3c1a', 'line_color': 'red'},
    {'color': 'LightBlue', 'line_color': 'Blue'},
    {'color': 'Yellow', 'line_color': 'Orange'},
    {'color': 'LightGreen', 'line_color': 'Green'}
]


def full_computation(data_gen, model_list, profile_filename):
    """The full computation method wrapper.

    Arguments:
        data_gen(iterable): the generator with collected data (data provider generators)
        model_list(list of Model enum values): the list of models to compute
        profile_filename(str): the base name for output visualisation file (will be further suffixed with specifiers)
    Returns:
        None

    """

    chunk_count = 0
    # Get the profiling data for each function
    for chunk in data_gen:
        chunk_count += 1
        # Set the title and output filename
        plot_filename = "{0}_func{1}_full_plot.html".format(profile_filename, chunk_count)
        plot_title = "{0} performance".format(chunk[2])

        # Create plotting figure and scatter plot of profiling data
        Ivisualization.set_figure(filename=plot_filename, title=plot_title)
        Ivisualization.plot_scatter(x=chunk[0], y=chunk[1])

        # Compute every requested regression model
        for result in reg.full_computation(chunk[0], chunk[1], model_list):
            # Create it's legend and plot the computed model
            legend = "{0}: {1}".format(
                result['model'], vis_utils.create_generic_legend(result['coeffs'], result['r_square']))
            Ivisualization.plot_model(x=result['plot_x'], y=result['plot_y'],
                                      legend=legend, color=_model_colors[result['model']])
        # Show the final figure
        Ivisualization.show_figure()


def iterative_computation_interactive(data_gen, model_list, parts, profile_filename):
    """The iterative computation method wrapper. Each step is plotted and saved - thus the interactivity.

    Arguments:
        data_gen(iterable): the generator with collected data (data provider generators)
        model_list(list of Model enum values): the list of models to compute
        parts(int): the number of parts to split the computation into
        profile_filename(str): the base name for output visualisation file (will be further suffixed with specifiers)
    Returns:
        None

    """

    chunk_count = 0
    # Get the profiling data for each function
    for chunk in data_gen:
        chunk_count += 1
        iter_count = 0
        # Get the next computation step
        for result in reg.iterative_computation(chunk[0], chunk[1], parts, model_list):
            iter_count += 1

            # Create the output filename and plot title
            plot_filename = "{0}_func{1}_iter{2}_plot.html".format(profile_filename, chunk_count, iter_count)
            plot_title = "{0} iteration {1} performance".format(chunk[2], iter_count)

            # Create the figure and scatter plot of profiling data
            Ivisualization.set_figure(filename=plot_filename, title=plot_title)
            Ivisualization.plot_scatter(x=result['x'][:result['len']], y=result['y'][:result['len']])

            # Create the legend and plot the model results
            legend = "{0}: {1}".format(
                result['model'], vis_utils.create_generic_legend(result['coeffs'], result['r_square']))
            Ivisualization.plot_model(x=result['plot_x'], y=result['plot_y'],
                                      legend=legend, color=_model_colors[result['model']])

            # Save and show the completed step
            Ivisualization.show_figure()


def iterative_computation(data_gen, model_list, parts, profile_filename):
    """The iterative computation method wrapper without interactivity, only the final best fitting model is shown.

    Arguments:
        data_gen(iterable): the generator with collected data (data provider generators)
        model_list(list of Model enum values): the list of models to compute
        parts(int): the number of parts to split the computation into
        profile_filename(str): the base name for output visualisation file (will be further suffixed with specifiers)
    Returns:
        None

    """

    chunk_count = 0
    # Get the profiling data for each function
    for chunk in data_gen:
        chunk_count += 1

        # Create the filename and plot title
        plot_filename = "{0}_func{1}_iter_plot.html".format(profile_filename, chunk_count)
        plot_title = "{0} performance".format(chunk[2])

        # Create the figure and scatter plot for profiling data
        Ivisualization.set_figure(filename=plot_filename, title=plot_title)
        Ivisualization.plot_scatter(x=chunk[0], y=chunk[1])

        # Do all the iterations for one function and show only the last one
        for result in reg.iterative_computation(chunk[0], chunk[1], parts, model_list):
            pass

        # Create legend and plot the model
        legend = "{0}: {1}".format(
            result['model'], vis_utils.create_generic_legend(result['coeffs'], result['r_square']))
        Ivisualization.plot_model(x=result['plot_x'], y=result['plot_y'],
                                  legend=legend, color=_model_colors[result['model']])

        # Show the figure
        Ivisualization.show_figure()


def interval_computation(data_gen, model_list, parts, profile_filename):
    """The interval computation method. Every interval is computed and visualized independently.

    Arguments:
        data_gen(iterable): the generator with collected data (data provider generators)
        model_list(list of Model enum values): the list of models to compute
        parts(int): the number of intervals to split the computation into
        profile_filename(str): the base name for output visualisation file (will be further suffixed with specifiers)
    Returns:
        None

    """

    chunk_count = 0
    # Get the profiling data for each function
    for chunk in data_gen:
        chunk_count += 1

        interval_count = 0
        # Get the interval data generator
        for interval_gen in reg.interval_computation(chunk[0], chunk[1], parts, model_list):
            interval_count += 1

            # Create the filename and plot title
            plot_filename = "{0}_func{1}_interval{2}_plot.html".format(profile_filename, chunk_count, interval_count)
            plot_title = "{0} interval {1} performance".format(chunk[2], interval_count)

            # Create the figure and scatter plot for profiling data
            Ivisualization.set_figure(filename=plot_filename, title=plot_title)
            Ivisualization.plot_scatter(x=chunk[0], y=chunk[1])

            # Get every model result for the given interval
            for result in interval_gen:
                # Create the legend and plot the model
                legend = "{0}: {1}".format(
                    result['model'], vis_utils.create_generic_legend(result['coeffs'], result['r_square']))
                Ivisualization.plot_model(x=result['plot_x'], y=result['plot_y'],
                                          legend=legend, color=_model_colors[result['model']])

            # Show the interval results
            Ivisualization.show_figure()


def initial_guess_computation(data_gen, model_list, sample, profile_filename):
    """The initial guess computation method wrapper, only the final best fitting model is shown.

    Arguments:
        data_gen(iterable): the generator with collected data (data provider generators)
        model_list(list of Model enum values): the list of models to compute
        sample(int): the sample specification to perform the initial guess on
        profile_filename(str): the base name for output visualisation file (will be further suffixed with specifiers)
    Returns:
        None

    """
    chunk_count = 0
    # Get the profiling data for each function
    for chunk in data_gen:
        chunk_count += 1

        # Create the filename and plot title
        plot_filename = "{0}_func{1}_guess_plot.html".format(profile_filename, chunk_count)
        plot_title = "{0} performance".format(chunk[2])

        # Create the figure and scatter plot for profiling data
        Ivisualization.set_figure(filename=plot_filename, title=plot_title)
        Ivisualization.plot_scatter(x=chunk[0], y=chunk[1])

        # We expect only single yield
        result = next(reg.initial_guess_computation(chunk[0], chunk[1], model_list, sample))

        # Create legend and plot the model
        legend = "{0}: {1}".format(
            result['model'], vis_utils.create_generic_legend(result['coeffs'], result['r_square']))
        Ivisualization.plot_model(x=result['plot_x'], y=result['plot_y'],
                                  legend=legend, color=_model_colors[result['model']])

        # Show the figure
        Ivisualization.show_figure()


def bisection_computation(data_gen, model_list, profile_filename):
    """The bisection computation method wrapper.

    Arguments:
        data_gen(iterable): the generator with collected data (data provider generators)
        model_list(list of Model enum values): the list of models to compute
        profile_filename(str): the base name for output visualisation file (will be further suffixed with specifiers)
    Returns:
        None

    """
    chunk_count = 0
    # Get the profiling data for each function
    for chunk in data_gen:
        chunk_count += 1

        section_count = 0
        for section in reg.bisection_computation(chunk[0], chunk[1], model_list):
            section_count += 1
            # Create the filename and plot title
            plot_filename = "{0}_func{1}_section{2}_plot.html".format(profile_filename, chunk_count, section_count)
            plot_title = "{0} performance".format(chunk[2])

            # Create the figure and scatter plot for profiling data
            Ivisualization.set_figure(filename=plot_filename, title=plot_title)
            Ivisualization.plot_scatter(x=chunk[0], y=chunk[1])

            # Create the legend and plot the model
            legend = "{0}: {1}".format(
                section['model'], vis_utils.create_generic_legend(section['coeffs'], section['r_square']))
            Ivisualization.plot_model(x=section['plot_x'], y=section['plot_y'],
                                      legend=legend, color=_model_colors[section['model']])

            # Show the interval results
            Ivisualization.show_figure()


def compare_algorithms(data_gen_list, profile_filename):
    """The algorithms absolute comparison method wrapper.

    Arguments:
        data_gen_list(list): the generators list with collected data (data provider generators)
        profile_filename(str): the base name for output visualisation file (will be further suffixed with specifiers)
    Returns:
        None

    """
    plot_filename = "{0}_compare.html".format(profile_filename)
    plot_title = "Algorithms comparison"
    Ivisualization.set_figure(filename=plot_filename, title=plot_title)

    alg_count = 0
    for data_gen in data_gen_list:
        for chunk in data_gen:
            Ivisualization.plot_scatter(x=chunk[0], y=chunk[1], legend=chunk[2], **_scatter_colors[alg_count])
            alg_count += 1

    # Show the interval results
    Ivisualization.show_figure()


def compare_algorithms_relative(data_gen_list, profile_filename):
    """The algorithms relative comparison method wrapper.

    Arguments:
        data_gen_list(list): the generators list with collected data (data provider generators)
        profile_filename(str): the base name for output visualisation file (will be further suffixed with specifiers)
    Returns:
        None

    """
    algorithms = []
    # Get all algorithms
    for data_gen in data_gen_list:
        for chunk in data_gen:
            algorithms.append(chunk)

    # Create all possible tuples
    tuple_count = 0
    for first_alg in range(0, len(algorithms) - 1):
        for second_alg in range(first_alg + 1, len(algorithms)):
            tuple_count += 1

            plot_filename = "{0}_compare_relative_tuple{1}.html".format(profile_filename, tuple_count)
            plot_title = "Algorithms relative comparison"
            Ivisualization.set_figure(filename=plot_filename, title=plot_title,
                                      x_axis_label=algorithms[first_alg][2], y_axis_label=algorithms[second_alg][2])
            Ivisualization.custom_function('plot_relative_comparison',
                                           x=algorithms[first_alg][1], y=algorithms[second_alg][1])

            # Show the scatter plot
            Ivisualization.show_figure()


def scatter_plot_algorithm(data_gen, profile_filename):
    """The algorithm scatter plot wrapper.

    Arguments:
        data_gen(iterable): the generator with collected data (data provider generators)
        profile_filename(str): the base name for output visualisation file (will be further suffixed with specifiers)
    Returns:
        None

    """
    chunk_count = 0
    # Get the profiling data for each function
    for chunk in data_gen:
        chunk_count += 1

        plot_filename = "{0}_scatter{1}_plot.html".format(profile_filename, chunk_count)
        plot_title = "{0} performance".format(chunk[2])

        Ivisualization.set_figure(filename=plot_filename, title=plot_title)
        Ivisualization.plot_scatter(x=chunk[0], y=chunk[1], legend=chunk[2], **_scatter_colors[chunk_count - 1])

        # Show the scatter plot
        Ivisualization.show_figure()


def memory_consumption_computation(data_gen, profile_filename):
    """The memory consumption computation method wrapper, uses iterative method to estimate the complexity.

    Arguments:
        data_gen(iterable): the generator with collected memory data (data provider generators)
        profile_filename(str): the base name for output visualisation file (will be further suffixed with specifiers)
    Returns:
        None

    """

    chunk_count = 0
    # Get the memory profiling data for each function
    for chunk in data_gen:
        chunk_count += 1

        # Create the filename and plot title
        plot_filename = "{0}_func{1}_memory_plot.html".format(profile_filename, chunk_count)
        plot_title = "{0} memory performance".format(chunk[2])

        # Create the figure and scatter plot for profiling data
        Ivisualization.set_figure(filename=plot_filename, title=plot_title,
                                  x_axis_label='time (ms)', y_axis_label='allocated memory (B)')
        Ivisualization.plot_scatter(x=chunk[0], y=chunk[1])

        # Do all the iterations for one function and show only the last one
        for result in reg.iterative_computation(chunk[0], chunk[1], 4, [Models.all]):
            pass

        # Create legend and plot the model
        legend = "{0}: {1}".format(
            result['model'], vis_utils.create_generic_legend(result['coeffs'], result['r_square']))
        Ivisualization.plot_model(x=result['plot_x'], y=result['plot_y'],
                                  legend=legend, color=_model_colors[result['model']])

        # Show the figure
        Ivisualization.show_figure()
