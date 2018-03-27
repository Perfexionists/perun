"""``perun.profile.convert`` is a module which specifies interface for
conversion of profiles from :ref:`profile-spec` to other formats.

.. _pandas: https://pandas.pydata.org/

Run the following in the Python interpreter to extend the capabilities of
Python to different formats of profiles::

    import perun.profile.convert

Combined with ``perun.profile.factory``, ``perun.profile.query`` and e.g.
`pandas`_ library one can obtain efficient interpreter for executing more
complex queries and statistical tests over the profiles.
"""
import copy

import perun.profile.query as query
import perun.postprocess.regression_analysis.transform as transform

import demandimport
with demandimport.enabled():
    import numpy
    import pandas

__author__ = 'Radim Podola'
__coauthors__ = ['Tomas Fiedor', 'Jirka Pavela']


def resources_to_pandas_dataframe(profile):
    """Converts the profile (w.r.t :ref:`profile-spec`) to format supported by
    `pandas`_ library.

    Queries through all of the resources in the `profile`, and flattens each
    key and value to the tabular representation. Refer to `pandas`_ libray for
    more possibilities how to work with the tabular representation of collected
    resources.

    E.g. given `time` and `memory` profiles ``tprof`` and ``mprof``
    respectively, one can obtain the following formats::

        >>> convert.resources_to_pandas_dataframe(tprof)
           amount  snapshots   uid
        0  0.616s          0  real
        1  0.500s          0  user
        2  0.125s          0   sys

        >>> convert.resources_to_pandas_dataframe(mmprof)
            address  amount  snapshots subtype                   trace    type
        0  19284560       4          0  malloc  malloc:unreachabl...  memory
        1  19284560       0          0    free  free:unreachable:...  memory

                          uid uid:function  uid:line                 uid:source
        0  main:../memo...:22         main        22   ../memory_collect_test.c
        1  main:../memo...:27         main        27   ../memory_collect_test.c

    :param dict profile: dictionary with profile w.r.t. :ref:`profile-spec`
    :returns: converted profile to ``pandas.DataFramelist`` with resources
        flattened as a pandas dataframe
    """
    resource_keys = list(query.all_resource_fields_of(profile))
    values = {key: [] for key in resource_keys}
    values['snapshots'] = []

    for (snapshot, resource) in query.all_resources_of(profile):
        values['snapshots'].append(snapshot)
        flattened_resource = dict(list(query.all_items_of(resource)))
        for rk in resource_keys:
            values[rk].append(flattened_resource.get(rk, numpy.nan))

    return pandas.DataFrame(values)


def to_heap_map_format(profile):
    """Simplifies the profile (w.r.t. :ref:`profile-spec`) to a representation
    more suitable for interpretation in the `heap map` format.

    This format is used as an internal representation in the
    :ref:`views-heapmap` visualization module. It specification is as follows:

    .. code-block:: json

        {
            "type": "type of representation (heap/heat)",
            "unit": "used memory unit (string)",
            "stats": {},
            "info": [{
                "line": "(int)",
                "function": "(string)",
                "source": "(string)"
             }],
            "snapshots": [{
                "time": "time of the snapshot (string)",
                "max_amount": "maximum allocated memory in snapshot (int)",
                "min_amount": "minimum allocated memory in snapshot (int)",
                "sum_amount": "sum of allocated memory in snapshot (int)",
                "max_address": "maximal address where we allocated (int)",
                "min_address": "minimal address where we allocated (int)",
                "map": [{
                    "address": "starting address of the allocation (int)",
                    "amount": "amount of the allocated memory (int)",
                    "uid": "index to info list with uid info (int)",
                    "subtype": "allocator (string)"
                }]
            }]
        }

    `Type` specifies either the heap or heat representation of the data. For
    each `snapshot`, we have a one `map` of addresses to allocated chunks of
    different subtypes of allocators and `uid`. Moreover, both `snapshot` and
    `stats` contains several aggregated data (e.g. min, or max address) for
    visualization of the memory.

    The usage of :ref:`views-heapmap` is for visualization of address space
    regarding the allocations during different time's of the program (i.e.
    snapshots) and is meant for detecting inefficient allocations or
    fragmentations of memory space.

    :param dict profile: profile w.r.t. :ref:`profile-spec` of **memory**
        `type`
    :returns: dictionary containing heap map representation usable for
        :ref:`views-heapmap` visualization module.
    """
    snapshots = [a for a in profile['snapshots']]

    # modifying the memory profile to heap map representation
    for snap in snapshots:
        snap['map'] = get_heap_map(snap['resources'])
        del snap['resources']

    # calculating existing allocations for each snapshot
    chunks = calculate_heap_map(snapshots)
    # adding statistics about each snapshot
    glob_stats = add_stats(snapshots)

    # approximation for extreme cases
    if glob_stats['max_address'] - glob_stats['min_address'] < 500:
        glob_stats['max_address'] = glob_stats['min_address'] + 500
    elif glob_stats['max_address'] - glob_stats['min_address'] > 1000000:
        glob_stats['max_address'] = glob_stats['min_address'] + 1000000

    return {'type': 'heap',
            'snapshots': snapshots,
            'info': chunks,
            'stats': glob_stats,
            'unit': profile['header']['units']['memory']}


def to_heat_map_format(profile):
    """Simplifies the profile (w.r.t. :ref:`profile-spec`) to a representation
    more suitable for interpretation in the `heat map` format.

    This format is used as an internal aggregation of the allocations through
    all of the snapshots in the :ref:`views-heapmap` visualization module.
    The specification is similar to :func:`to_heap_map_format` as follows:

    .. code-block:: json

        {
            "type": "type of representation (heap/heat)",
            "unit": "used memory unit (string)",
            "stats": {
                "max_address": "maximal address in snapshot (int)",
                "min_address": "minimal address in snapshot (int)"
            },
            "map": [ ]
        }

    The main difference is in the `map`, where the data are aggregated over the
    snapshots represented by value representing the colours. The `warmer` the
    colour the more it was allocated on the concrete address.

    :param dict profile: profile w.r.t. :ref:`profile-spec` of **memory**
        `type`
    :returns: dictionary containing heat map representation usable for
        :ref:`views-heapmap` visualization module.
    """
    resources = []
    for snap in profile['snapshots']:
        resources.extend(snap['resources'])

    # adding statistics
    max_address = max(item.get('address', 0) + item.get('amount', 0)
                      for item in resources if item.get('address', 0) > 0)
    min_address = min(item.get('address', 0) for item in resources if item.get('address', 0) > 0)
    # approximation for extreme cases
    if max_address - min_address < 500:
        max_address = min_address + 500
    elif max_address - min_address > 1000000:
        max_address = min_address + 1000000

    # transform the memory profile to heat map representation
    heat_map = get_heat_map(resources, min_address, max_address)

    return {"type": 'heat',
            "stats": {'max_address': max_address, 'min_address': min_address, },
            "map": heat_map,
            'unit': profile['header']['units']['memory']}


def get_heat_map(resources, min_add, max_add):
    """ Parse resources from the memory profile to HEAT map representation

    Arguments:
        resources(list): list of the resources from the memory profile

    Returns:
        list: list of the number of access to address
    """
    address_count = max_add - min_add
    add_map = [0 for _ in range(address_count)]

    for res in resources:
        if res['address'] > max_add:
            continue

        address = res['address']
        amount = res['amount']

        for add in range(amount):
            add_map[address + add - min_add] += 1

    return add_map


def get_heap_map(resources):
    """ Parse resources from the memory profile to simpler representation

    Arguments:
        resources(list): list of the resources from the memory profile

    Returns:
        list: list of the simple allocations records
    """
    # TODO maybe needed approximation inc ase of really different sizes
    # of the amount, when smaller sizes could be set to zero and other sizes's
    # units change to bigger ones (B > MB)
    simple_map = []

    for res in resources:
        map_item = {}
        map_item['address'] = res['address']
        map_item['subtype'] = res['subtype']
        map_item['amount'] = res['amount']
        if not res['uid']:
            continue
        map_item['uid'] = res['uid']
        if res['subtype'] == 'free':
            map_item['type'] = 'free'
        else:
            map_item['type'] = 'allocation'

        simple_map.append(map_item)

    return simple_map


def calculate_heap_map(snapshots):
    """ Will calculate existing allocations for each snapshot

        Result is in the form of modified input argument.
        Allocations which are not freed within snapshot are spread to next
        following snapshots till they are freed

    Arguments:
        snapshots(list): list of snapshots

    Returns:
        list: chunk of the all used UIDs
    """
    alloc_chunks = []
    new_allocations = []
    existing_allocations = []
    for snap in snapshots:
        for allocation in copy.copy(snap['map']):
            if allocation['type'] == 'free':
                alloc = next((x for x in new_allocations
                              if x['address'] == allocation['address']), None)
                if alloc:
                    new_allocations.remove(alloc)

                # removing free record
                snap['map'].remove(allocation)
            else:
                del allocation['type']
                new_allocations.append(allocation)

        # extending existing allocations from previous to the current snapshot
        snap['map'].extend(existing_allocations)
        existing_allocations = copy.deepcopy(new_allocations)

        # change absolute UID to chunk reference
        for allocation in snap['map']:
            allocation['uid'] = __set_chunks(alloc_chunks, allocation['uid'])

    return alloc_chunks


def __set_chunks(chunks, uid):
    """ Sets UID reference to chunk list

        Check if UID is in the chunk list, if so index is returned.
        If not, UID is added to the chunk list.

    Arguments:
        chunks(list): chunk list
        uid(dict): UID structure

    Returns:
        int: index to chunk list referencing UID
    """
    # UID is already referencing
    if isinstance(uid, int):
        return uid

    for i, chunk in enumerate(chunks):
        func_cond = chunk['function'] == uid['function']
        line_cond = chunk['line'] == uid['line']
        source_cond = chunk['source'] == uid['source']
        # UID found in chunk
        if func_cond and line_cond and source_cond:
            return i

    # UID add to chunk
    chunks.append(uid)

    return len(chunks) - 1


def resource_iterator(snapshot, field, initial_value=None):
    """
    Arguments:
        snapshot(list): list of resources
        field(str): field we are iterating over in the list of resources
        initial_value(object): neutral value, that is returned as first

    Returns:
        :
    """
    found_value = False
    for item in snapshot:
        if field in item.keys():
            found_value = True
            yield item[field]
    if not found_value:
        yield initial_value


def add_stats(snapshots):
    """ Add statistic about each snapshot and global view

        Maximum amount of the allocated memory,
        minimum amount of the allocated memory,
        summary of the amount of the allocated memory,
        maximal address of the allocated memory
        (counted as start address + amount),
        minimal address of the allocated memory.

        Result is in the form of modified input argument.

    Arguments:
        snapshots(list): list of snapshots

    Return:
        dict: calculated global statistics over all the snapshots
    """
    glob_max_address = []
    glob_min_address = []
    glob_max_sum_amount = []
    glob_max_amount = []
    glob_min_amount = []

    for snap in snapshots:
        if not len(snap['map']):
            continue
        else:
            snap['max_address'] \
                = max(item.get('address', 0) + item.get('amount', 0) for item in snap['map'])
            snap['min_address'] = min(resource_iterator(snap['map'], 'address', 0))
            snap['sum_amount'] = sum(resource_iterator(snap['map'], 'amount', 0))
            snap['max_amount'] = max(resource_iterator(snap['map'], 'amount', 0))
            snap['min_amount'] = min(resource_iterator(snap['map'], 'amount', 0))

        glob_max_address.append(snap['max_address'])
        glob_min_address.append(snap['min_address'])
        glob_max_sum_amount.append(snap['sum_amount'])
        glob_max_amount.append(snap['max_amount'])
        glob_min_amount.append(snap['min_amount'])

    return {'max_address': max(glob_max_address),
            'min_address': min(glob_min_address),
            'max_sum_amount': max(glob_max_sum_amount),
            'max_amount': max(glob_max_amount),
            'min_amount': min(glob_min_amount)
           }


def to_allocations_table(profile):
    """ Create the allocations table

    Fixme: Where exactly is this used?

    Arguments:
        profile(dict): the memory profile

    Returns:
        dict: the allocations table

    Format of the allocations table is following:
        {"snapshots": [(int)]
         "amount": [(int)]
         "uid": [(str)]
         "subtype": [(str)]
         "address": [(int)]
        }
    uid object is serialized into: function()~source~line
    """
    table = {
        'snapshots': [],
        'amount': [],
        'uid': [],
        'subtype': [],
        'address': []
    }

    for i, snap in enumerate(profile['snapshots']):
        for alloc in snap['resources']:
            table['snapshots'].append(i + 1)
            table['amount'].append(alloc['amount'])
            table['uid'].append(to_string_line(alloc['uid']))
            table['subtype'].append(alloc['subtype'])
            table['address'].append(alloc['address'])

    return table


def to_flow_table(profile):
    """ Create the heap map table

    Fixme: Where exactly is this used

    Arguments:
        profile(dict): the memory profile

    Returns:
        dict: the heap map table

    Format of the allocations table is following:
        {"snapshots": [(int)]
         "amount": [(int)]
         "uid": [(str)]
         "subtype": [(str)]
         "address": [(int)]
        }
    uid object is serialized into: function()~source~line
    """
    heap = to_heap_map_format(profile)

    table = {
        'snapshots': [],
        'amount': [],
        'uid': [],
        'subtype': [],
        'address': []
    }

    for i, snap in enumerate(heap['snapshots']):

        for alloc in snap['map']:
            uid_chunk = heap['info'][alloc['uid']]

            table['snapshots'].append(i + 1)
            table['amount'].append(alloc['amount'])
            table['uid'].append(to_string_line(uid_chunk))
            table['subtype'].append(alloc['subtype'])
            table['address'].append(alloc['address'])

    return table


def to_flame_graph_format(profile):
    """Transforms the **memory** profile w.r.t. :ref:`profile-spec` into the
    format supported by perl script of Brendan Gregg.

    .. _Brendan Gregg's homepage: http://www.brendangregg.com/index.html

    :ref:`views-flame-graph` can be used to visualize the inclusive consumption
    of resources w.r.t. the call trace of the resource. It is useful for fast
    detection, which point at the trace is the hotspot (or bottleneck) in the
    computation. Refer to :ref:`views-flame-graph` for full capabilities of our
    Wrapper. For more information about flame graphs itself, please check
    `Brendan Gregg's homepage`_.

    Example of format is as follows::

        >>> print(''.join(convert.to_flame_graph_format(memprof)))
        malloc()~unreachable~0;main()~/home/user/dev/test.c~45 4
        valloc()~unreachable~0;main()~/home/user/dev/test.c~75;__libc_start_main()~unreachable~0;_start()~unreachable~0 8
        main()~/home/user/dev/test02.c~79 156

    Each line corresponds to some collected resource (in this case amount of
    allocated memory) preceeded by its trace (i.e. functions or other unique
    identifiers joined using ``;`` character.

    :param dict profile: the memory profile
    :returns: list of lines, each representing one allocation call stack
    """
    stacks = []
    for snap in profile['snapshots']:
        for alloc in snap['resources']:
            if alloc['subtype'] != 'free':
                stack_str = ""
                for frame in alloc['trace']:
                    line = to_string_line(frame)
                    stack_str += line + ';'
                if stack_str and stack_str.endswith(';'):
                    final = stack_str[:-1]
                    final += " " + str(alloc['amount']) + '\n'
                    stacks.append(final)

    return stacks


def to_string_line(frame):
    """ Create string representing call stack's frame

    Arguments:
        frame(dict): call stack's frame

    Returns:
        str: line representing call stack's frame
    """
    return "{}()~{}~{}".format(frame['function'], frame['source'], frame['line'])


def plot_data_from_coefficients_of(model):
    """Transform coefficients computed by
    :ref:`postprocessors-regression-analysis` into dictionary of points,
    plotable as a function or curve. This function serves as a public wrapper
    over regression analysis transformation function.

    :param dict model: the models dictionary from profile (refer to
        :pkey:`models`)
    :returns dict: updated models dictionary extended with `plot_x` and
        `plot_y` lists
    """
    model.update(transform.coefficients_to_points(**model))
    return model


def flatten(flattened_value):
    """Converts the value to something that can be used as one value.

    Flattens the value to single level, lists are processed to comma separated representation and
    rest is left as it is.
    TODO: Add caching

    :param object flattened_value: value that is flattened
    :returns: either decimal, string, or something else
    """
    # Dictionary is processed recursively according to the all items that are nested
    if isinstance(flattened_value, dict):
        nested_values = []
        for _, value in query.all_items_of(flattened_value):
            # Add one level of hierarchy with ':'
            nested_values.append(value)
        # Return the overall key as joined values of its nested stuff,
        # only if root is not a list (i.e. root key is not int = index)!
        return ":".join(map(str, nested_values))
    # Lists are merged as comma separated keys
    elif isinstance(flattened_value, list):
        return ','.join(
            ":".join(str(nested_value[1]) for nested_value in query.flattened_values(i, lv))
            for (i, lv) in enumerate(flattened_value)
        )
    # Rest of the values are left as they are
    else:
        return flattened_value
