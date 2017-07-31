"""Module for various means of regression data acquisition. """

from operator import itemgetter
import sys
import json


def data_provider_mapper(profile):
    """Unified data provider for various profile types.

    Arguments:
        profile(dict): the loaded profile dictionary

    Returns:
        generator: generator object created by specific provider function
    """
    profile_type = profile['header']['type']
    return _profile_mapper[profile_type](profile)


def complexity_profile_provider(profile):
    """Data provider for complexity collector profiling output.

    Arguments:
        profile(dict): the complexity profile dictionary

    Returns:
        generator: each subsequent call returns tuple: x points list, y points list, function name
    """
    # Get the file resources contents
    resources = profile['global']['resources']

    # Sort the dictionaries by function name for easier traversing
    resources = sorted(resources, key=itemgetter('uid'))
    x_points_list = []
    y_points_list = []
    function_name = resources[0]['uid']
    # Store all the points until the function name changes
    for resource in resources:
        if resource['uid'] != function_name:
            if x_points_list:
                # Function name changed, yield the list of data points
                yield x_points_list, y_points_list, function_name
                x_points_list = [resource['structure-unit-size']]
                y_points_list = [resource['amount']]
                function_name = resource['uid']
        else:
            # Add the data points
            x_points_list.append(resource['structure-unit-size'])
            y_points_list.append(resource['amount'])
    # End of resources, yield the current lists
    if x_points_list:
        yield x_points_list, y_points_list, function_name


def store_profile_to_file(filename, profile):
    """Save the profile dictionary into the unified profiling format.

    Arguments:
        filename(str): the name of the profiling file
        profile(dict): the profiling dictionary to save

    """
    with open(filename, 'w') as f:
        f.write(json.dumps(profile, sort_keys=True, indent=2))


def memory_collector_provider(filename):
    """Data provider for memory collector profiling output.

    Arguments:
        filename(string): the name of complexity profiling file

    Returns:
        generator: each subsequent call returns tuple: x points list, y points list, function name
    """
    with open(filename) as f:
        data = json.load(f)

    time_list, amount_list = [], []
    profile_edge = True
    for snapshot in data['snapshots']:
        timestamp = int(float(snapshot['time']) * 1000)
        amount = 0
        if 'sum_amount' in snapshot:
            amount = int(snapshot['sum_amount'])
        if amount_list and amount < amount_list[-1] and profile_edge:
            chunk_store_to_file((time_list, amount_list, 'SkiplistInsert optimized'), 'skiplist_opt_edge')
            profile_edge = False
        time_list.append(timestamp)
        amount_list.append(amount)
    chunk_store_to_file((time_list, amount_list, 'SkiplistInsert optimized'), 'skiplist_opt_full')


def column_file_provider(files):
    """Data provider for column profiling file.

    Arguments:
        files(list): the list of column profiling files
    Return:
        iter: the generator object which produces tuple of x, y and function name

    """
    for filename in files:
        try:
            # Tries to open the file
            with open(filename) as f:
                # Read the function name
                func = f.readline().rstrip('\n')
                # Read the data points
                x_pts, y_pts = [], []
                for line in f:
                    line = line.split(',')
                    x_pts.append(int(line[0]))
                    y_pts.append(int(line[1]))
                yield x_pts, y_pts, func
        except IOError:
            print('File {0} does not exist.'.format(filename), file=sys.stderr)


def profile_store_to_files(resources):
    """Used for the common profile"""
    chunk_num = 0
    # Get the chunks
    for chunk in complexity_profile_provider(resources):
        with open('chunk_' + str(chunk_num), 'w') as f:
            # Store the uid
            f.write(chunk[2] + '\n')
            # Write the points
            f.write('\n'.join('{0},{1}'.format(pt[0], pt[1]) for pt in zip(chunk[0], chunk[1])))
        chunk_num += 1


def chunk_store_to_file(chunk, filename):
    """Used for the common profile"""
    with open(filename, 'w') as f:
        # Store the uid
        f.write(chunk[2] + '\n')
        # Write the points
        f.write('\n'.join('{0},{1}'.format(pt[0], pt[1]) for pt in zip(chunk[0], chunk[1])))


# profile types : data provider functions mapping dictionary
# to add new profile type - simply add new keyword and specific provider function with signature:
#  - return value: generator object that produces required profile data
#  - parameter: profile dictionary
_profile_mapper = {
    'mixed': complexity_profile_provider,
    'memory': memory_collector_provider
}
