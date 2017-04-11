"""This module implement the flow graph visualization of the profile"""
import curses
import curses.textpad
import json
import sys
import math

# debug in console
import heap_representation as heap_representation

__author__ = 'Radim Podola'

class FlowGraphVisualization(object):
    """ Class providing visualization of the allocation flow.

        Visualization is implemented over curses module.

    Attributes:
        MOVE_RIGHT       Constant representing move's direction
                            to the next snapshot.
        MOVE_LEFT       Constant representing move's direction
                            to the previous snapshot.
        NO_MOVE    Constant representing move's direction
                            to the current snapshot.
        INTRO_DELAY         Time delay after intro in [ms]
        ANIMATION_DELAY     Time delay between frames in ANIMATION mode in [ms]
        TIK_FREQ            Tik frequency, visualized in the map. Value defines
                            a number of the fields in the tik.
    """
    MOVE_RIGHT = 1
    MOVE_LEFT = -1
    NO_MOVE = 0
    INTRO_DELAY = 1000
    BAR_SPACE = 15

    # minimal size of the heap map window
    __MIN_ROWS = 40
    __MIN_COLS = 70

    # map's visualising symbols
    BAR_SYM = '#'
    BAR_PEAK_SYM = 'O'
    X_LINES_SYM = '-'
    BORDER_SYM = 'X'

    # text's constants
    __Y_AXIS_TEXT = 'MEMORY [B]'
    __X_AXIS_TEXT = 'SNAPSHOT->'
    __MENU_TEXT = '[Q] QUIT  [I] ENTER INTERACTIVE MODE'
    __INTERACTIVE_MENU_TEXT = '[Q] QUIT  [<] PREVIOUS  [>] NEXT'
    __RESIZE_REQ_TEXT = "Increase the size of your screen, please"

    def __init__(self, window, heap):
        """ Initialize the FLOW GRAPH visualization object

            [{'fields': 0, 'peak': False, 'time': 0.0, 'snapshot': 0}]

        Arguments:
            window(any): initialized curses window
            heap(dict): the heap representation

        :type __peak: int
        """
        # memory allocated peak
        self.__peak = max(item.get('sum_amount', 0)
                          for item in heap['snapshots'])
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

    def show_intro(self):
        """ Print INTRO screen about FLOW GRAPH visualization """
        text = "INTERACTIVE FLOW GRAPH VISUALIZATION!"
        row_pos = curses.LINES // 2
        col_pos = (curses.COLS - len(text)) // 2

        self.__window.addstr(row_pos, col_pos, text, curses.A_BOLD)

        text = "Author: " + __author__
        row_pos = curses.LINES // 2 + 1
        col_pos = (curses.COLS - len(text)) // 2
        self.__window.addstr(row_pos + 1, col_pos, text)

        self.__window.refresh()
        # just for effect :)
        curses.napms(self.INTRO_DELAY)

    def resize_req_print(self):
        """ Print resize request to the window """
        text = self.__RESIZE_REQ_TEXT
        row_pos = curses.LINES // 2
        col_pos = (curses.COLS - len(text)) // 2

        self.__window.clear()
        self.__window.addstr(row_pos, col_pos, text, curses.A_BOLD)

    def menu_print(self, text):
        """ Print text as menu information to the window

        Arguments:
            text(string): string to print as a MENU text
        """
        row_pos = curses.LINES - 1
        col_pos = (curses.COLS - len(text)) // 2

        # clearing line
        self.__window.hline(curses.LINES - 1, 0, ' ', curses.COLS - 1)
        self.__window.addstr(row_pos, col_pos, text, curses.A_BOLD)

    def __y_axis_info_print(self, rows, cols, margin):
        """ Print the Y-axis information

        Arguments:
            rows(int): total number of the screen's rows
            cols(int): total number of the screen's columns
            margin(int): length of the Y-axis info space
        """
        field_size = self.__peak // rows
        info_tik = 5

        self.__window.addstr(0, 0, self.__Y_AXIS_TEXT)

        tik_cnt = 0
        for i, row in enumerate(range(0, rows, info_tik)):
            starting_row = rows - row - 2
            self.__window.addstr(starting_row, 0, str(field_size * tik_cnt))
            tik_cnt += 1

            for col in range(margin + 1, cols):
                if i == 0:
                    break
                self.__window.addch(starting_row, col, self.X_LINES_SYM)


    def __x_axis_info_print(self, rows, cols, margin):
        """ Print the X-axis information

        Arguments:
            rows(int): total number of the screen's rows
            cols(int): total number of the screen's columns
            margin(int): length of the Y-axis info space
        """
        self.__window.addstr(rows - 1, 0, self.__X_AXIS_TEXT)

        for i, bar in enumerate(self.__graph_data):
            col = margin + (i + 1) * self.BAR_SPACE
            self.__window.addstr(rows - 1, col, str(bar['snapshot']))

    def graph_print(self, rows, cols, margin):
        """ Prints the graph data to the screen with borders and axis's info

        Arguments:
            rows(int): total number of the screen's rows
            cols(int): total number of the screen's columns
            margin(int): length of the Y-axis info space
        """
        # set iterator over graph data list
        iterator = iter(self.__graph_data)

        record = next(iterator, None)

        # empty space between graph's bars
        bar_space = FlowGraphVisualization.BAR_SPACE
        for col in range(margin + bar_space, cols, bar_space):

            if record is None:
                break

            if record['peak']:
                # print different symbol representing PEAK bar
                symbol = FlowGraphVisualization.BAR_PEAK_SYM
            else:
                symbol = FlowGraphVisualization.BAR_SYM

            # total rows - number of fields - 2x border field
            start_row = rows - 2 - record['fields']
            # prints BAR
            self.__window.vline(start_row, col, symbol, record['fields'])

            record = next(iterator, None)

        # printing horizontal borders
        self.__window.hline(0, margin, self.BORDER_SYM, cols)
        self.__window.hline(rows - 2, margin, self.BORDER_SYM, cols)
        # printing left vertical border
        self.__window.vline(0, margin, self.BORDER_SYM, rows)

        # printing axises's information
        self.__y_axis_info_print(rows, cols, margin)
        self.__x_axis_info_print(rows, cols, margin)

    def __set_start_snap(self, following_snap, cols):
        """ Sets starting snapshot

        Arguments:
            following_snap(int): number of the snapshot to set

        Returns:
            bool: success of the operation
        """
        """
        # calculating total number of the bars in screen
        bars = cols // FlowGraphVisualization.BAR_SPACE

        # check for maximal bars
        if following_snap > self.__heap['max'] - bars + 1:
            return False

        if following_snap in range(1, self.__heap['max'] + 1):
            self.__current_snap = following_snap
            return True
        else:
            return False
        """
        # calculating total number of the bars in screen
        bars = cols // FlowGraphVisualization.BAR_SPACE

        if following_snap not in range(1, self.__heap['max'] + 1):
            return

        # dynamic moving when resize to occurred
        if self.__current_snap == following_snap:
            if self.__heap['max'] - self.__current_snap + 1 < bars:
                self.__current_snap = following_snap - 1
                return

        # check for maximal bars
        if following_snap > self.__heap['max'] - bars + 1:
            return

        self.__current_snap = following_snap

    def create_partial_decomposition(self, rows, cols):
        # clearing old data
        self.__graph_data = []
        # calculating total number of the bars in screen
        bars = cols // FlowGraphVisualization.BAR_SPACE
        # calculating approximation size of the field
        field_size = self.__peak / rows

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
                    if snap['sum_amount'] == self.__peak:
                        data['peak'] = True
                    else:
                        data['peak'] = False
                    self.__graph_data.append(data)

    def partial_view(self, move):
        """ Redraw the heap map screen to represent the specified snapshot
                Arguments:
            move(int): move of the following snapshot (PREVIOUS/NEXT)
        """
        try:
            rows, cols, margin = self.__get_graph_size()
        except RuntimeError:
            self.resize_req_print()
            return

        # sets first snapshot
        self.__set_start_snap(self.__current_snap + move, cols)

        # creating the flow graph screen decomposition
        self.__window.clear()

        self.create_partial_decomposition(rows, cols)

        # graph print
        self.graph_print(self.__MIN_ROWS, curses.COLS, margin)

        # print interactive menu text
        self.menu_print(self.__INTERACTIVE_MENU_TEXT)

    def interactive_mode(self):
        """ Interactive FLOW GRAPH visualization prompt """
        # print partial view
        self.partial_view(self.NO_MOVE)

        while True:
            # catching key value
            key = self.__window.getch()

            # quit the interactive mode
            if key in (ord('q'), ord('Q')):
                break
            # previous snapshot
            elif key == curses.KEY_LEFT:
                self.partial_view(self.MOVE_LEFT)
            # next snapshot
            elif key == curses.KEY_RIGHT:
                self.partial_view(self.MOVE_RIGHT)
            # change of the screen size occurred
            elif key == curses.KEY_RESIZE:
                self.partial_view(self.NO_MOVE)

    def __get_graph_size(self):
        """ Calculate true graph's size.

            Also check the screen's size limitations.
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
            raise RuntimeError

        # number of the screen's rows == (minimum of rows)
        # - (2*border lines) - 1 (info line)
        graph_rows = self.__MIN_ROWS - 3
        # number of the screen's columns ==
        # (terminal's current number of the columns)
        # - (size of Y-axis info) - 1(border)
        graph_cols = curses.COLS - max_y_axis_len - 1

        return graph_rows, graph_cols, max_y_axis_len

    def create_global_decomposition(self, rows, cols):
        """ Create graph's data decomposition for global view

            Decomposition is saved into instance attribute __graph_data.

        Arguments:
            rows(int): total number of the graph's rows
            cols(int): total number of the graph's columns
        """
        # clearing old data
        self.__graph_data = []
        # calculating total number of the bars in screen
        bars = cols // FlowGraphVisualization.BAR_SPACE
        # calculating approximation size of the field
        field_size = self.__peak / rows

        if self.__heap['max'] >= bars:
            approx_bars = int(math.ceil(self.__heap['max'] / bars))
            bars_cnt = 0
            was_peak = False
            avg_sum = 0
            # heap representation transforming into graph data
            for i, snap in enumerate(self.__heap['snapshots']):
                bars_cnt += 1
                avg_sum += snap['sum_amount']
                if snap['sum_amount'] == self.__peak:
                    was_peak = True
                if bars_cnt == approx_bars:
                    data = {}
                    # number of the fields is average of the approximated bars
                    data['fields'] = int(avg_sum / field_size / approx_bars)
                    data['time'] = snap['time']
                    data['snapshot'] = i + 1
                    data['peak'] = True if was_peak else False
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
                if snap['sum_amount'] == self.__peak:
                    data['peak'] = True
                else:
                    data['peak'] = False
                self.__graph_data.append(data)

    def global_view(self):
        """ Redraw global view of the allocation's FLOW """
        self.__window.clear()

        try:
            # getting true graph's size
            rows, cols, margin = self.__get_graph_size()
        except RuntimeError:
            self.resize_req_print()
            return

        # creating the flow graph screen decomposition
        self.create_global_decomposition(rows, cols)

        # graph print
        self.graph_print(self.__MIN_ROWS, curses.COLS, margin)

        # print menu text
        self.menu_print(self.__MENU_TEXT)


def flow_graph_prompt(window, heap):
    """ FLOW GRAPH visualization prompt

    Arguments:
        window(any): initialized curses window
        heap(dict): the heap representation
    """
    # instantiate of the flow graph visualization object
    vis_obj = FlowGraphVisualization(window, heap)

    # print intro
    vis_obj.show_intro()

    # print global view
    vis_obj.global_view()

    while True:
        # catching key value
        key = window.getch()

        # quit of the visualization
        if key in (ord('q'), ord('Q')):
            break
        # enter interactive mode
        elif key in (ord('i'), ord('I')):
            vis_obj.interactive_mode()
            # print global view
            vis_obj.global_view()
        # change of the screen size occurred
        elif key == curses.KEY_RESIZE:
            # print global view
            vis_obj.global_view()


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
        curses.wrapper(flow_graph_prompt, heap)
    except curses.error as error:
        print('Screen too small!', file=sys.stderr)
        print(str(error), file=sys.stderr)


if __name__ == "__main__":
    with open("memory.perf") as prof_json:
        prof = heap_representation.create(json.load(prof_json))
        flow_graph(prof)
