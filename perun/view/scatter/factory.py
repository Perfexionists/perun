""" Module with graphs creation and configuration functions. """

import numpy as np
from operator import itemgetter
from collections import defaultdict

import perun.profile.query as query
import perun.profile.convert as convert
import perun.utils.bokeh_helpers as bokeh_helpers
import perun.postprocess.regression_analysis.data_provider as data_provider
import perun.postprocess.regressogram.methods as rg_methods

import demandimport

with demandimport.enabled():
    import bkcharts as charts
    import bokeh.palettes as palettes

__author__ = 'Jiri Pavela'


def slice_resources_by_uid(resources, models, uids):
    """ Splits the resource tables and models into slices by the unique uids found in the resources.

    :param pandas.DataFrame resources: the data table from resources
    :param list of dict models: the list of models from profile
    :param map uids: the list of unique uids from profile
    :returns generator: resources and models slices of unique uid as pair
        (data_slice(pandas.DataFrame), uid_models(list))
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

    :param list of dict models: the list of models to split
    :returns generator: stream of models slices (list)
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

    :param dict profile: loaded perun profile
    :returns generator: generator: resources and models slices of unique uid as pair
        (data_slice(pandas.DataFrame), uid_models(list))
    """
    # Get resources for scatter plot points and models for curves
    resource_table = convert.resources_to_pandas_dataframe(profile)
    models = list(map(itemgetter(1), query.all_models_of(profile)))
    # Get unique uids from profile, each uid (and optionally interval) will have separate graph
    uids = map(convert.flatten, query.unique_resource_values_of(profile, 'uid'))

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


def draw_models(graph, models, profile):
    """ Add models renderers to the graph.

    :param charts.Graph graph: the scatter plot without models
    :param list models: list of models to plot
    :param dict profile: dictionary with measured data to pairing model with resources
    :returns charts.Graph: the modified graph with model curves renderers
    """
    # Get unique colors for the model curves
    colour_palette = palettes.viridis(len(models))
    for idx, model in enumerate(models):
        # Coefficients are part only of parametric models
        if 'coeffs' in model:
            graph = create_parametric_model(graph, model, colour_palette[idx])
        # The non-parametric models do not contain the coefficients
        elif model['method'] == 'regressogram':
                graph = create_regressogram_model(graph, model, colour_palette[idx])
        elif model['method'] == 'moving_average':
                graph = create_moving_average_model(graph, model, profile, colour_palette[idx])
    return graph


def create_parametric_model(graph, model, colour):
    """
    Rendering the parametric models according to its coefficients.

    :param charts.Graph graph: the scatter plot to render new models
    :param model: the parametric model to be render to the graph
    :param colour: the color of the current model to distinguish in the case of several models in the graph
    :return charts.Graph: the modified graph with new model curves
    """
    # Convert the coefficients to points that can be plotted
    model = convert.plot_data_from_coefficients_of(model)
    # Create legend for the plotted model
    coeffs = ', '.join('{}={:f}'.format(c['name'], c['value']) for c in model['coeffs'])
    legend = '{0}: {1}, r^2={2:f}'.format(model['model'], coeffs, model['r_square'])
    # Plot the model
    graph.line(x=model['plot_x'], y=model['plot_y'], line_color='#000000', line_width=7.5, legend=legend)
    graph.line(x=model['plot_x'], y=model['plot_y'], line_color=colour, line_width=3.5, legend=legend)
    return graph


def create_regressogram_model(graph, model, colour):
    """
    Rendering the regressogram model according to its computed properties.

    :param charts.Graph graph: the scatter plot to render new models
    :param model: the regressogram model which to be rendered to the graph
    :param colour: the color of the current model to distinguish in the case of several models in the graph
    :return charts.Graph: the modified graph with new regressogram model
    """
    # Evenly division of the interval by number of buckets
    x_pts = np.linspace(model['x_interval_start'], model['x_interval_end'], num=len(model['bucket_stats']) + 1)
    # Add the beginning of the first edge
    y_pts = np.append(model['y_interval_start'], model['bucket_stats'])
    # Create legend for the plotted model
    legend = '{0}: buckets={1}, stat: {2}, R^2={3:f}'.format(model['method'][:3], len(model['bucket_stats']),
                                                             model['statistic_function'], model['r_square'])
    # Plot the render_step_function function for regressogram model
    graph_params = {'color': colour, 'line_width': 3.5, 'legend': legend}
    return rg_methods.render_step_function(graph, x_pts, y_pts, graph_params)


def create_moving_average_model(graph, model, profile, colour):
    """
    Rendering the moving average model according to its computed properties.

    :param charts.Graph graph: the scatter plot to render new models
    :param model: the moving average model which to be rendered to the graph
    :param dict profile: the profile to obtains the x-coordinates
    :param colour: the color of the current model to distinguish in the case of several models in the graph
    :return charts.Graph: the modified graph with new moving average model
    """
    # Create legend for the plotted model
    legend = '{0}: window={1}, R^2={2:f}'.format(model['moving_method'], model['window_width'], model['r_square'])
    # Obtains the x-coordinates with the required uid to pair with current model
    params = {'of_key': 'amount', 'per_key': model['per_key']}
    for x_pts, _, uid in data_provider.data_provider_mapper(profile, **params):
        if uid == model['uid']:
            # Plot the model
            graph.line(x=sorted(x_pts), y=model['bucket_stats'], line_color=colour, line_width=3.5, legend=legend)
    return graph


def create_from_params(profile, of_key, per_key, x_axis_label, y_axis_label, graph_title,
                       graph_width=800):
    """Creates Scatter plot graph according to the given parameters.

    Takes the input profile, convert it to pandas.DataFrame. Then the data according to 'of_key'
    parameter are used as values and are output depending on values of 'per_key'.
    Furthermore, models records are also plotted if the profile contains them.

    :param dict profile: dictionary with measured data
    :param str of_key: key that specifies which fields of the resource entry will be used as data
    :param str per_key: key that specifies fields of the resource that will be on the x axis
    :param str x_axis_label: label on the x axis
    :param str y_axis_label: label on the y axis
    :param str graph_title: name of the graph
    :param int graph_width: width of the created bokeh graph
    :returns uid, charts.Scatter: uid and scatter plot graph with models built according to the
        params
    """
    for data_slice, models_slice in generate_plot_data_slices(profile):
        # Plot the points as a scatter plot
        scatter = charts.Scatter(data_slice, x=per_key, y=of_key, title=graph_title,
                                 xlabel=x_axis_label, ylabel=y_axis_label,
                                 tools='pan,wheel_zoom,box_zoom,zoom_in,zoom_out,crosshair,'
                                       'reset,save')

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
        scatter = draw_models(scatter, models_slice, profile)

        yield '{}'.format(data_slice.uid.values[0]), scatter
