""" Module with graphs creation and configuration functions. """

from operator import itemgetter
from collections import defaultdict

import perun.profile.query as query
import perun.profile.converters as converters
import perun.utils.bokeh_helpers as bokeh_helpers

import demandimport
with demandimport.enabled():
    import bkcharts as charts
    import bokeh.palettes as palettes

__author__ = 'Jiri Pavela'


def slice_resources_by_uid(resources, models, uids):
    """ Splits the resource tables and models into slices by the unique uids found in the resources.

    Arguments:
        resources(pandas.DataFrame): the data table from resources
        models(list of dict): the list of models from profile
        uids(list): the list of unique uids from profile

    Returns:
        generator: resources and models slices of unique uid as pair
            data_slice(pandas.DataFrame)
            uid_models(list)
    """
    for uid in uids:
        # Slice only the plotted uid from the data table
        uid_slice = resources[resources.uid == uid]
        if uid_slice.size == 0 or uid_slice.shape[0] <= 1:
            # plotting one point does not work (it has no real usage anyway), fix later
            continue
        # Filter models for the given uid
        uid_models = list(filter(lambda m, u=uid: m['uid'] in u, models))
        yield uid_slice, uid_models


def slice_models_by_interval(models):
    """ Splits the models list into slices with different x axis intervals.

    Arguments:
        models(list of dict): the list of models to split

    Returns:
        generator: stream of models slices (list)
    """
    # Sort the models by intervals first, to yield them in order
    models = sorted(models, key=itemgetter('x_interval_start', 'x_interval_end'))
    # Separate the models into groups according to intervals
    intervals = defaultdict(list)
    for model in models:
        intervals[(model['x_interval_start'], model['x_interval_end'])].append(model)
    # Yield the list of models with the same interval
    for interval_models in intervals.items():
        yield interval_models[1]


def generate_plot_data_slices(profile):
    """ Generates data slices for plotting resources and models. The resources are split by unique
        uids, models are sliced into parts by uid and interval.

    Arguments:
        profile(dict): loaded perun profile

    Returns:
        generator: generator: resources and models slices of unique uid as pair
            data_slice(pandas.DataFrame)
            uid_models(list)
    """
    # Get resources for scatter plot points and models for curves
    resource_table = converters.resources_to_pandas_dataframe(profile)
    models = [m[1] for m in list(query.all_models_of(profile))]
    # Get unique uids from profile, each uid (and optionally interval) will have separate graph
    uids = query.unique_resource_values_of(profile, 'uid')

    # Process each uid data
    for uid_slice, uid_models in slice_resources_by_uid(resource_table, models, uids):
        # Slice the uid models according to different intervals (each interval is plotted
        # separately as it improves readability)
        if uid_models:
            for interval_models in slice_models_by_interval(uid_models):
                yield uid_slice, interval_models
        else:
            # There are no models to plot
            yield uid_slice, []


def draw_models(graph, models):
    """ Add models renderers to the graph.

    Arguments:
        graph(charts.Graph): the scatter plot without models
        models(list): list of models to plot

    Returns:
        charts.Graph: the modified graph with model curves renderers
    """
    # Get unique colors for the model curves
    colour_palette = palettes.viridis(len(models))
    for idx, model in enumerate(models):
        # Convert the coefficients to points that can be plotted
        model = converters.plot_data_from_coefficients_of(model)
        # Create legend for the plotted model
        coeffs = ', '.join('{}={:f}'.format(c['name'], c['value']) for c in model['coeffs'])
        legend = '{0}: {1}, r^2={2:f}'.format(model['model'], coeffs, model['r_square'])
        # Plot the model
        graph.line(x=model['plot_x'], y=model['plot_y'],
                   line_color=colour_palette[idx], line_width=2.5, legend=legend)
    return graph


def create_from_params(profile, of_key, per_key, x_axis_label, y_axis_label, graph_title,
                       graph_width=800):
    """Creates Scatter plot graph according to the given parameters.

    Takes the input profile, convert it to pandas.DataFrame. Then the data according to 'of_key'
    parameter are used as values and are output depending on values of 'per_key'.
    Furthermore, models records are also plotted if the profile contains them.

    Arguments:
        profile(dict): dictionary with measured data
        of_key(str): key that specifies which fields of the resource entry will be used as data
        per_key(str): key that specifies fields of the resource that will be on the x axis
        x_axis_label(str): label on the x axis
        y_axis_label(str): label on the y axis
        graph_title(str): name of the graph
        graph_width(int): width of the created bokeh graph

    Returns:
        charts.Scatter: scatter plot graph with models built according to the params
    """
    for data_slice, models_slice in generate_plot_data_slices(profile):
        # Plot the points as a scatter plot
        scatter = charts.Scatter(data_slice, x=per_key, y=of_key, title=graph_title,
                                 xlabel=x_axis_label, ylabel=y_axis_label)

        # Configure the graph properties
        # Create the graph title as a combination of default parameter, uid, method and
        # interval values (only if models are plotted) for easier identification
        this_graph_title = graph_title + '; uid: {0}'.format(data_slice.uid.values[0])
        if models_slice:
            this_graph_title += ('; method: {0}; interval <{1}, {2}>'
                                 .format(models_slice[0]['method'],
                                         models_slice[0]['x_interval_start'],
                                         models_slice[0]['x_interval_end']))
        bokeh_helpers.configure_graph(
            scatter, profile, 'count', this_graph_title, x_axis_label, y_axis_label, graph_width)

        # Plot all models
        scatter = draw_models(scatter, models_slice)

        yield scatter
