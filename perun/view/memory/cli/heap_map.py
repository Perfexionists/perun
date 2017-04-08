"""This module implement the heap map visualization of the profile"""
import curses
import curses.textpad
import json
import sys
from random import randint

# import perun.view.memory.cli.heap_representation as heap_representation
# debug in console
import heap_representation as heap_representation


class HeapMapColors(object):
    """ Class providing operations with curses colors used in the heap map.

        Before first use it's necessary to initialize the curses color module
        and the colors for later use in the heap map. This is done with calling
        init_curses_colors() class method.
    """
    # good visible colors
    __good_colors = (
        1, 2, 3, 4, 5, 6, 7, 11, 14, 17, 21, 19, 22, 23, 27, 33, 30, 34, 45,
        41, 46, 49, 51, 52, 54, 56, 58, 59, 62, 65, 71, 76, 89, 91, 94, 95,
        124, 125, 126, 127, 129, 130, 131, 154, 156, 159, 161, 166, 167, 178,
        195, 197, 199, 203, 208, 210, 211, 214, 220, 226, 229, 255)
    # structure for saving corresponding allocation
    # with their specific color representation
    __color_records = []
    __good_colors_number = 0

    # color used as border field
    COLOR_BORDER = 1
    # color used as free field
    COLOR_FREE_FIELD = 2
    # color used for field with informative text
    COLOR_INFO_TEXT = 3

    @classmethod
    def init_curses_colors(cls):
        """ Initialize colors used later in __heap map """
        # 16 == black
        # -1 == implicit color

        # initializing the curses color module
        curses.start_color()
        curses.use_default_colors()

        start_pair_number = 1
        for i in cls.__good_colors:
            curses.init_pair(start_pair_number, 16, i)
            start_pair_number += 1

        cls.__good_colors_number = start_pair_number - 1
        # border color
        curses.init_pair(start_pair_number, 16, 16)
        cls.COLOR_BORDER = start_pair_number
        start_pair_number += 1
        # free field color
        curses.init_pair(start_pair_number, -1, 8)
        # for better grey scale printing
        curses.init_pair(start_pair_number, 16, 7)
        cls.COLOR_FREE_FIELD = start_pair_number
        start_pair_number += 1
        # info text color
        curses.init_pair(start_pair_number, -1, 16)
        cls.COLOR_INFO_TEXT = start_pair_number

    @classmethod
    def get_field_color(cls, field):
        """ Pick a right color for the given field.
        Arguments:
            field(dict): allocation's information

        Returns:
            int: number of the picked curses color.pair()
        """
        if field['uid'] is None:
            return cls.COLOR_FREE_FIELD

        uid = field['uid']
        for item in cls.__color_records:
            if (uid['function'] == item['uid']['function'] and
                    uid['source'] == item['uid']['source']):
                return item['color']

        color = randint(1, cls.__good_colors_number)
        cls.__color_records.append({'uid': uid, 'color': color})

        return color


# TODO maybe current snap and coordinates move to attributes?
class HeapMapVisualization(object):
    """ Class providing visualization of the __heap map.

        Visualization is implemented over curses module.
    """
    __memory_unit = None
    # initialized curses screen
    __window = None
    # heap representation
    __heap = None

    __NEXT_SNAPSHOT = 1
    __PREV_SNAPSHOT = -1
    __CURRENT_SNAPSHOT = 0
    __MIN_ROWS = 30
    __MIN_COLS = 70

    # delay after INTRO text [ms]
    __INTRO_DELAY = 700
    # delay between frames in ANIMATION mode [ms]
    __ANIMATION_DELAY = 1000

    __MENU_TEXT = '[Q] QUIT  [<] PREVIOUS  [>] NEXT  [A] ANIMATE  ' \
                  '[4|8|6|5] CURSOR L|U|R|D'
    __ANIME_MENU_TEXT = '[S] STOP  [P] PAUSE  [R] RESTART'
    __RESIZE_REQ_TEXT = "Increase the size of your screen, please"

    def show_intro(self):
        """ Print INTRO screen about HEAP MAP visualization """
        text = "HEAP MAP!"

        self.__window.addstr(curses.LINES // 2, (curses.COLS - len(text)) // 2,
                             text, curses.A_BOLD)
        self.__window.refresh()
        # just for effect :)
        curses.napms(self.__INTRO_DELAY)

    def resize_req_print(self):
        """ Print resize request to the window """
        self.__window.clear()
        self.__window.addstr(curses.LINES // 2,
                             (curses.COLS - len(self.__RESIZE_REQ_TEXT)) // 2,
                             self.__RESIZE_REQ_TEXT)

    def menu_print(self, text):
        """ Print text as menu information to the window
        Arguments:
        """
        self.__window.addstr(curses.LINES - 1, (curses.COLS - len(text)) // 2,
                             text, curses.A_BOLD)

    def info_print(self, curr, margin):
        """ Print the heap information to the window
        Arguments:
            curr(int): number of the current snapshot
            margin(int): left margin
        """
        info_text = 'SNAPSHOT: ' + str(curr) + '/' + str(self.__heap['max'])
        self.__window.addstr(0, ((curses.COLS - len(info_text) - margin) //
                                 2 + margin), info_text,
                             curses.color_pair(HeapMapColors.COLOR_INFO_TEXT))

    def create_screen_decomposition(self, curr, rows, cols):
        """ Create a matrix with corresponding representation of the snapshot
        Arguments:
            curr(int): number of the current snapshot
            rows(int): total number of the screen's rows
            cols(int): total number of the screen's columns

        Returns:
            dict: matrix representing screen's decomposition
                  and size of the field
        """
        snap = self.__heap['snapshots'][curr - 1]
        stats = self.__heap['stats']

        # calculating approximated field size
        field_size = (stats['max_address'] - stats['min_address']) / \
                     (rows * cols)

        matrix = [[None for _ in range(cols)] for _ in range(rows)]

        allocations = snap['map']
        # sorting allocations records by frequency of allocations
        allocations.sort(key=lambda x: x['address'])
        iterator = iter(allocations)

        record = next(iterator, None)
        # set starting address to first approx field
        last_field = stats['min_address']
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
                        remain_amount = 0 if record is None \
                            else record['amount']
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

    def matrix_print(self, heap_map, rows, cols, add_length):
        """ Prints the screen representation matrix to the window
        Arguments:
            heap_map(dict): representation information
            rows(int): total number of the screen's rows
            cols(int): total number of the screen's columns
            add_length(int): length of the maximal address
        """
        # border_sym = u"\u2588"
        border_sym = ' '
        field_sym = '_'
        tik_delimiter = '|'
        tik_freq = 10
        tik_amount = int(heap_map['field_size'] * tik_freq)

        # calculating address range on one line
        address = heap_map['data'][0][0]['address']
        line_address_size = int(heap_map['cols'] * heap_map['field_size'])

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

            self.__window.addnstr(row, 0, address_string, len(address_string),
                                  curses.color_pair(HeapMapColors.COLOR_INFO_TEXT))

            tik_counter = 0
            for col in range(add_length, cols):
                # border printing
                if col in (add_length, cols-1) or row in (0, rows-1):
                    self.__window.addch(row, col, border_sym,
                                        curses.color_pair(HeapMapColors.COLOR_BORDER))

                # field printing
                else:
                    field = heap_map['data'][row - 1][col - add_length - 1]
                    color = HeapMapColors.get_field_color(field)
                    if tik_counter % tik_freq == 0:
                        symbol = tik_delimiter
                    elif row == rows-2:
                        symbol = border_sym
                    else:
                        symbol = field_sym

                    self.__window.addstr(row, col, symbol, curses.color_pair(color))

                tik_counter += 1

        # adding tik amount info
        tik_amount_str = ''
        for i, col in enumerate(range(add_length, cols, tik_freq)):
            if tik_freq >= cols - col:
                break
            tik_string = str(tik_amount * i) + self.__memory_unit
            tik_amount_str += tik_string
            tik_amount_str += border_sym*(tik_freq - len(tik_string))

        self.__window.addstr(rows - 1, add_length + 1, tik_amount_str,
                             curses.color_pair(HeapMapColors.COLOR_INFO_TEXT))

    def redraw_heap_map(self, snap):
        """ Redraw the __heap map screen to represent the specified snapshot
        Arguments:
            snap(int): number of the snapshot to represent

        Returns:
            dict: cursor's screen coordinates
        """
        curses.update_lines_cols()
        self.__window.clear()

        # calculate space for the addresses information
        max_add_len = len(str(self.__heap['stats']['max_address']))
        if max_add_len < len('ADDRESS:'):
            max_add_len = len('ADDRESS:')

        # check for the minimal screen size
        if curses.LINES < self.__MIN_ROWS or \
                        (curses.COLS - max_add_len) < self.__MIN_COLS:
            return None

        # number of the screen's rows == (minimum of rows) - (2*border field)
        map_rows = self.__MIN_ROWS - 2
        # number of the screen's columns == (terminal's current number of
        # the columns) - (size of address info - 2*border field)
        map_cols = curses.COLS - max_add_len - 2
        # creating the __heap map screen decomposition
        decomposition = self.create_screen_decomposition(snap,
                                                         map_rows, map_cols)
        assert decomposition

        try:
            # printing __heap map decomposition to the console __window
            self.matrix_print(decomposition,
                              self.__MIN_ROWS, curses.COLS, max_add_len)
            # printing __heap info to the console __window
            self.info_print(snap, max_add_len)

            return {'row': 1, 'col': max_add_len + 1,
                    'map': decomposition}

        except curses.error:
            return None

    def animation_prompt(self, snap, cords):
        """ Handle animation feature of the HEAP MAP visualization
        Arguments:
            snap(int): number of the current snapshot
            cords(dict): Heap map's screen

        Returns:
            int: number of the current snapshot
        """
        curr_snap = snap

        # set non_blocking __window.getch()
        self.__window.nodelay(1)

        while True:
            # redraw standard MENU text with ANIMATION MENU text
            self.__window.hline(curses.LINES - 1, 0, ' ', curses.COLS - 1)
            self.menu_print(self.__ANIME_MENU_TEXT)
            self.__window.refresh()

            # delay between individually __heap map screens
            curses.napms(self.__ANIMATION_DELAY)
            key = self.__window.getch()

            if curr_snap < self.__heap['max']:
                curr_snap += 1
                heap_map = self.redraw_heap_map(curr_snap)
                if heap_map is None:
                    self.resize_req_print()
                    cords.update({'map': None})
                else:
                    cords.update(heap_map)

            if key in (ord('s'), ord('S')):
                # redraw ANIMATION MENU text with standard MENU text
                self.__window.hline(curses.LINES - 1, 0, ' ', curses.COLS - 1)
                self.menu_print(self.__MENU_TEXT)
                self.__window.refresh()
                # set cursor's position to the upper left corner of the __heap map
                self.__window.move(cords['row'], cords['col'])
                break
            # restart animation from the 1st snapshot
            elif key in (ord('r'), ord('R')):
                curr_snap = 0
            # stop animation until 'C' key is pressed
            elif key in (ord('p'), ord('P')):
                while self.__window.getch() not in (ord('c'), ord('C')):
                    menu = '[C] CONTINUE'
                    self.__window.addstr(curses.LINES - 1,
                                         (curses.COLS - len(menu)) // 2,
                                         menu, curses.A_BOLD)
                    self.__window.refresh()
            # change of the screen size occurred
            elif key == curses.KEY_RESIZE:
                heap_map = self.redraw_heap_map(curr_snap)
                if heap_map is None:
                    self.resize_req_print()
                    cords.update({'map': None})
                else:
                    cords.update(heap_map)

        # empty buffer __window.getch()
        while self.__window.getch() != -1:
            pass
        # set blocking __window.getch()
        self.__window.nodelay(0)

        return curr_snap

    def following_snapshot(self, current_snap, following_snap, cords):
        """ Set following snapshot to print
        Arguments:
            current_snap(int): number of the current snapshot
            following_snap(int): number of the following snapshot
            cords(dict): Heap map's screen

        Returns:
            int: number of the current snapshot
        """
        if following_snap == self.__NEXT_SNAPSHOT:
            if current_snap < self.__heap['max']:
                current_snap += following_snap
            else:
                return current_snap

        elif following_snap == self.__PREV_SNAPSHOT:
            if current_snap > 1:
                current_snap += following_snap
            else:
                return current_snap

        # draw heap map
        heap_map = self.redraw_heap_map(current_snap)
        if map is None:
            self.resize_req_print()
            cords.update({'map': None})
        else:
            cords.update(heap_map)
            # printing menu to the console window
            self.menu_print(self.__MENU_TEXT)
            # set cursor's position to the upper left corner of the heap map
            self.__window.move(cords['row'], cords['col'])

        return current_snap

    def cursor_move(self, direction, cords):
        """ Move the cursor to the new position defined by direction
        Arguments:
            direction(any): character returned by curses.getch()
            cords(dict): Heap map's screen
        """
        # current cursor's position
        row_col = self.__window.getyx()

        if direction == ord('4'):
            if row_col[1] - cords['col'] > 0:
                self.__window.move(row_col[0], row_col[1] - 1)
        elif direction == ord('6'):
            if row_col[1] - cords['col'] < cords['map']['cols'] - 1:
                self.__window.move(row_col[0], row_col[1] + 1)
        elif direction == ord('8'):
            if row_col[0] - cords['row'] > 0:
                self.__window.move(row_col[0] - 1, row_col[1])
        elif direction == ord('5'):
            if row_col[0] - cords['row'] < cords['map']['rows'] - 1:
                self.__window.move(row_col[0] + 1, row_col[1])

    def print_field_info(self, cords):

        if cords['map'] is None:
            return
        # current cursor's position
        row_col = self.__window.getyx()
        matrix_row = row_col[0] - cords['row']
        matrix_col = row_col[1] - cords['col']

        try:
            data = cords['map']['data'][matrix_row][matrix_col]
            if data['uid'] is None:
                info = "TODO global"
            else:
                info = "Starting address: " + str(data['address']) + '\n'
                info += "Allocated space: " + str(data['amount']) + ' ' \
                        + self.__memory_unit + '\n'
                info += "Allocation: " + str(data['uid'])
        except KeyError:
            info = ''

        self.__window.addstr(cords['map']['rows'] + 5, 0, info)

        self.__window.move(*row_col)

    def heap_map_prompt(self):
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
        """
        curr_snap = 0
        # initialize the screen's information
        screen_cords = {'row': 0, 'col': 0, 'map': {}}
        # initialize colors which will be used

        # print 1st snapshot's __heap map
        curr_snap = self.following_snapshot(curr_snap, self.__NEXT_SNAPSHOT,
                                            screen_cords)
        self.print_field_info(screen_cords)
        while True:
            # catching key value
            key = self.__window.getch()

            # quit of the visualization
            if key in (ord('q'), ord('Q')):
                break
            # previous snapshot
            elif key == curses.KEY_LEFT:
                curr_snap = self.following_snapshot(curr_snap,
                                                    self.__PREV_SNAPSHOT,
                                                    screen_cords)
            # next snapshot
            elif key == curses.KEY_RIGHT:
                curr_snap = self.following_snapshot(curr_snap,
                                                    self.__NEXT_SNAPSHOT,
                                                    screen_cords)
            # start of the animation
            elif key in (ord('a'), key == ord('A')):
                curr_snap = self.animation_prompt(curr_snap,
                                                  screen_cords)
            # cursor moved
            elif key in (ord('4'), ord('6'), ord('8'), ord('5')):
                self.cursor_move(key, screen_cords)
            # change of the screen size occurred
            elif key == curses.KEY_RESIZE:
                curr_snap = self.following_snapshot(curr_snap,
                                                    self.__CURRENT_SNAPSHOT,
                                                    screen_cords)

            self.print_field_info(screen_cords)

    def visualization_init(self, window, heap):
        self.__memory_unit = heap['unit']
        self.__window = window
        self.__heap = heap

        HeapMapColors.init_curses_colors()
        # set cursor visible
        curses.curs_set(2)

        self.show_intro()
        self.heap_map_prompt()

    def __init__(self, heap):
        """ Initialize heap map and call curses wrapper and start visualization

            Wrapper initialize terminal,
            turn off automatic echoing of keys to the screen,
            turn reacting to keys instantly
            (without requiring the Enter key to be pressed) on,
            enable keypad mode for special keys s.a. HOME.

        Arguments:
            heap(dict): the __heap representation

        Returns:
            string: message informing about operation success
        """
        # after integration remove try block
        try:
            # call __heap map visualization prompt in curses wrapper
            curses.wrapper(self.visualization_init, heap)
        except curses.error as error:
            print('Screen too small!', file=sys.stderr)
            print(str(error), file=sys.stderr)


if __name__ == "__main__":
    with open("memory.perf") as prof_json:
        prof = heap_representation.create(json.load(prof_json))
        HeapMapVisualization(prof)
