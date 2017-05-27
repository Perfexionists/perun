"""This module implement the flow graph visualization of the profile"""
import curses
import curses.textpad
import sys
import math

__author__ = 'Radim Podola'

class FlowGraphVisualization(object):
    """ Class providing visualization of the allocation flow.

        Visualization is implemented over curses module.

    Attributes:
        MOVE_RIGHT(int):   Constant representing move's direction
                           to the next snapshot.
        MOVE_LEFT(int):   Constant representing move's direction
                          to the previous snapshot.
        NO_MOVE(int):   Constant representing move's direction
                        to the current snapshot.
        INTRO_DELAY(int):   Time delay after intro in [ms]
        BAR_SPACE(int): Space between bars
        LINE_DELIMITER_SPACE(int): Space between line delimiters
        BAR_SYM(char): character used as ba regular bar
        BAR_PEAK_SYM(char): character used as a peak bar
        X_LINES_SYM(char):  character used as a line delimiter
        BORDER_SYM(char):  character used as a border
    """
    MOVE_RIGHT = 1
    MOVE_LEFT = -1
    NO_MOVE = 0
    INTRO_DELAY = 1000
    BAR_SPACE = 10
    LINE_DELIMITER_SPACE = 5

    # minimal size of the heap map window
    __MIN_ROWS = 40
    __MIN_COLS = 70

    # map's visualising symbols
    BAR_SYM = '\u275A'
    BAR_PEAK_SYM = '\u2AFC'
    X_LINES_SYM = '\u2504'
    BORDER_X_SYM = '\u2550'
    BORDER_Y_SYM = '\u2551'
    BORDER_LEFT_DOWN_CORNER_SYM = '\u255A'
    BORDER_LEFT_UP_CORNER_SYM = '\u2554'
    BORDER_RIGHT_UP_CORNER_SYM = '\u2557'
    BORDER_RIGHT_DOWN_CORNER_SYM = '\u255D'

    # text's constants
    __Y_AXIS_TEXT = 'MEMORY [B]'
    __X_AXIS_TEXT = 'SNAPSHOT->'
    __MENU_TEXT = '[Q] QUIT  [I] ENTER INTERACTIVE MODE'
    __INTERACTIVE_MENU_TEXT = '[Q] QUIT  [<] PREVIOUS  [>] NEXT'

    def __init__(self, window, heap):
        """ Initialize the FLOW GRAPH visualization object

            [{'fields': 0, 'peak': False, 'time': 0.0, 'snapshot': 0}]

        Arguments:
            window(any): initialized curses window
            heap(dict): the heap representation
        """
        # memory allocated peak
        self.__peak = heap['stats']['max_sum_amount']
        # initialized curses window
        self.__window = window
        # heap representation
        self.__heap = heap
        # currently printed map's snapshot
        self.__current_snap = 1
        # graph data
        self.__graph_data = []

        # initializing the curses color module
        curses.start_color()
        curses.use_default_colors()
        # set cursor invisible
        curses.curs_set(0)

    def print_intro(self):
        """ Builds and prints INTRO screen about FLOW GRAPH visualization """
        main_text = "INTERACTIVE FLOW GRAPH VISUALIZATION!"
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

    def __print_y_axis_info(self, rows, cols, margin):
        """ Prints the Y-axis information

        Arguments:
            rows(int): total number of the screen's rows
            cols(int): total number of the screen's columns
            margin(int): length of the Y-axis info space
        """
        field_size = self.__get_field_size(rows)

        self.__window.addstr(0, 0, self.__Y_AXIS_TEXT)

        tik_cnt = 0
        for i, row in enumerate(range(0, rows, self.LINE_DELIMITER_SPACE)):
            starting_row = rows - row - 2
            self.__window.addstr(starting_row, 0, str(int(field_size * tik_cnt)))
            tik_cnt += 1

            for col in range(margin + 1, cols - 1):
                if i == 0:
                    break
                self.__window.addch(starting_row, col, self.X_LINES_SYM)

    def __print_x_axis_info(self, rows, margin):
        """ Prints the X-axis information

        Arguments:
            rows(int): total number of the screen's rows
            margin(int): length of the Y-axis info space
        """
        self.__window.addstr(rows - 1, 0, self.__X_AXIS_TEXT)

        for i, bar in enumerate(self.__graph_data):
            col = margin + (i + 1) * self.BAR_SPACE
            self.__window.addstr(rows - 1, col, str(bar['snapshot']))

    def __print_borders(self, rows, cols, margin):
        """ Prints the borders around graph

        Arguments:
            rows(int): total number of the screen's rows
            cols(int): total number of the screen's cols
            margin(int): length of the Y-axis info space
        """
        # printing horizontal borders
        for col in range(margin, cols):
            self.__window.addch(0, col, self.BORDER_X_SYM)
            self.__window.addch(rows - 2, col, self.BORDER_X_SYM)

        # printing border's corners
        self.__window.addch(0, margin, self.BORDER_LEFT_UP_CORNER_SYM)
        self.__window.addch(rows - 2, margin, self.BORDER_LEFT_DOWN_CORNER_SYM)
        self.__window.addch(0, cols - 1, self.BORDER_RIGHT_UP_CORNER_SYM)
        self.__window.addch(rows - 2, cols - 1, self.BORDER_RIGHT_DOWN_CORNER_SYM)

        # printing vertical borders
        for row in range(1, rows - 2):
            self.__window.addch(row, margin, self.BORDER_Y_SYM)
            self.__window.addch(row, cols - 1, self.BORDER_Y_SYM)

    def __set_start_snap(self, following_snap, cols):
        """ Sets starting snapshot

        Arguments:
            following_snap(int): number of the snapshot to set
            cols(int): total number of the screen's columns
        """
        # calculating total number of the bars in screen
        bars = cols // self.BAR_SPACE
        snapshots = len(self.__heap['snapshots'])

        if following_snap not in range(1, snapshots + 1):
            return

        # dynamic moving when resize to occurred
        if self.__current_snap == following_snap:
            if snapshots - self.__current_snap + 1 < bars:
                self.__current_snap = following_snap - 1
                return

        # check for maximal bars
        if following_snap > snapshots - bars + 1:
            return

        self.__current_snap = following_snap

    def print_graph(self, rows, cols, margin):
        """ Prints the graph data to the screen with borders and axis's info

        Arguments:
            rows(int): total number of the screen's rows
            cols(int): total number of the screen's columns
            margin(int): length of the Y-axis info space
        """
        # set iterator over graph data list
        iterator = iter(self.__graph_data)
        record = next(iterator, None)

        for col in range(margin + self.BAR_SPACE, cols, self.BAR_SPACE):

            if record is None:
                break

            if record['peak']:
                # print different symbol representing PEAK bar
                symbol = self.BAR_PEAK_SYM
            else:
                symbol = self.BAR_SYM

            # total rows - number of fields - 2x border field
            start_row = rows - 2 - record['fields']
            # prints BAR
            for row in range(start_row, rows - 2):
                self.__window.addch(row, col, symbol)

            record = next(iterator, None)

        # printing borders
        self.__print_borders(rows, cols, margin)

        # printing axises's information
        self.__print_y_axis_info(rows, cols, margin)
        self.__print_x_axis_info(rows, margin)

    def __get_field_size(self, rows):
        """ Calculates the field's size based on the screen's size

        Returns:
            float: field size
        """
        # calculating approximation size of the field
        size = self.__peak / rows

        return size

    def create_partial_graph(self, rows, cols):
        """ Create graph's data structure for partial view

            Structure is saved into instance attribute __graph_data.

        Arguments:
            rows(int): total number of the graph's rows
            cols(int): total number of the graph's columns
        """
        # clearing old data
        self.__graph_data = []
        # calculating total number of the bars in screen
        bars = cols // self.BAR_SPACE
        field_size = self.__get_field_size(rows)

        bars_cnt = 0
        for i, snap in enumerate(self.__heap['snapshots']):
            # heap representation transforming into graph data
            if self.__current_snap <= i + 1:
                bars_cnt += 1
                if bars_cnt <= bars:
                    data = {}
                    total_fields = int(math.ceil(snap['sum_amount'] / field_size))
                    data['fields'] = total_fields
                    data['time'] = snap['time']
                    data['snapshot'] = i + 1
                    if 'sum_amount' in snap:
                        data['peak'] = bool(snap['sum_amount'] == self.__peak)
                    else:
                        data['peak'] = 0
                    self.__graph_data.append(data)

    def print_partial_view(self, move):
        """ Draws the heap map screen to represent the specified snapshot

        Arguments:
            move(int): move of the following snapshot (PREVIOUS/NEXT)
        """
        try:
            rows, cols, margin = self.__get_graph_size()
        except curses.error:
            self.print_resize_req()
            return

        # sets first snapshot
        self.__set_start_snap(self.__current_snap + move, cols)
        # creating the flow graph screen decomposition
        self.__window.clear()
        self.create_partial_graph(rows, cols)

        # graph print
        self.print_graph(self.__MIN_ROWS, curses.COLS, margin)

        # print interactive menu text
        self.print_menu(self.__INTERACTIVE_MENU_TEXT)

    def print_global_view(self):
        """ Draw global view of the allocation's FLOW """
        self.__window.clear()

        try:
            # getting true graph's size
            rows, cols, margin = self.__get_graph_size()
        except curses.error:
            self.print_resize_req()
            return

        # creating the flow graph screen decomposition
        self.create_global_graph(rows, cols)
        # graph print
        self.print_graph(self.__MIN_ROWS, curses.COLS, margin)
        # print menu text
        self.print_menu(self.__MENU_TEXT)

    def create_global_graph(self, rows, cols):
        """ Create graph's data structure for global view

            Structure is saved into instance attribute __graph_data.

        Arguments:
            rows(int): total number of the graph's rows
            cols(int): total number of the graph's columns
        """
        # clearing old data
        self.__graph_data = []
        # calculating total number of the bars in screen
        bars = cols // self.BAR_SPACE
        field_size = self. __get_field_size(rows)
        snapshots = len(self.__heap['snapshots'])

        if snapshots >= bars:
            approx_bars = int(math.ceil(snapshots / bars))
            bars_cnt = 0
            was_peak = False
            avg_sum = 0
            # heap representation transforming into graph data
            for i, snap in enumerate(self.__heap['snapshots']):
                bars_cnt += 1
                avg_sum += snap['sum_amount']
                if 'sum_amount' in snap and snap['sum_amount'] == self.__peak:
                    was_peak = True
                if bars_cnt == approx_bars:
                    data = {}
                    # number of the fields is average of the approximated bars
                    total_fields = avg_sum / field_size / approx_bars
                    data['fields'] = int(math.ceil(total_fields))
                    data['time'] = snap['time']
                    data['snapshot'] = i + 1
                    data['peak'] = bool(was_peak)
                    self.__graph_data.append(data)
                    bars_cnt = 0
                    avg_sum = 0
                    was_peak = False

        else:
            for i, snap in enumerate(self.__heap['snapshots']):
                # heap representation transforming into graph data
                data = {}
                total_fields = int(math.ceil(snap['sum_amount'] / field_size))
                data['fields'] = total_fields
                data['time'] = snap['time']
                data['snapshot'] = i + 1
                if 'sum_amount' in snap:
                    data['peak'] = bool(snap['sum_amount'] == self.__peak)
                else:
                    data['peak'] = 0
                self.__graph_data.append(data)

    def __get_graph_size(self):
        """ Calculates the true graph's size.

            Also check the screen's size limitations.

        Returns:
            tuple: address info length, map's rows, map's columns

        Raises:
            curses.error: when minimal screen's size is not respected
        """
        curses.update_lines_cols()

        # calculate space for the Y-axis information
        max_y_axis_len = len(str(self.__heap['stats']['max_amount']))
        if max_y_axis_len < len(self.__Y_AXIS_TEXT):
            max_y_axis_len = len(self.__Y_AXIS_TEXT)

        # check for the minimal screen size
        rows_cond = curses.LINES < self.__MIN_ROWS
        cols_cond = curses.COLS - max_y_axis_len < self.__MIN_COLS
        if rows_cond or cols_cond:
            raise curses.error

        # number of the screen's rows == (minimum of rows)
        # - 2(border lines) - 1 (info line)
        graph_rows = self.__MIN_ROWS - 3
        # number of the screen's columns ==
        # (terminal's current number of the columns)
        # - (size of Y-axis info) - 2(border columns)
        graph_cols = curses.COLS - max_y_axis_len - 2

        return graph_rows, graph_cols, max_y_axis_len

    def interactive_logic(self):
        """ Interactive FLOW GRAPH visualization prompt logic """
        # print partial view
        self.print_partial_view(self.NO_MOVE)

        while True:
            # catching key value
            key = self.__window.getch()

            # quit the interactive mode
            if key in (ord('q'), ord('Q')):
                break
            # previous snapshot
            elif key == curses.KEY_LEFT:
                self.print_partial_view(self.MOVE_LEFT)
            # next snapshot
            elif key == curses.KEY_RIGHT:
                self.print_partial_view(self.MOVE_RIGHT)
            # change of the screen size occurred
            elif key == curses.KEY_RESIZE:
                self.print_partial_view(self.NO_MOVE)


def flow_graph_logic(window, heap):
    """ FLOW GRAPH visualization prompt logic

    Arguments:
        window(any): initialized curses window
        heap(dict): the heap representation
    """
    # instantiate of the flow graph visualization object
    vis_obj = FlowGraphVisualization(window, heap)

    # print intro
    vis_obj.print_intro()
    # print global view
    vis_obj.print_global_view()

    while True:
        # catching key value
        key = window.getch()

        # quit of the visualization
        if key in (ord('q'), ord('Q')):
            break
        # enter interactive mode
        elif key in (ord('i'), ord('I')):
            vis_obj.interactive_logic()
            # print global view
            vis_obj.print_global_view()
        # change of the screen size occurred
        elif key == curses.KEY_RESIZE:
            # print global view
            vis_obj.print_global_view()


def flow_graph(heap):
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
        curses.wrapper(flow_graph_logic, heap)
    except curses.error as error:
        print('Screen too small!', file=sys.stderr)
        print(str(error), file=sys.stderr)


if __name__ == "__main__":
    pass
