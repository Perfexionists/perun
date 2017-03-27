"""This module implement the heap map visualization of the profile"""
import json
import time
import curses
import curses.textpad
from random import randint

__author__ = 'Radim Podola'
MIN_ROWS = 30
MIN_COLS = 70
COLOR_BORDER = 1
COLOR_FREE_FIELD = 2
COLOR_SNAPSHOT_INFO = 3


def init_curses_colors():
    curses.start_color()
    curses.use_default_colors()

    # border color
    curses.init_pair(COLOR_BORDER, 16, -1)
    curses.init_pair(COLOR_FREE_FIELD, curses.COLOR_BLACK, -1)
    curses.init_pair(COLOR_SNAPSHOT_INFO, curses.COLOR_WHITE, 16)

    for i in range(4, curses.COLORS):
        curses.init_pair(i, i, -1)


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

    window.addstr(int(curses.LINES / 2), int((curses.COLS - len(intro))/2),
                  intro, curses.A_BOLD)


def menu_print(window):
    """ Print menu information to the window
    Arguments:
        window(any): console window
    """
    menu = '[Q] QUIT  [<] PREVIOUS  [>] NEXT  [A] ANIMATE  [S] SAVE'

    window.addstr(curses.LINES - 1, int((curses.COLS - len(menu)) / 2),
                  menu, curses.A_BOLD)


def info_print(window, max, curr, indent):
    """ Print the heap information to the window
    Arguments:
        window(any): console window
        max(int): total number of the snapshots
        curr(int): number of the current snapshot
    """
    info_text = 'SNAPSHOT: ' + str(curr) + '/' + str(max)
    window.addstr(0, int((curses.COLS - len(info_text)) / 2) + indent,
                  info_text, curses.color_pair(COLOR_SNAPSHOT_INFO))


def create_screen_matrix(rows, cols):
    """ Create a matrix for rows and columns
    Arguments:
        rows(int): number of the rows in a matrix
        cols(int): number of the columns in a matrix

    Returns:
        list: created 2D matrix for rows and cols
    """
    # creating screen matrix x_size X y_size
    screen_matrix = [[None for y in range(cols)] for x in range(rows)]

    return screen_matrix


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


    data = [[{"uid": None, "address": x+y} for y in range(cols)] for x in range(rows)]
    data[0][cols-1] = {"uid": {"function": 'f1', "source": 's1'}, "address": 80}
    data[27][2] = {"uid": {"function": 'f1', "source": 's1'}, "address": 800}
    data[25][2] = {"uid": {"function": 'f2', "source": 's1'}, "address": 800}
    data[25][3] = {"uid": {"function": 'f2', "source": 's1'}, "address": 800}
    return {'map':data}


def matrix_print(window, data, rows, cols, add_length):
    """ Prints the matrix to the window
    Arguments:
        window(any): console window
        data(list): data to print
    """
    field_sym = u"\u2588"
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
                            'color': randint(2, curses.COLORS)})
        return color_records[-1]['color']


    for row in range(rows):
        # address info printing
        if row not in (0, rows-1):
            window.addstr(row, 0, str(data['map'][row - 1][0]['address']))

        for col in range(add_length, cols):
            # border printing
            if row in (0, rows-1):
                window.addch(row, col, field_sym, curses.color_pair(COLOR_BORDER))
            elif col in (add_length, cols-1):
                window.addch(row, col, field_sym, curses.color_pair(COLOR_BORDER))
            # filed printing
            else:
                field = data['map'][row - 1][col - add_length - 1]
                color = get_field_color(field, color_records)
                window.addch(row, col, field_sym, curses.color_pair(color))


def redraw_heap_map(window, heap, snapshot):
    curses.update_lines_cols()
    window.clear()

    if curses.LINES < MIN_ROWS or curses.COLS < MIN_COLS:
        window.clear()
        resize_req_print(window)
        menu_print(window)
        window.refresh()
        return 0, 0

    try:
        # max_add_len = len(str(heap['snapshots'][snapshot - 1]['max_address']))
        max_add_len = 4
        add_info_len = max_add_len + 2
        # number of matrix rows == minimum of rows - 2*border field
        map_rows = MIN_ROWS - 2
        # number of matrix cols == terminal current cols - size of address info - 2*border field
        map_cols = curses.COLS - add_info_len - 2
        # getting heap map decomposition
        decomposition = create_screen_decomposition(heap, snapshot,
                                                    map_rows, map_cols)
        # printing heap map decomposition to the console window
        matrix_print(window, decomposition, MIN_ROWS, curses.COLS, add_info_len)
        # printing heap info to the console window
        info_print(window, heap['max'], snapshot, add_info_len)
        # printing menu to the console window
        menu_print(window)

        window.move(1, max_add_len+3)
        return map_rows, map_cols

    except curses.error:
        window.clear()
        resize_req_print(window)
        menu_print(window)
        return 0, 0


def heap_map_prompt(window, heap):
    """ Visualization prompt
    Arguments:
        window(any): initialized console window
        heap(dict): heap map representation
    """
    current_snapshot = 1

    init_curses_colors()
    # set cursor invisible
    curses.curs_set(2)
    # INTRO screen
    intro_print(window)
    window.refresh()
    # just for effect :)
    time.sleep(1)

    rows, cols = redraw_heap_map(window, heap, current_snapshot)
    start_xy = window.getyx()
    while True:
        key = window.getch()

        if key == ord('q') or key == ord('Q'):
            break
        elif key == curses.KEY_LEFT:
            if current_snapshot > 1:
                current_snapshot -= 1
                rows, cols = redraw_heap_map(window, heap, current_snapshot)
                start_xy = window.getyx()
        elif key == curses.KEY_RIGHT:
            if current_snapshot < heap['max']:
                current_snapshot += 1
                rows, cols = redraw_heap_map(window, heap, current_snapshot)
                start_xy = window.getyx()
        elif key == ord('s') or key == ord('S'):
            pass
        elif key == ord('a') or key == ord('A'):
            pass
        elif key == ord('4'):
            curr_xy = window.getyx()
            if (curr_xy[1] - start_xy[1]) > 0:
                window.move(curr_xy[0], curr_xy[1] - 1)
        elif key == ord('6'):
            curr_xy = window.getyx()
            if (curr_xy[1] - start_xy[1]) < cols-1:
                window.move(curr_xy[0], curr_xy[1] + 1)
        elif key == ord('8'):
            curr_xy = window.getyx()
            if (curr_xy[0] - start_xy[0]) > 0:
                window.move(curr_xy[0] - 1, curr_xy[1])
        elif key == ord('5'):
            curr_xy = window.getyx()
            if (curr_xy[0] - start_xy[0]) < rows-1:
                window.move(curr_xy[0] + 1, curr_xy[1])
        elif key == curses.KEY_RESIZE:
            rows, cols = redraw_heap_map(window, heap, current_snapshot)
            start_xy = window.getyx()


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
        print(str(error))


def create_heap_map_representation(profile):
    """ Create the heap map representation for visualization
    Arguments:
        profile(dict): the memory profile

    Returns:
        dict: the heap map representation

    Format of the heap map representation is following:
        {"max": number of snapshots taken (int),
         "unit": used memory unit (string),
         "snapshots": [
            {"time": time of the snapshot (string),
             "max_amount": maximum amount of the allocated memory
                           in snapshot (int),
             "min_amount": minimum amount of the allocated memory
                           in snapshot (int),
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
    add_stats(snapshots)

    return {'snapshots': snapshots,
            'max': len(snapshots),
            'unit': profile['header']['units']['memory']}


def get_map(resources):
    """ Parse resources from the memory profile to simpler representation
    Arguments:
        resources(list): list of the resources from the memory profile

    Returns:
        list: list of the simple allocations records
    """
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
    """ Add statistic about each snapshot

        Maximum amount of the allocated memory,
        minimum amount of the allocated memory,
        summary of the amount of the allocated memory,
        maximal address of the allocated memory,
        minimal address of the allocated memory.

        Result is in the form of modified input argument.

    Arguments:
        snapshots(list): list of snapshots
    """
    for snap in snapshots:
        snap['max_address'] = max(item.get('address', 0) for item in snap['map'])

        snap['min_address'] = min(item.get('address', 0) for item in snap['map'])

        snap['sum_amount'] = sum(item.get('amount', 0) for item in snap['map'])

        snap['max_amount'] = max(item.get('amount', 0) for item in snap['map'])

        snap['min_amount'] = min(item.get('amount', 0) for item in snap['map'])


if __name__ == "__main__":
    with open("memory.perf") as prof_json:
        heap_map(json.load(prof_json))
