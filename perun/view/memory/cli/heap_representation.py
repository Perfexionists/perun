"""This module implements translation of the profile to heap representation"""
__author__ = 'Radim Podola'


def create_heap_map(profile):
    """ Create the heap map representation for visualization
    Arguments:
        profile(dict): the memory profile

    Returns:
        dict: the heap map representation

    Format of the heap map representation is following:
        {"type": type of representation (heap/heat)
         "unit": used memory unit (string),
         "stats": { # same stats like for each snapshots but calculated
                    # over all the snapshots
                    # (except sum_amount -> max_sum_amount instead)
                    },
         "info": [{uid of the function which made the allocation
                    "line": (int),
                    "function": (string),
                    "source": (string)
                 }]
         "snapshots": [
            {"time": time of the snapshot (string),
             "max_amount": maximum amount of the allocated memory
                           in snapshot (int),
             "min_amount": minimum amount of the allocated memory
                           in snapshot (int),
             "sum_amount": summary of the amount of the allocated memory
                           in snapshots (int)
             "max_address": maximal address of the allocated memory
                            in snapshot(int),
             "min_address": minimal address of the allocated memory
                            in snapshot (int),
             "map": [ # mapping of all the allocations in snapshot
                {"address": starting address of the allocated memory (int),
                 "amount": amount of the allocated memory (int),
                 "uid": index to info list with absolutely uid info (int)
                }
             ]
            }
         ]
        }
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

    return {'type': 'heap',
            'snapshots': snapshots,
            'info': chunks,
            'stats': glob_stats,
            'unit': profile['header']['units']['memory']}


def create_heat_map(profile):
    """ Create the heat map representation for visualization
    Arguments:
        profile(dict): the memory profile

    Returns:
        dict: the heat map representation

    Format of the heat map representation is following:
        {"type": type of representation (heap/heat)
         "unit": used memory unit (string),
         "stats": {"max_address": maximal address of the allocated memory
                                  in snapshot(int),
                   "min_address": minimal address of the allocated memory
                                  in snapshot (int)
                  },
         "map": [# mapping all the allocations to number of access to address
                 # size of array == max_address - min_address
                    0, 0, 5
                ]
        }
    """
    resources = []
    for snap in profile['snapshots']:
        resources.extend(snap['resources'])

    # adding statistics
    max_address = max(item.get('address', 0) + item.get('amount', 0)
                                      for item in resources)
    min_address = min(item.get('address', 0) for item in resources)

    # transform the memory profile to heat map representation
    map = get_heat_map(resources, min_address, max_address)

    return {"type": 'heat',
            "stats": {'max_address': max_address,
                      'min_address': min_address,
                      },
            "map": map,
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

    Arguments:
        snapshots(list): list of snapshots
    """
    alloc_chunks = []
    new_allocations = []
    existing_allocations = []
    for snap in snapshots:

        for allocation in snap['map']:
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
        existing_allocations = new_allocations.copy()

        for allocation in snap['map']:
            allocation['uid'] = set_chunks(alloc_chunks, allocation['uid'])

    return alloc_chunks


def set_chunks(chunks, uid):
    for i, c in enumerate(chunks):
        if isinstance(uid, int):
            return uid
        if c['function'] == uid['function'] and c['line'] == uid['line'] and c['source'] == uid['source']:
            return i

    chunks.append(uid)
    return len(chunks) - 1


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
            snap['max_address'] = max(item.get('address', 0) +
                                      item.get('amount', 0)
                                      for item in snap['map'])
            snap['min_address'] = min(item.get('address', 0)
                                      for item in snap['map'])
            snap['sum_amount'] = sum(item.get('amount', 0)
                                     for item in snap['map'])
            snap['max_amount'] = max(item.get('amount', 0)
                                     for item in snap['map'])
            snap['min_amount'] = min(item.get('amount', 0)
                                     for item in snap['map'])

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


if __name__ == "__main__":
    pass
