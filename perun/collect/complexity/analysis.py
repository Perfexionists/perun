"""Wrapper for regression analysis and visualization of collected data for easier usage.

The module consists of wrapper function for each implemented regression method. Every functions
takes care of analysis and visualisation and thus connecting the various modules.

"""

import regression_analysis.methods as reg
import visualizer.interface as Ivisualization
import visualizer.utils as vis_utils

# The color used for each model plotting
_model_colors = {
    'linear': 'GreenYellow',
    'logarithmic': 'Aqua',
    'power': 'DarkMagenta',
    'exponential': 'LimeGreen',
    'quadratic': 'MediumBlue'
}


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
        plot_filename = "{0}_func{1}_full_plot".format(profile_filename, chunk_count)
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
            plot_filename = "{0}_func{1}_iter{2}_plot".format(profile_filename, chunk_count, iter_count)
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
        plot_filename = "{0}_func{1}_iter_plot".format(profile_filename, chunk_count)
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
            plot_filename = "{0}_func{1}_interval{2}_plot".format(profile_filename, chunk_count, interval_count)
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
