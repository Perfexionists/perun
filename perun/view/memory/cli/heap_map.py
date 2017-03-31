"""This module implement the heap map visualization of the profile"""
import sys
import math
import curses
import curses.textpad
from random import randint

import json

__author__ = 'Radim Podola'
NEXT_SNAPSHOT = 1
PREV_SNAPSHOT = -1
MIN_ROWS = 30
MIN_COLS = 70
COLOR_BORDER = 1
COLOR_FREE_FIELD = 2
COLOR_SNAPSHOT_INFO = 3
GOOD_COLORS = 0


def init_curses_colors():
    global GOOD_COLORS, COLOR_BORDER, COLOR_FREE_FIELD, COLOR_SNAPSHOT_INFO

    curses.start_color()
    curses.use_default_colors()

    good_colors = (
        1, 2, 3, 4, 5, 6, 7, 11, 14, 17, 21, 19, 22, 23, 27, 33, 30, 34, 45,
        41,46, 49, 51, 52, 54, 56, 58, 59, 62, 65, 71, 76, 89, 91, 94, 95, 124,
        125, 126, 127, 129, 130, 131, 154, 156, 159, 161, 166, 167, 178, 195,
        197, 199, 203, 208, 210, 211, 214, 220, 226, 229, 255)

    start_pair_number = 1
    for i in good_colors:
        curses.init_pair(start_pair_number, -1, i)
        start_pair_number += 1

    GOOD_COLORS = start_pair_number - 1
    # border color
    curses.init_pair(start_pair_number, 16, 16)
    COLOR_BORDER = start_pair_number
    start_pair_number += 1

    curses.init_pair(start_pair_number, -1, 242)
    COLOR_FREE_FIELD = start_pair_number
    start_pair_number += 1

    curses.init_pair(start_pair_number, -1, 16)
    COLOR_SNAPSHOT_INFO = start_pair_number



def resize_req_print(window):
    """ Print resize request to the window
    Arguments:
        window(any): console window
    """
    resize_req = "Resize screen up, please"

    window.addstr(int(curses.LINES / 2),
                  int((curses.COLS - len(resize_req)) / 2),
                  resize_req)


def intro_print(window):
    """ Print INTRO screen to the window
    Arguments:
        window(any): console window
    """
    intro = "HEAP MAP!"

    window.addstr(curses.LINES // 2, (curses.COLS - len(intro))//2,
                  intro, curses.A_BOLD)


def menu_print(window):
    """ Print menu information to the window
    Arguments:
        window(any): console window
    """
    menu = '[Q] QUIT  [<] PREVIOUS  [>] NEXT  [A] ANIMATE  [4|8|6|5] CURSOR L|U|R|D'

    window.addstr(curses.LINES - 1, (curses.COLS - len(menu)) // 2,
                  menu, curses.A_BOLD)


def animation_menu_print(window):
    """ Print animation menu information to the window
    Arguments:
        window(any): console window
    """
    menu = '[Q] QUIT  [S] STOP  [C] CONTINUE  [R] RESTART'

    window.addstr(curses.LINES - 1, (curses.COLS - len(menu)) // 2,
                  menu, curses.A_BOLD)


def info_print(window, max, curr, indent):
    """ Print the heap information to the window
    Arguments:
        window(any): console window
        max(int): total number of the snapshots
        curr(int): number of the current snapshot
    """
    info_text = 'SNAPSHOT: ' + str(curr) + '/' + str(max)
    window.addstr(0, (curses.COLS - len(info_text)) // 2 + indent,
                  info_text, curses.color_pair(COLOR_SNAPSHOT_INFO))


def create_screen_decomposition(heap, curr, rows, cols):
    """ Fill the matrix with corresponding representation of snapshot
    Arguments:
        matrix(list): matrix to update
        heap(dict): heap map representation
        curr(int): number of the current snapshot

    Returns:
        list: updated matrix
    """
    snap = heap['snapshots'][curr - 1]

    # calculating approximated field size
    add_range = snap['max_address'] - snap['min_address']
    field_size = math.ceil(add_range / (cols * rows))

    if field_size < 1:
        field_size = 1
    assert field_size >= 1

    matrix = [[None for y in range(cols)] for x in range(rows)]

    allocations = snap['map']
    # sorting allocations records by frequency of allocations
    allocations.sort(key=lambda x: x['address'])
    iterator = iter(allocations)


    record = next(iterator, None)
    # set starting address to first approx field
    last_field = 0 if record is None else record['address']
    remain_amount = 0 if record is None else record['amount']
    for row in range(rows):
        for col in range(cols):

            if record is not None:
                # if is record address not in the next field,
                # let's put there empty field
                if record['address'] > last_field + field_size:
                    matrix[row][col] = {"uid": None,
                                        "address": last_field,
                                        "amount": 0}
                    last_field += field_size
                    continue

                matrix[row][col] = {"uid": record['uid'],
                                    "address": record['address'],
                                    "amount": record['amount']}

                if remain_amount <= field_size:
                    record = next(iterator, None)
                    remain_amount = 0 if record is None else record['amount']
                else:
                    remain_amount -= field_size

                last_field += field_size
            else:
                matrix[row][col] = {"uid": None,
                                    "address": last_field,
                                    "amount": 0}
                last_field +=field_size


    return {'map': matrix, 'size': field_size}


def matrix_print(window, data, rows, cols, add_length):
    """ Prints the matrix to the window
    Arguments:
        window(any): console window
        data(list): data to print
    """
    #field_sym = u"\u2588"
    border_sym = u"\u2588"
    field_sym = '_'
    address = data['map'][0][0]['address']
    line_address_size = len(data['map'][0]) * data['size']
    # structure for saving corresponding allocation
    # with their specific color representation
    color_records = []


    def get_field_color(field, color_records):
        if field['uid'] is None:
            return COLOR_FREE_FIELD

        uid = field['uid']
        for item in color_records:
            if (uid['function'] == item['uid']['function'] and
                uid['source'] == item['uid']['source']):
                return item['color']

        color_records.append({'uid': uid,
                            'color': randint(1, GOOD_COLORS)})
        return color_records[-1]['color']


    for row in range(rows):
        # address info printing calculated from 1st and field size (approx)
        if row not in (0, rows-1):
            window.addstr(row, 0, str(address))
            address += line_address_size
        elif row == 0:
            window.addstr(row, 0, 'ADDRESS:', curses.A_BOLD)

        for col in range(add_length, cols):
            # border printing
            if row in (0, rows-1):
                window.addch(row, col, border_sym, curses.color_pair(COLOR_BORDER))
            elif col in (add_length, cols-1):
                window.addch(row, col, border_sym, curses.color_pair(COLOR_BORDER))
            # filed printing
            else:
                field = data['map'][row - 1][col - add_length - 1]
                color = get_field_color(field, color_records)
                if row == rows-2:
                    window.addch(row, col, ' ', curses.color_pair(color))
                else:
                    window.addstr(row, col, field_sym, curses.color_pair(color))


def redraw_heap_map(window, heap, snapshot):
    curses.update_lines_cols()
    window.clear()

    max_add_len = len(str(heap['snapshots'][snapshot - 1]['max_address']))
    add_info_len = max_add_len + 2

    if curses.LINES < MIN_ROWS or (curses.COLS - add_info_len) < MIN_COLS:
        window.clear()
        resize_req_print(window)
        return {'x': 0, 'y': 0, 'rows': 0, 'cols': 0}

    # number of matrix rows == minimum of rows - 2*border field
    map_rows = MIN_ROWS - 2
    # number of matrix cols == terminal current cols - size of address info - 2*border field
    map_cols = curses.COLS - add_info_len - 2
    # getting heap map decomposition
    decomposition = create_screen_decomposition(heap, snapshot,
                                                map_rows, map_cols)
    assert decomposition

    try:
        # printing heap map decomposition to the console window
        matrix_print(window, decomposition, MIN_ROWS, curses.COLS, add_info_len)
        # printing heap info to the console window
        info_print(window, heap['max'], snapshot, add_info_len)

        return {'x': 1, 'y': add_info_len + 1, 'rows': map_rows, 'cols': map_cols}

    except curses.error:
        window.clear()
        resize_req_print(window)
        return {'x': 0, 'y': 0, 'rows': 0, 'cols': 0}


def animation_prompt(window, heap, snap, cords):
    curr_snap = snap

    # set non_blocking window.getch()
    window.nodelay(1)

    while True:
        window.hline(curses.LINES - 1, 0, ' ', curses.COLS - 1)
        animation_menu_print(window)
        window.refresh()

        curses.napms(1000)

        if curr_snap < heap['max']:
            curr_snap += 1
            cords.update(redraw_heap_map(window, heap, curr_snap))

        key = window.getch()
        if key in (ord('q'), ord('Q')):
            # printing menu to the console window
            window.hline(curses.LINES - 1, 0, ' ', curses.COLS - 1)
            menu_print(window)
            window.refresh()
            window.move(cords['x'], cords['y'])
            break
        elif key in (ord('r'), ord('R')):
            curr_snap = 0
        elif key in (ord('s'), ord('S')):
            while window.getch() not in (ord('c'), ord('C')):
                menu = '[C] CONTINUE'
                window.addstr(curses.LINES - 1, (curses.COLS - len(menu)) // 2,
                              menu, curses.A_BOLD)
                window.refresh()

    while window.getch() != -1:
        pass

    window.nodelay(0)

    return curr_snap


def another_snapshot(current_snap, next_snap, window, heap, cords):

    if next_snap == NEXT_SNAPSHOT:
        if current_snap < heap['max']:
            current_snap += next_snap
        else:
            return current_snap

    elif next_snap == PREV_SNAPSHOT:
        if current_snap > 1:
            current_snap += next_snap
        else:
            return current_snap

    cords.update(redraw_heap_map(window, heap, current_snap))

    # printing menu to the console window
    menu_print(window)

    window.move(cords['x'], cords['y'])

    return current_snap


def heap_map_prompt(window, heap):
    """ Visualization prompt
    Arguments:
        window(any): initialized console window
        heap(dict): heap map representation
    """
    current_snapshot = 0
    screen_cords = {'x': 0, 'y': 0, 'rows': 0, 'cols': 0}

    init_curses_colors()

    # set cursor invisible
    curses.curs_set(2)
    # INTRO screen
    intro_print(window)
    window.refresh()
    # just for effect :)
    curses.napms(700)

    current_snapshot = another_snapshot(current_snapshot, NEXT_SNAPSHOT,
                                        window, heap, screen_cords)

    while True:
        key = window.getch()

        if key == ord('q') or key == ord('Q'):
            break
        elif key == curses.KEY_LEFT:
            current_snapshot = another_snapshot(current_snapshot,
                                                PREV_SNAPSHOT,
                                                window, heap, screen_cords)
        elif key == curses.KEY_RIGHT:
            current_snapshot = another_snapshot(current_snapshot,
                                                NEXT_SNAPSHOT,
                                                window, heap, screen_cords)
        elif key == ord('a') or key == ord('A'):
            current_snapshot = animation_prompt(window, heap,
                                                current_snapshot, screen_cords)
        elif key == ord('4'):
            curr_xy = window.getyx()
            if (curr_xy[1] - screen_cords['y']) > 0:
                window.move(curr_xy[0], curr_xy[1] - 1)
        elif key == ord('6'):
            curr_xy = window.getyx()
            if (curr_xy[1] - screen_cords['y']) < screen_cords['cols'] - 1:
                window.move(curr_xy[0], curr_xy[1] + 1)
        elif key == ord('8'):
            curr_xy = window.getyx()
            if (curr_xy[0] - screen_cords['x']) > 0:
                window.move(curr_xy[0] - 1, curr_xy[1])
        elif key == ord('5'):
            curr_xy = window.getyx()
            if (curr_xy[0] - screen_cords['x']) < screen_cords['rows'] - 1:
                window.move(curr_xy[0] + 1, curr_xy[1])
        elif key == curses.KEY_RESIZE:
            current_snapshot = another_snapshot(current_snapshot,
                                                0,
                                                window, heap, screen_cords)


def heap_map(profile):
    """ Prepare the heap map to visualization and call curses wrapper

        Wrapper initialize terminal,
        turn off automatic echoing of keys to the screen,
        turn reacting to keys instantly
        (without requiring the Enter key to be pressed) on,
        enable keypad mode for special keys s.a. HOME.

    Arguments:
        profile(dict): the memory profile

    Returns:
        string: message informing about operation success
    """
    # preparing heap map representation
    heap = create_heap_map_representation(profile)

    # after integration remove try block
    try:
        # call heap map visualization prompt in curses wrapper
        curses.wrapper(heap_map_prompt, heap)
    except curses.error as error:
        print('Screen too small!', file=sys.stderr)
        print(str(error), file=sys.stderr)


def create_heap_map_representation(profile):
    """ Create the heap map representation for visualization
    Arguments:
        profile(dict): the memory profile

    Returns:
        dict: the heap map representation

    Format of the heap map representation is following:
        {"max": number of snapshots taken (int),
         "unit": used memory unit (string),
         "stats": { # same stats like for each snapshots but calculated
                    # over all the snapshots
                    # (except sum_amount -> doesn't make sense)
                    }
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
                 "type": type of the allocation ("allocation"/"free")
                 "uid": {uid of the function which made the allocation
                    "line": (int),
                    "function": (string),
                    "source": (string)
                 }
                }
             ]
            }
         ]
        }
    """
    snapshots = [a for a in profile['snapshots']]

    # modifying the memory profile to heap map representation
    for snap in snapshots:
        snap['map'] = get_map(snap['resources'])
        del snap['resources']

    # calculating existing allocations for each snapshot
    calculate_heap_map(snapshots)
    # adding statistics about each snapshot
    glob_stats = add_stats(snapshots)

    return {'snapshots': snapshots,
            'max': len(snapshots),
            'stats': glob_stats,
            'unit': profile['header']['units']['memory']}


def get_map(resources):
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
    new_allocations = []
    existing_allocations = []
    for snap in snapshots:

        for m in snap['map']:
            if m['type'] == 'free':
                alloc = next((x for x in new_allocations
                              if x['address'] == m['address']), None)
                if alloc:
                    new_allocations.remove(alloc)

                # removing free record
                snap['map'].remove(m)
            else:
                new_allocations.append(m)

        # extending existing allocations from previous to the current snapshot
        snap['map'].extend(existing_allocations)
        existing_allocations = new_allocations.copy()


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
    glob_sum_amount = []
    glob_max_amount = []
    glob_min_amount = []

    for snap in snapshots:
        if not len(snap['map']):
            snap['max_address'] = 0
            snap['min_address'] = 0
            snap['sum_amount'] = 0
            snap['max_amount'] = 0
            snap['min_amount'] = 0
        else:
            snap['max_address'] = max(item.get('address', 0) + item.get('amount', 0)
                                  for item in snap['map'])
            snap['min_address'] = min(item.get('address', 0) for item in snap['map'])
            snap['sum_amount'] = sum(item.get('amount', 0) for item in snap['map'])
            snap['max_amount'] = max(item.get('amount', 0) for item in snap['map'])
            snap['min_amount'] = min(item.get('amount', 0) for item in snap['map'])

        glob_max_address.append(snap['max_address'])
        glob_min_address.append(snap['min_address'])
        glob_max_amount.append(snap['max_amount'])
        glob_min_amount.append(snap['min_amount'])

    return {'max_address': max(glob_max_address),
            'min_address': min(glob_min_address),
            'max_amount': max(glob_max_amount),
            'min_amount': min(glob_min_amount)
            }


if __name__ == "__main__":
    with open("memory.perf") as prof_json:
        heap_map(json.load(prof_json))
