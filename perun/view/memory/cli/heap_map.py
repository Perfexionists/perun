"""This module implement the heap map visualization of the profile"""
import sys
import json
import time
import curses
import curses.textpad

__author__ = 'Radim Podola'
MIN_WIDTH = 80


def fill_screen_matrix(matrix, heap, curr):
    """ Fill the matrix with corresponding representation of snapshot
    Arguments:
        matrix(list): matrix to update
        heap(dict): heap map representation
        curr(int): number of the current snapshot

    Returns:
        list: updated matrix
    """
    for row, _ in enumerate(matrix):
        for col, _ in enumerate(matrix[row]):
            if row == 20 and col == 15:
                matrix[row][col] = {'char': '5', 'color': 2}
            else:
                matrix[row][col] = {'char': '+', 'color': 1}


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


def info_print(window, max, curr):
    """ Print the heap information to the window
    Arguments:
        window(any): console window
        max(int): total number of the snapshots
        curr(int): number of the current snapshot
    """
    info_text = 'SNAPSHOT: ' + str(curr) + '/' + str(max)
    rows, cols = window.getmaxyx()
    window.addstr(' '*int((cols - len(info_text))/2))
    window.addstr(info_text, curses.color_pair(11))
    window.addch('\n')


def matrix_print(window, matrix, border='#'):
    """ Prints the matrix to the window
    Arguments:
        window(any): console window
        matrix(list): matrix to print
        border(char): border symbol
    """
    assert len(border) < 2
    border_size = len(border)

    if border_size > 0:
        x_border_size, y_border_size = len(matrix) + 2, len(matrix[0]) + 2

        for row in range(x_border_size):
            for col in range(y_border_size):
                if (row in (0, x_border_size-border_size) or
                            col in (0, y_border_size-border_size)):
                    window.addch(row, col, border, curses.color_pair(10))
                else:
                    field = matrix[row - border_size][col - border_size]
                    window.addch(row, col, field['char'],
                                 curses.color_pair(field['color']))

    else:
        for row, _ in enumerate(matrix):
            for col, _ in enumerate(matrix[row]):
                window.addch(row, col, matrix[row][col])


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


def heap_map_prompt(window, heap):
    """ Visualization prompt
    Arguments:
        window(any): initialized console window
        heap(dict): heap map representation
    """
    curses.start_color()
    curses.use_default_colors()
    for i in range(0, curses.COLORS):
        curses.init_pair(i + 1, i, -1)
    curses.init_pair(10, curses.COLOR_RED, curses.COLOR_RED)
    curses.init_pair(11, curses.COLOR_YELLOW, -1)
    curses.init_pair(1, -1, curses.COLOR_GREEN)
    curses.init_pair(2, -1, curses.COLOR_MAGENTA)
    # set cursor invisible
    curses.curs_set(1)
    # INTRO screen
    intro_print(window)
    window.refresh()
    # just for effect :)
    time.sleep(1)

    curses.update_lines_cols()
    # temporary default values
    rows, cols = 40, curses.COLS-2
    current_snapshot = 1

    while True:
        curses.update_lines_cols()
        if curses.COLS > MIN_WIDTH:
            cols = curses.COLS - 2
        window.clear()
        try:
            # creating matrix
            screen_matrix = create_screen_matrix(rows, cols)
            # filling matrix with s heap information
            fill_screen_matrix(screen_matrix, heap, current_snapshot)
            # printing matrix to the console window
            matrix_print(window, screen_matrix)
            # printing heap info to the console window
            info_print(window, heap['max'], current_snapshot)
            # printing menu to the console window
            menu_print(window)
        except curses.error:
            window.clear()
            resize_req_print(window)
            menu_print(window)

        window.refresh()
        key = window.getch()
        if key == ord('q') or key == ord('Q'):
            break
        elif key == curses.KEY_LEFT:
            if current_snapshot > 1:
                current_snapshot -= 1
        elif key == curses.KEY_RIGHT:
            if current_snapshot < heap['max']:
                current_snapshot += 1
        elif key == ord('s') or key == ord('S'):
            pass
        elif key == ord('a') or key == ord('A'):
            pass


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
        maximal address of the allocated memory,
        minimal address of the allocated memory.

        Result is in the form of modified input argument.

    Arguments:
        snapshots(list): list of snapshots
    """
    for snap in snapshots:
        max_address_item = max(snap['map'], key=lambda x: x['address'])
        snap['max_address'] = max_address_item['address']

        min_address_item = min(snap['map'], key=lambda x: x['address'])
        snap['min_address'] = min_address_item['address']

        max_amount_item = max(snap['map'], key=lambda x: x['amount'])
        snap['max_amount'] = max_amount_item['amount']

        min_amount_item = min(snap['map'], key=lambda x: x['amount'])
        snap['min_amount'] = min_amount_item['amount']


if __name__ == "__main__":
    with open("memory.perf") as prof_json:
        heap_map(json.load(prof_json))
