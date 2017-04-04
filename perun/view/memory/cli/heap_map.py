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
CURR_SNAPSHOT = 0
MIN_ROWS = 30
MIN_COLS = 70


class HeapMapColors(object):
    __good_colors = (
        1, 2, 3, 4, 5, 6, 7, 11, 14, 17, 21, 19, 22, 23, 27, 33, 30, 34, 45,
        41, 46, 49, 51, 52, 54, 56, 58, 59, 62, 65, 71, 76, 89, 91, 94, 95,
        124, 125, 126, 127, 129, 130, 131, 154, 156, 159, 161, 166, 167, 178,
        195, 197, 199, 203, 208, 210, 211, 214, 220, 226, 229, 255)
    # structure for saving corresponding allocation
    # with their specific color representation
    __color_records = []
    __good_colors_number = 0

    border_color = 1
    free_field_color = 2
    info_color = 3

    @classmethod
    def init_curses_colors(cls):
        """ Initialize colors used later in heap map """
        # 16 == black
        # -1 == implicit color

        curses.start_color()
        curses.use_default_colors()

        start_pair_number = 1
        for i in cls.__good_colors:
            curses.init_pair(start_pair_number, 16, i)
            start_pair_number += 1

        cls.__good_colors_number = start_pair_number - 1
        # border color
        curses.init_pair(start_pair_number, 16, 16)
        cls.border_color = start_pair_number
        start_pair_number += 1
        # free field color
        curses.init_pair(start_pair_number, -1, 8)
        # excel
        curses.init_pair(start_pair_number, 16, 7)
        cls.free_field_color = start_pair_number
        start_pair_number += 1
        # snapshot info color
        curses.init_pair(start_pair_number, -1, 16)
        cls.info_color = start_pair_number


    @classmethod
    def get_field_color(cls, field):
        if field['uid'] is None:
            return cls.free_field_color

        uid = field['uid']
        for item in cls.__color_records:
            if (uid['function'] == item['uid']['function'] and
                        uid['source'] == item['uid']['source']):
                return item['color']

        color = randint(1, cls.__good_colors_number)
        cls.__color_records.append({'uid': uid, 'color': color})

        return color


def show_intro(window):
    """ Print INTRO screen about HEAP MAP visualization
    Arguments:
        window(any): initialized console window
    """
    text = "HEAP MAP!"

    window.addstr(curses.LINES // 2, (curses.COLS - len(text))//2,
                  text, curses.A_BOLD)
    window.refresh()
    # just for effect :)
    curses.napms(700)


def resize_req_print(window):
    """ Print resize request to the window
    Arguments:
        window(any): initialized console window
    """
    resize_req = "Increase the size of your screen, please"

    window.addstr(curses.LINES // 2, (curses.COLS - len(resize_req)) // 2,
                  resize_req)


def menu_print(window, is_animation=False):
    """ Print menu or animation menu information to the window
    Arguments:
        window(any): initialized console window
    """
    menu = '[Q] QUIT  [<] PREVIOUS  [>] NEXT  [A] ANIMATE' \
           '  [4|8|6|5] CURSOR L|U|R|D'
    if is_animation:
        menu = '[S] STOP  [P] PAUSE  [R] RESTART'

    window.addstr(curses.LINES - 1, (curses.COLS - len(menu)) // 2,
                  menu, curses.A_BOLD)


def info_print(window, max_snap, curr, margin):
    """ Print the heap information to the window
    Arguments:
        window(any): initialized console window
        max_snap(int): total number of the snapshots
        curr(int): number of the current snapshot
        margin(int): left margin
    """
    info_text = 'SNAPSHOT: ' + str(curr) + '/' + str(max_snap)
    window.addstr(0, (curses.COLS - len(info_text) - margin) // 2 + margin,
                  info_text,
                  curses.color_pair(HeapMapColors.info_color))


def create_screen_decomposition(heap, curr, rows, cols):
    """ Create a matrix with corresponding representation of the snapshot
    Arguments:
        heap(dict): heap map representation
        curr(int): number of the current snapshot
        rows(int): total number of the screen's rows
        cols(int): total number of the screen's columns

    Returns:
        dict: matrix representing screen's decomposition and size of the field
    """
    snap = heap['snapshots'][curr - 1]

    # calculating approximated field size
    add_range = heap['stats']['max_address'] - heap['stats']['min_address']
    field_size = add_range / (rows * cols)

    matrix = [[None for _ in range(cols)] for _ in range(rows)]

    allocations = snap['map']
    # sorting allocations records by frequency of allocations
    allocations.sort(key=lambda x: x['address'])
    iterator = iter(allocations)

    record = next(iterator, None)
    # set starting address to first approx field
    last_field = heap['stats']['min_address']
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
                last_field += field_size

    return {"data": matrix, "field_size": field_size,
            "rows": rows, "cols": cols}


def matrix_print(window, map, rows, cols, add_length, unit):
    """ Prints the screen representation matrix to the window
    Arguments:
        window(any): initialized console window
        map(dict): representation information
        rows(int): total number of the screen's rows
        cols(int): total number of the screen's columns
        add_length(int): length of the maximal address
    """
    # border_sym = u"\u2588"
    border_sym = ' '
    field_sym = '_'
    tik_field_sym = '|'
    tik_freq = 10
    tik_amount = int(map['field_size'] * tik_freq)

    # calculating address range on one line
    address = map['data'][0][0]['address']
    line_address_size = int(map['cols'] * map['field_size'])

    for row in range(rows):
        # address info printing calculated from 1st and field size (approx)
        if row not in (0, rows-1):
            address_string = str(address)
            if len(address_string) < add_length:
                address_string += border_sym*(add_length - len(address_string))
            address += line_address_size
        elif row == 0:
            address_string = "ADDRESS:"
            if len(address_string) < add_length:
                address_string += border_sym * \
                                  (add_length - len(address_string))
        else:
            address_string = border_sym*(add_length)
        window.addnstr(row, 0, address_string, len(address_string),
                       curses.color_pair(HeapMapColors.info_color))

        tik_counter = 0
        for col in range(add_length, cols):
            # border printing
            if col in (add_length, cols-1) or row in (0, rows-1):
                window.addch(row, col, border_sym,
                             curses.color_pair(HeapMapColors.border_color))

            # field printing
            else:
                field = map['data'][row - 1][col - add_length - 1]
                color = HeapMapColors.get_field_color(field)
                if tik_counter % tik_freq == 0:
                    symbol = tik_field_sym
                elif row == rows-2:
                    symbol = border_sym
                else:
                    symbol = field_sym
                window.addstr(row, col, symbol, curses.color_pair(color))

            tik_counter += 1

    # adding tik amount info
    tik_amount_str = ''
    for col in range(add_length, cols, tik_freq):
        if tik_freq >= cols - col:
            break
        tik_amount_str += str(tik_amount) + unit
        tik_amount_str += border_sym*(tik_freq - len(str(tik_amount) + unit))


    window.addstr(rows-1, add_length + 1, tik_amount_str,
                  curses.color_pair(HeapMapColors.info_color))


def redraw_heap_map(window, heap, snap):
    """ Redraw the heap map screen to represent the specified snapshot
    Arguments:
        window(any): initialized console window
        heap(dict): heap map representation
        snap(int): number of the snapshot to represent

    Returns:
        dict: cursor's screen coordinates
    """
    curses.update_lines_cols()
    window.clear()

    # calculate space for the addresses information
    max_add_len = len(str(heap['stats']['max_address']))
    if max_add_len < len('ADDRESS:'):
        max_add_len = len('ADDRESS:')

    # check for the minimal screen size
    if curses.LINES < MIN_ROWS or (curses.COLS - max_add_len) < MIN_COLS:
        return None

    # number of the screen's rows == (minimum of rows) - (2*border field)
    map_rows = MIN_ROWS - 2
    # number of the screen's columns == (terminal's current number of
    # the columns) - (size of address info - 2*border field)
    map_cols = curses.COLS - max_add_len - 2
    # creating the heap map screen decomposition
    decomposition = create_screen_decomposition(heap, snap, map_rows, map_cols)
    assert decomposition

    try:
        # printing heap map decomposition to the console window
        matrix_print(window, decomposition,
                     MIN_ROWS, curses.COLS, max_add_len, heap['unit'])
        # printing heap info to the console window
        info_print(window, heap['max'], snap, max_add_len)

        return {'row': 1, 'col': max_add_len + 1,
                'map': decomposition}

    except curses.error:
        return None


def animation_prompt(window, heap, snap, cords):
    """ Handle animation feature of the HEAP MAP visualization
    Arguments:
        window(any): initialized console window
        heap(dict): heap map representation
        snap(int): number of the current snapshot
        cords(dict): Heap map's screen

    Returns:
        int: number of the current snapshot
    """
    curr_snap = snap

    # set non_blocking window.getch()
    window.nodelay(1)

    while True:
        # redraw standard MENU text with ANIMATION MENU text
        window.hline(curses.LINES - 1, 0, ' ', curses.COLS - 1)
        menu_print(window, True)
        window.refresh()

        # delay between individually heap map screens
        curses.napms(1000)
        key = window.getch()

        if curr_snap < heap['max']:
            curr_snap += 1
            map = redraw_heap_map(window, heap, curr_snap)
            if map is None:
                window.clear()
                resize_req_print(window)
                cords.update({'map': None})
            else:
                cords.update(map)

        if key in (ord('s'), ord('S')):
            # redraw ANIMATION MENU text with standard MENU text
            window.hline(curses.LINES - 1, 0, ' ', curses.COLS - 1)
            menu_print(window)
            window.refresh()
            # set cursor's position to the upper left corner of the heap map
            window.move(cords['row'], cords['col'])
            break
        # restart animation from the 1st snapshot
        elif key in (ord('r'), ord('R')):
            curr_snap = 0
        # stop animation until 'C' key is pressed
        elif key in (ord('p'), ord('P')):
            while window.getch() not in (ord('c'), ord('C')):
                menu = '[C] CONTINUE'
                window.addstr(curses.LINES - 1, (curses.COLS - len(menu)) // 2,
                              menu, curses.A_BOLD)
                window.refresh()
        # change of the screen size occurred
        elif key == curses.KEY_RESIZE:
            map = redraw_heap_map(window, heap, curr_snap)
            if map is None:
                window.clear()
                resize_req_print(window)
                cords.update({'map': None})
            else:
                cords.update(map)

    # empty buffer window.getch()
    while window.getch() != -1:
        pass
    # set blocking window.getch()
    window.nodelay(0)

    return curr_snap


def following_snapshot(current_snap, following_snap, window, heap, cords):
    """ Set following snapshot to print
    Arguments:
        current_snap(int): number of the current snapshot
        following_snap(int): number of the following snapshot
        window(any): initialized console window
        heap(dict): heap map representation
        cords(dict): Heap map's screen

    Returns:
        int: number of the current snapshot
    """
    if following_snap == NEXT_SNAPSHOT:
        if current_snap < heap['max']:
            current_snap += following_snap
        else:
            return current_snap

    elif following_snap == PREV_SNAPSHOT:
        if current_snap > 1:
            current_snap += following_snap
        else:
            return current_snap

    # draw heap map
    map = redraw_heap_map(window, heap, current_snap)
    if map is None:
        window.clear()
        resize_req_print(window)
        cords.update({'map': None})
    else:
        cords.update(map)
        # printing menu to the console window
        menu_print(window)
        # set cursor's position to the upper left corner of the heap map
        window.move(cords['row'], cords['col'])

    return current_snap


def cursor_move(window, direction, cords):
    """ Move the cursor to the new position defined by direction
    Arguments:
        window(any): initialized console window
        direction(any): character returned by curses.getch()
        cords(dict): Heap map's screen
    """
    # current cursor's position
    row_col = window.getyx()

    if direction == ord('4'):
        if row_col[1] - cords['col'] > 0:
            window.move(row_col[0], row_col[1] - 1)
    elif direction == ord('6'):
        if row_col[1] - cords['col'] < cords['map']['cols'] - 1:
            window.move(row_col[0], row_col[1] + 1)
    elif direction == ord('8'):
        if row_col[0] - cords['row'] > 0:
            window.move(row_col[0] - 1, row_col[1])
    elif direction == ord('5'):
        if row_col[0] - cords['row'] < cords['map']['rows'] - 1:
            window.move(row_col[0] + 1, row_col[1])


def print_field_info(window, cords, unit):

    if cords['map'] is None:
        return
    # current cursor's position
    row_col = window.getyx()
    matrix_row = row_col[0] - cords['row']
    matrix_col = row_col[1] - cords['col']

    try:
        data = cords['map']['data'][matrix_row][matrix_col]
        if data['uid'] is None:
            info = "TODO global"
        else:
            info = "Starting address: " + str(data['address']) + '\n'
            info += "Allocated space: " + str(data['amount']) + ' ' + unit + '\n'
            info += "Allocation: " + str(data['uid'])
    except KeyError:
        info = ''

    window.addstr(cords['map']['rows']+5, 0, info)

    window.move(*row_col)


def heap_map_prompt(window, heap):
    """ Visualization prompt

        Heap map's screen is represented by dictionary as follow:
        {'col': X coordinate of upper left corner of the map (int),
         'row': Y coordinate of upper left corner of the map (int),
         'map':{
            'rows': number of map's rows (int),
            'cols': number of map's columns (int),
            'data': matrix with map's data
          }
         }

        Coordinate space is 0---->X
                            |
                            |
                            |
                            Y

    Arguments:
        window(any): initialized console window
        heap(dict): heap map representation
    """
    current_snapshot = 0
    # initialize the screen's information
    screen_cords = {'row': 0, 'col': 0, 'map': {}}
    # initialize colors which will be used
    HeapMapColors.init_curses_colors()
    # set cursor visible
    curses.curs_set(2)

    show_intro(window)
    # print 1st snapshot's heap map
    current_snapshot = following_snapshot(current_snapshot, NEXT_SNAPSHOT,
                                          window, heap, screen_cords)
    print_field_info(window, screen_cords, heap['unit'])
    while True:
        # catching key value
        key = window.getch()

        # quit of the visualization
        if key in (ord('q'), ord('Q')):
            break
        # previous snapshot
        elif key == curses.KEY_LEFT:
            current_snapshot = following_snapshot(current_snapshot,
                                                  PREV_SNAPSHOT,
                                                  window, heap,
                                                  screen_cords)
        # next snapshot
        elif key == curses.KEY_RIGHT:
            current_snapshot = following_snapshot(current_snapshot,
                                                  NEXT_SNAPSHOT,
                                                  window, heap,
                                                  screen_cords)
        # start of the animation
        elif key in (ord('a'), key == ord('A')):
            current_snapshot = animation_prompt(window, heap,
                                                current_snapshot,
                                                screen_cords)
        # cursor moved
        elif key in (ord('4'), ord('6'), ord('8'), ord('5')):
            cursor_move(window, key, screen_cords)
        # change of the screen size occurred
        elif key == curses.KEY_RESIZE:
            current_snapshot = following_snapshot(current_snapshot,
                                                  CURR_SNAPSHOT,
                                                  window, heap, screen_cords)

        print_field_info(window, screen_cords, heap['unit'])


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
        if not res['uid']:
            continue
        map_item['uid'] = res['uid']
        if res['subtype'] == 'free':
            map_item['type'] = 'free'
        else:
            map_item['type'] = 'allocation'

        simple_map.append(map_item)

    return simple_map

# TODO Remove useless allocation['type']
def calculate_heap_map(snapshots):
    """ Will calculate existing allocations for each snapshot

        Result is in the form of modified input argument.

    Arguments:
        snapshots(list): list of snapshots
    """
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
                new_allocations.append(allocation)

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
