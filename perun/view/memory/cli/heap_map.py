"""This module implement the heap map visualization of the profile"""
import json
import time
import curses
import curses.textpad

__author__ = 'Radim Podola'


INTRO = "HEAP MAP!"
MENU = '[Q] QUIT  [<] PREVIOUS  [>] NEXT  [A] ANIMATE  [S] SAVE'
RESIZE_REQ = "Resize screen up, please"


def fill_screen_matrix(matrix, snap):
    """ Fill matrix with corresponding representation of snapshot
    Arguments:
        matrix(list): matrix to update
        snap(dict): snapshot to represent

    Returns:
        list: updated matrix
    """
    pass


def matrix_to_string(matrix):
    """ Transfer matrix to the string representation
    Arguments:
        matrix(list): matrix to transfer

    Returns:
        string: transferred matrix
    """
    str_matrix = ''

    for x, _ in enumerate(matrix):
        for y, _ in enumerate(matrix[x]):
            str_matrix += matrix[x][y]
        str_matrix += '\n'

    return str_matrix


def create_screen_matrix(rows, cols, symbol='+', border='#'):
    """ Create a matrix for rows and columns placed in a border
    Arguments:
        rows(int): number of the rows in a matrix
        cols(int): number of the columns in a matrix
        symbol(char): symbol which is the screen filled with
        border(char): border symbol

    Returns:
        list: created 2D matrix for rows and cols placed in a border
    """
    assert len(symbol) == 1
    assert len(border) == 1
    border_size = 1
    x_size, y_size = rows + 2*border_size, cols + 2*border_size

    # creating screen matrix x_size X y_size
    screen_matrix = [[symbol for y in range(y_size)] for x in range(x_size)]

    if border_size > 0:
        for x in range(x_size):
            for y in range(y_size):
                if x in (0, x_size - border_size) or \
                                y in (0, y_size - border_size):
                    screen_matrix[x][y] = border

    return screen_matrix


def heap_map_prompt(window, heap):
    """ Visualization prompt
    Arguments:
        window(any): initialized curses screen
        heap(dict): heap map representation
    """
    curses.use_default_colors()
    # set cursor invisible
    curses.curs_set(0)
    # INTRO screen
    window.addstr(int(curses.LINES / 2),
                  int((curses.COLS - len(INTRO))/2),
                  INTRO, curses.A_BOLD)
    window.refresh()
    # just for effect :)
    time.sleep(1)

    # temporary default values
    rows, cols = 40, 100
    current_snapshot = 1

    while True:
        curses.update_lines_cols()
        window.clear()
        try:
            screen_matrix = create_screen_matrix(rows, cols)
            fill_screen_matrix(screen_matrix,
                               heap['snapshots'][current_snapshot - 1])
            window.addstr(curses.LINES - rows - 2 - 1, 0,
                          matrix_to_string(screen_matrix))
            map_text = ' SNAPSHOT: ' + str(current_snapshot) + '/' + str(heap['max']) + ' '
            window.addstr(curses.LINES - rows - 2 - 1,
                          int((cols + 2 - len(map_text))/2),
                          map_text)
            window.addstr(curses.LINES - 1,
                          int((curses.COLS - len(MENU))/2),
                          MENU, curses.A_BOLD)
        except curses.error:
            window.clear()
            window.addstr(int(curses.LINES / 2),
                          int((curses.COLS - len(RESIZE_REQ))/2),
                          RESIZE_REQ)
            window.addstr('\n')
            window.addstr(curses.LINES - 1,
                          int((curses.COLS - len(MENU))/2),
                          MENU, curses.A_BOLD)

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
