"""This module implement the HEAP MAP visualization of the profile"""
import curses
import curses.textpad
import json
import sys

# debug in console
import heap_representation as heap_representation
import heap_map_colors as hpcolors

#from perun.view.memory.cli.heap_map_colors import HeapMapColors

__author__ = 'Radim Podola'


class HeapMapVisualization(object):
    """ Class providing visualization of the heap map.

        Visualization is implemented over curses module.
        Is able to dynamic screen's size change.

        Heap map's metadata and coordinates are represented
        by dictionary in following form:

        {'col': # X coordinate of upper left corner of the map (int),
         'row': # Y coordinate of upper left corner of the map (int),
         'map':{
            'rows': # number of map's rows (int),
            'cols': # number of map's columns (int),
            'field_size': # field size (float),
            'data': # matrix with HEAP map's data
                {'uid': # UID of the allocation (dict),
                 'address': # starting address of the allocation (int),
                 'amount': # amount of allocated space (int)
                }
                # or matrix with HEAT map's data
               {'access': # number of access to the address (int),
                'address': # address of the memory space (int)
               }
          }
         }
            Coordinate space is 0---->X
                                |
                                |
                                |
                                Y

    Attributes:
        NEXT_SNAPSHOT(int): Constant representing move's direction
                            to the next snapshot.
        PREV_SNAPSHOT(int): Constant representing move's direction
                            to the previous snapshot.
        CURRENT_SNAPSHOT(int):  Constant representing move's direction
                                to the current snapshot.
        INTRO_DELAY(int):   Time delay after intro in [ms]
        ANIMATION_DELAY(int):   Time delay between frames
                                in ANIMATION mode in [ms]
        TIK_FREQ(int):  Tik frequency, visualized in the map. Value defines
                        a number of the fields in the tik.
        BORDER_SYM(char): character used as border
        FIELD_SYM(char): character used as regular field
        TIK_SYM(char):  character used as tik field
    """
    NEXT_SNAPSHOT = 1
    PREV_SNAPSHOT = -1
    CURRENT_SNAPSHOT = 0
    INTRO_DELAY = 1000
    ANIMATION_DELAY = 1000
    TIK_FREQ = 10

    # minimal size of the heap map window
    __MIN_ROWS = 30
    __MIN_COLS = 70

    # map's visualising symbols
    BORDER_SYM = ' '
    FIELD_SYM = '_'
    TIK_SYM = '|'

    # text's constants
    __ADDRESS_INFO_TEXT = 'ADDRESS:'
    __MENU_TEXT = '[Q] QUIT  [<] PREV  [>] NEXT  ' \
                  '[4|8|6|5] CURSOR MOVE  [A] ANIMATE  [H] HEAT'
    __ANIME_MENU_TEXT = '[S] STOP  [P] PAUSE  [R] RESTART'
    __ANIME_CONTINUE_TEXT = '[C] CONTINUE'
    __HEAT_MENU_TEXT = '[Q] QUIT [4|8|6|5] CURSOR MOVE'

    def print_intro(self):
        """ Builds and prints INTRO screen about HEAP MAP visualization """
        main_text = "INTERACTIVE HEAP MAP VISUALIZATION!"
        author_text = "Author: " + __author__

        # print MAIN text
        row_pos = curses.LINES // 2
        col_pos = (curses.COLS - len(main_text)) // 2
        self.__window.addstr(row_pos, col_pos, main_text, curses.A_BOLD)
        # print author info
        row_pos = curses.LINES // 2 + 1
        col_pos = (curses.COLS - len(author_text)) // 2
        self.__window.addstr(row_pos + 1, col_pos, author_text)

        self.__window.refresh()
        # delay for effect
        curses.napms(self.INTRO_DELAY)

    def print_resize_req(self):
        """ Prints resize request to the window """
        resize_text = "Increase the size of your screen, please"

        row_pos = curses.LINES // 2
        col_pos = (curses.COLS - len(resize_text)) // 2
        # clearing whole window
        self.__window.clear()
        self.__window.addstr(row_pos, col_pos, resize_text, curses.A_BOLD)

    def print_menu(self, menu_text):
        """ Prints text as menu information to the window

            Menu text is placed in the middle of the window's bottom

        Arguments:
            menu_text(string): string to print as a MENU text
        """
        # clearing line for MENU text
        self.__window.hline(curses.LINES - 1, 0, ' ', curses.COLS - 1)
        # print MENU text
        row_pos = curses.LINES - 1
        col_pos = (curses.COLS - len(menu_text)) // 2
        self.__window.addstr(row_pos, col_pos, menu_text, curses.A_BOLD)

    def print_map_info(self, margin):
        """ Prints the map information to the window

            Informative text is placed in the middle of the map's top border

        Arguments:
            margin(int): left margin
        """
        text = 'SNAPSHOT: {!s}/{!s}  ({!s}s)'.format(
            self.__current_snap, len(self.__heap['snapshots']),
            self.__heap['snapshots'][self.__current_snap - 1]['time'])

        row_pos = 0
        col_pos = (curses.COLS - len(text) - margin) // 2 + margin

        self.__window.addstr(row_pos, col_pos, text,
                             curses.color_pair(self.__colors.info_text))

    def __print_glob_stats(self, address):
        """ Prints global specific info

            Informative text is placed right bellow the map

        Arguments:
            address(float): map field's address
        """
        snap = self.__heap['snapshots'][self.__current_snap - 1]
        space_text = "Total allocated space: "
        address_text = "Address: "
        field_text = "Field size: "
        glob_text = 'MAP INFO:'
        margin = len(space_text)

        row_pos = self.__map_cords['map']['rows'] + 2
        col_pos = (curses.COLS - len(glob_text)) // 2

        self.__window.hline(row_pos, 0, self.BORDER_SYM, curses.COLS,
                            curses.color_pair(self.__colors.info_text))
        self.__window.addstr(row_pos, col_pos, glob_text,
                             curses.color_pair(self.__colors.info_text))

        # 1st line
        line1 = space_text + ' '*(margin - len(space_text))
        line1 += str(snap['sum_amount']) + ' ' + self.__heap['unit']
        line1 += ' '*(curses.COLS - len(line1))
        # 2nd line
        line2 = address_text + ' '*(margin - len(address_text))
        line2 += str(int(address))
        line2 += ' '*(curses.COLS - len(line2))
        # 3rd line
        line3 = field_text + ' '*(margin - len(field_text))
        line3 += str(int(self.__map_cords['map']['field_size']))
        line3 += ' ' + self.__heap['unit']
        line3 += ' '*(curses.COLS - len(line3))

        # print current field's information
        self.__window.addstr(row_pos + 1, 0, line1 + line2 + line3,
                             curses.color_pair(self.__colors.info_text))

    def __print_alloc_stats(self, data):
        """ Prints field's specific info

            Informative text is placed right bellow the map

        Arguments:
            data(dict): map field's data
        """
        space_text = "Allocated space: "
        address_text = "Starting address: "
        allocation_text = "Allocation: "
        glob_text = 'ALLOCATION INFO:'
        margin = len(address_text)

        row_pos = self.__map_cords['map']['rows'] + 2
        col_pos = (curses.COLS - len(glob_text)) // 2

        self.__window.hline(self.BORDER_SYM, curses.COLS,
                            curses.color_pair(self.__colors.info_text))
        self.__window.addstr(row_pos, col_pos, glob_text,
                             curses.color_pair(self.__colors.info_text))

        # 1st line
        line1 = space_text + ' '*(margin - len(space_text))
        line1 += str(data['amount']) + ' ' + self.__heap['unit']
        line1 += ' '*(curses.COLS - len(line1))
        # 2nd line
        line2 = address_text + ' '*(margin - len(address_text))
        line2 += str(data['address'])
        line2 += ' '*(curses.COLS - len(line2))
        # 3rd line
        line3 = allocation_text + ' '*(margin - len(allocation_text))
        line3 += "F: " + str(data['uid']['function'])
        line3 += ' '*(curses.COLS - len(line3))
        # 4th line
        line4 = ' '*margin
        line4 += "S: " + str(data['uid']['source'])
        line4 += ":" + str(data['uid']['line'])
        line4 += ' '*(curses.COLS - len(line4))

        # print current field's information
        self.__window.addstr(row_pos + 1, 0, line1 + line2 + line3 + line4,
                             curses.color_pair(self.__colors.info_text))

    def __print_heat_stats(self, data):
        """ Prints field's access info

            Informative text is placed right bellow the map

        Arguments:
            data(dict): map field's data
        """
        heat_text = 'HEAT INFO:'
        access_text = "Number of accesses: "
        address_text = "Starting address: "
        margin = len(access_text)

        row_pos = self.__map_cords['map']['rows'] + 2
        col_pos = (curses.COLS - len(heat_text)) // 2

        self.__window.hline(self.BORDER_SYM, curses.COLS,
                            curses.color_pair(self.__colors.info_text))
        self.__window.addstr(row_pos, col_pos, heat_text,
                             curses.color_pair(self.__colors.info_text))

        # 1st line
        line1 = access_text + ' '*(margin - len(access_text))
        line1 += str(data['access']) + 'x'
        line1 += ' '*(curses.COLS - len(line1))
        # 2nd line
        line2 = address_text + ' '*(margin - len(address_text))
        line2 += str(int(data['address']))
        line2 += ' '*(curses.COLS - len(line2))

        # print current field's information
        self.__window.addstr(row_pos + 1, 0, line1 + line2,
                             curses.color_pair(self.__colors.info_text))

    def __get_tik_info(self, length, tik_amount):
        """ Builds tik information line

        Arguments:
           length(int): length of information text
           tik_amount(int): tik amount

        Returns:
            str: built tik information text
        """
        tik_amount_str = ''

        for i, col in enumerate(range(0, length, self.TIK_FREQ)):
            if self.TIK_FREQ >= length - col:
                break
            tik_string = '{!s}{}'.format((tik_amount * i), self.__heap['unit'])
            tik_amount_str += tik_string
            empty_fields = self.TIK_FREQ - len(tik_string)
            tik_amount_str += self.BORDER_SYM * empty_fields

        return tik_amount_str

    def __print_address(self, row, add_str, space):
        """ Prints the address info

        Arguments:
           row(int): window's row where print the address
           add_str(str): address string
           space(int): length of the address info space
        """
        empty_fields = space - len(add_str)
        add_str += self.BORDER_SYM * empty_fields
        self.__window.addnstr(row, 0, add_str, len(add_str),
                              curses.color_pair(self.__colors.info_text))

    def __get_field_size(self):
        """ Calculates the field's size based on the screen's size

        Returns:
            float: field size
        """
        stats = self.__heap['stats']
        _, rows, cols = self.__get_map_size()
        # calculating approximated field size
        line_address_range = stats['max_address'] - stats['min_address']
        size = line_address_range / (rows * cols)

        return size

    def __get_map_size(self):
        """ Calculate the true map's size

        Returns:
            tuple: address info length, map's rows, map's columns
        """
        # calculate space for the addresses information
        max_add_len = len(str(self.__heap['stats']['max_address']))
        if max_add_len < len(self.__ADDRESS_INFO_TEXT):
            max_add_len = len(self.__ADDRESS_INFO_TEXT)

        # number of the screen's rows == (minimum of rows) - (2*border field)
        map_rows = self.__MIN_ROWS - 2
        # number of the screen's columns == (terminal's current number of
        # the columns) - (size of address info - 2*border field)
        map_cols = curses.COLS - max_add_len - 2

        return max_add_len, map_rows, map_cols

    def create_map_matrix(self, rows, cols):
        """ Create a matrix with corresponding representation of the snapshot

        Arguments:
            rows(int): total number of the screen's rows
            cols(int): total number of the screen's columns

        Returns:
            dict: matrix representing map with additional info
                  following format:
                  {"data": matrix,
                   "field_size": (float),
                   "rows": (int),
                   "cols": (int)
                  }
            matrix format:
                  [{"uid": # allocation UID (dict),
                   "address": # field's address or
                                allocation's starting address (float),
                   "amount": (int)
                  }]
        """
        snap = self.__heap['snapshots'][self.__current_snap - 1]
        field_size = self.__get_field_size()
        # creating empty matrix
        matrix = [[None for _ in range(cols)] for _ in range(rows)]

        allocations = snap['map']
        # sorting allocations records by frequency of allocations
        allocations.sort(key=lambda x: x['address'])
        #set iterator over list
        iterator = iter(allocations)
        # set starting points
        record = next(iterator, None)
        last_field = self.__heap['stats']['min_address']
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

                    # record is in the next field, let's put it's info there
                    uid_info = self.__heap['info'][record['uid']]
                    matrix[row][col] = {"uid": uid_info,
                                        "address": record['address'],
                                        "amount": record['amount']}

                    # spread record over or get next record
                    if remain_amount <= field_size:
                        record = next(iterator, None)
                        if record is None:
                            remain_amount = 0
                        else:
                            remain_amount = record['amount']

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

    def create_heat_matrix(self, rows, cols):
        """ Create a matrix with corresponding HEAT representation

        Arguments:
            rows(int): total number of the screen's rows
            cols(int): total number of the screen's columns

        Returns:
            dict: matrix representing HEAT map with additional info
                  following format:
                  {"data": matrix,
                   "field_size": (float),
                   "rows": (int),
                   "cols": (int)
                  }
            matrix format:
                  [{"address": # field's address (float),
                    "access": number of the field's access (int)
                  }]
        """
        field_size = self.__get_field_size()

        # creating empty matrix
        matrix = [[None for _ in range(cols)] for _ in range(rows)]

        accesses = self.__heap['map']
        # set starting address to first approx field
        min_address = self.__heap['stats']['min_address']
        curr_add = min_address
        for row in range(rows):
            for col in range(cols):

                access_number = max(accesses[int(curr_add) + i - min_address]
                                    for i in range(int(field_size)))

                matrix[row][col] = {"access": access_number,
                                    "address": curr_add
                                   }

                curr_add += field_size

        return {"data": matrix, "field_size": field_size,
                "rows": rows, "cols": cols}

    def print_matrix(self, rows, cols, add_length):
        """ Prints the matrix representation to the window

            Printed matrix is also surrounded by border and address info

        Arguments:
            rows(int): total number of the screen's rows
            cols(int): total number of the screen's columns
            add_length(int): length of the address info space
        """
        map_data = self.__map_cords['map']
        tik_amount = int(map_data['field_size'] * self.TIK_FREQ)

        # calculating address range on one line
        address = map_data['data'][0][0]['address']
        line_address_size = int(map_data['cols'] * map_data['field_size'])

        for row in range(rows):
            # address info printing calculated from 1st and field size (approx)
            if row not in (0, rows - 1):
                self.__print_address(row, str(address), add_length)
                address += line_address_size
            elif row == 0:
                self.__print_address(row, self.__ADDRESS_INFO_TEXT, add_length)
            else:
                self.__print_address(row, '', add_length)

            tik_counter = 0
            for col in range(add_length, cols):
                # border printing
                if col in (add_length, cols-1) or row in (0, rows-1):
                    self.__window.addch(row, col, self.BORDER_SYM,
                                        curses.color_pair(
                                            self.__colors.border))

                # field printing
                else:
                    field = map_data['data'][row - 1][col - add_length - 1]
                    if self.__heat_mode:
                        color = self.__colors.heat_field_color(field['access'])
                    else:
                        color = self.__colors.heap_field_color(field['uid'])

                    if tik_counter % self.TIK_FREQ == 0:
                        symbol = self.TIK_SYM
                    elif row == rows-2:
                        symbol = self.BORDER_SYM
                    else:
                        symbol = self.FIELD_SYM

                    self.__window.addstr(row, col, symbol,
                                         curses.color_pair(color))

                tik_counter += 1

        # adding tik amount info
        tik_str = self.__get_tik_info(cols - add_length, tik_amount)
        self.__window.addstr(rows - 1, add_length + 1, tik_str,
                             curses.color_pair(self.__colors.info_text))

    def draw_heap_map(self):
        """ Draw the window to represent the current snapshot

        Returns:
            bool: success of the operation
        """
        curses.update_lines_cols()
        self.__window.clear()
        self.__map_cords = None

        add_space, true_rows, true_cols = self.__get_map_size()

        # check for the minimal screen size
        rows_cond = curses.LINES < self.__MIN_ROWS
        cols_cond = curses.COLS - add_space < self.__MIN_COLS
        if rows_cond or cols_cond:
            return False

        # creating the heap map screen decomposition
        decomposition = self.create_map_matrix(true_rows, true_cols)
        # update map information and coordinates
        self.__map_cords = {'row': 1, 'col': add_space + 1,
                            'map': decomposition}

        # printing heap map decomposition to the console window
        self.print_matrix(self.__MIN_ROWS, curses.COLS, add_space)

        # printing heap info to the console window
        self.print_map_info(add_space)

        return True

    def draw_heat_map(self):
        """ Draw the window to represent HEAT map """
        curses.update_lines_cols()
        self.__window.clear()
        self.__map_cords = None

        add_space, true_rows, true_cols = self.__get_map_size()

        # check for the minimal screen size
        rows_cond = curses.LINES < self.__MIN_ROWS
        cols_cond = curses.COLS - add_space < self.__MIN_COLS
        if rows_cond or cols_cond:
            self.print_resize_req()
            return

        # creating the heat map screen decomposition
        decomposition = self.create_heat_matrix(true_rows, true_cols)
        # update map information and coordinates
        self.__map_cords = {'row': 1, 'col': add_space + 1,
                            'map': decomposition}

        # printing heat map decomposition to the console window
        self.print_matrix(self.__MIN_ROWS, curses.COLS, add_space)

        self.print_menu(self.__HEAT_MENU_TEXT)

        self.reset_cursor()
        self.print_field_info()

    def __set_current_snap(self, following_snap):
        """ Sets current snapshot

        Arguments:
            following_snap(int): number of the snapshot to set
        """
        if following_snap in range(1, len(self.__heap['snapshots']) + 1):
            self.__current_snap = following_snap
            return True
        else:
            return False

    def following_snapshot(self, direction):
        """ Set following snapshot and print the map

        Arguments:
            direction(int): direction of the following snapshot (PREVIOUS/NEXT)

        Returns:
            bool: success of the operation
        """
        if not self.__set_current_snap(self.__current_snap + direction):
            return

        if self.draw_heap_map():
            # printing menu to the console window
            self.print_menu(self.__MENU_TEXT)
            # set cursor's position to the upper left corner of the heap map
            self.reset_cursor()
            self.print_field_info()
        else:
            self.print_resize_req()

    def reset_cursor(self):
        """ Resets the cursor position

            Default position is in the upper left corner of the heap map
        """
        self.__window.move(self.__map_cords['row'], self.__map_cords['col'])

    def move_cursor(self, direction):
        """ Move the cursor to the new position defined by direction

        Arguments:
            direction(any): character returned by curses.getch()
        """
        if not self.__map_cords:
            return

        # save current cursor's position
        row_col = self.__window.getyx()

        map_rows = self.__map_cords['map']['rows']
        map_cols = self.__map_cords['map']['cols']

        if direction == ord('4'):
            if row_col[1] - self.__map_cords['col'] > 0:
                self.__window.move(row_col[0], row_col[1] - 1)
            else:
                self.__window.move(row_col[0],
                                   self.__map_cords['col'] + map_cols - 1)

        elif direction == ord('6'):
            if row_col[1] - self.__map_cords['col'] < map_cols - 1:
                self.__window.move(row_col[0], row_col[1] + 1)
            else:
                self.__window.move(row_col[0],
                                   self.__map_cords['col'])

        elif direction == ord('8'):
            if row_col[0] - self.__map_cords['row'] > 0:
                self.__window.move(row_col[0] - 1, row_col[1])
            else:
                self.__window.move(self.__map_cords['row'] + map_rows - 1,
                                   row_col[1])

        else:
            if row_col[0] - self.__map_cords['row'] < map_rows - 1:
                self.__window.move(row_col[0] + 1, row_col[1])
            else:
                self.__window.move(self.__map_cords['row'], row_col[1])

    def print_field_info(self):
        """ Prints information about memory space pointed by the cursor """
        if not self.__map_cords:
            return

        # save current cursor's position
        orig_row_col = self.__window.getyx()
        # calculate map field from cursor's position
        matrix_row = orig_row_col[0] - self.__map_cords['row']
        matrix_col = orig_row_col[1] - self.__map_cords['col']

        info_start_cords = self.__map_cords['map']['rows'] + 2, 0
        self.__window.move(*info_start_cords)
        # clear previous field's information
        self.__window.clrtobot()

        try:
            data = self.__map_cords['map']['data'][matrix_row][matrix_col]
            if self.__heat_mode:
                self.__print_heat_stats(data)
            elif data['uid'] is None:
                self.__print_glob_stats(data['address'])
            else:
                self.__print_alloc_stats(data)
        except KeyError:
            pass
        # printing menu to the console window, was also cleared
        if self.__heat_mode:
            self.print_menu(self.__HEAT_MENU_TEXT)
        else:
            self.print_menu(self.__MENU_TEXT)
        # move cursor to the original position
        self.__window.move(*orig_row_col)

    def animation_logic(self):
        """ Animation feature's logic of the HEAP MAP visualization """
        # set non_blocking window.getch()
        self.__window.nodelay(1)

        while True:
            # print ANIMATION MENU text
            self.print_menu(self.__ANIME_MENU_TEXT)

            # delay between individually heap map screens
            curses.napms(self.ANIMATION_DELAY)

            key = self.__window.getch()

            self.following_snapshot(self.NEXT_SNAPSHOT)

            if key in (ord('s'), ord('S')):
                # stop ANIMATION
                self.following_snapshot(self.CURRENT_SNAPSHOT)
                break
            # restart animation from the 1st snapshot
            elif key in (ord('r'), ord('R')):
                self.__set_current_snap(1)
                self.following_snapshot(self.CURRENT_SNAPSHOT)
            # stop animation until 'C' key is pressed
            elif key in (ord('p'), ord('P')):
                while self.__window.getch() not in (ord('c'), ord('C')):
                    self.print_menu(self.__ANIME_CONTINUE_TEXT)
            # change of the screen size occurred
            elif key == curses.KEY_RESIZE:
                self.following_snapshot(self.CURRENT_SNAPSHOT)

        # empty buffer window.getch()
        while self.__window.getch() != -1:
            pass
        # set blocking window.getch()
        self.__window.nodelay(0)

    def __init__(self, window, heap):
        """ Initialize the HEAP MAP visualization object

        Arguments:
            window(any): initialized curses window
            heap(dict): the heap representation
        """
        # initialized curses window
        self.__window = window
        # heap representation
        self.__heap = heap
        # mode
        self.__heat_mode = bool(heap['type'] == 'heat')
        # currently printed map's snapshot
        self.__current_snap = 0
        # heap map's metadata and coordinates
        self.__map_cords = None
        # instance of the color module object
        self.__colors = hpcolors.HeapMapColors(
            hpcolors.HeapMapColors.CURSES_COLORS)

        # set cursor visible
        curses.curs_set(2)


def heat_map_logic(window, heat):
    """ HEAT visualization logic prompt

    Arguments:
        window(any): initialized curses window
        heat(dict): the heat map representation
    """
    # instantiate of the heat map visualization object
    vis_obj = HeapMapVisualization(window, heat)

    vis_obj.draw_heat_map()

    while True:
        # catching key value
        key = window.getch()

        # quit of the visualization
        if key in (ord('q'), ord('Q')):
            break
        # cursor moved
        elif key in (ord('4'), ord('6'), ord('8'), ord('5')):
            vis_obj.move_cursor(key)
            vis_obj.print_field_info()
        # change of the screen size occurred
        elif key == curses.KEY_RESIZE:
            vis_obj.draw_heat_map()


def heap_map_logic(window, heap, heat):
    """ HEAP visualization logic prompt

    Arguments:
        window(any): initialized curses window
        heap(dict): the heap map representation
        heat(dict): the heat map representation
    """
    # instantiate of the heap map visualization object
    vis_obj = HeapMapVisualization(window, heap)

    # print intro
    vis_obj.print_intro()
    # print 1st snapshot's heap map
    vis_obj.following_snapshot(vis_obj.NEXT_SNAPSHOT)

    while True:
        # catching key value
        key = window.getch()

        # quit of the visualization
        if key in (ord('q'), ord('Q')):
            break
        # previous snapshot
        elif key == curses.KEY_LEFT:
            vis_obj.following_snapshot(vis_obj.PREV_SNAPSHOT)
        # next snapshot
        elif key == curses.KEY_RIGHT:
            vis_obj.following_snapshot(vis_obj.NEXT_SNAPSHOT)
        # start of the animation
        elif key in (ord('a'), ord('A')):
            vis_obj.animation_logic()
        # cursor moved
        elif key in (ord('4'), ord('6'), ord('8'), ord('5')):
            vis_obj.move_cursor(key)
            vis_obj.print_field_info()
        # HEAT map
        elif key in (ord('h'), ord('H')):
            heat_map_logic(window, heat)
            vis_obj.following_snapshot(vis_obj.CURRENT_SNAPSHOT)
        # change of the screen size occurred
        elif key == curses.KEY_RESIZE:
            vis_obj.following_snapshot(vis_obj.CURRENT_SNAPSHOT)


def heap_map(heap, heat):
    """ Call curses wrapper and start visualization

        Wrapper initialize terminal,
        turn off automatic echoing of keys to the screen,
        turn reacting to keys instantly
        (without requiring the Enter key to be pressed) on,
        enable keypad mode for special keys s.a. HOME.

    Arguments:
        heap(dict): the heap representation

    Returns:
        string: message informing about operation success
    """
    # after integration remove try block
    try:
        # call heap map visualization prompt in curses wrapper
        curses.wrapper(heap_map_logic, heap, heat)
    except curses.error as error:
        print('Screen too small!', file=sys.stderr)
        print(str(error), file=sys.stderr)


if __name__ == "__main__":
    with open("memory.perf") as f:
        heap_file = heap_representation.create_heap_map(json.load(f))
    with open("heat.perf") as f:
        heat_file = heap_representation.create_heat_map(json.load(f))
    heap_map(heap_file, heat_file)
