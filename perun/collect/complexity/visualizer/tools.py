"""The internal tools module with helper functions.

"""

import visualizer.visualizer_exceptions as vis_except


def check_missing_arg(arg_list, collection):
    """Checks if collection is missing required arguments

    Arguments:
        arg_list(list): list of arguments that should be present in a collection
        collection(iterable): any iterable collection that will be checked
    Raises:
        VisualizationDataMissingArgument: if the collection is missing any of the arguments
    Returns:
        None
    """
    for arg in arg_list:
        if arg not in collection:
            raise vis_except.VisualizationDataMissingArgument(str(arg))