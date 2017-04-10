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
        NEXT_SNAPSHOT       Constant representing move's direction
                            to the next snapshot.
        PREV_SNAPSHOT       Constant representing move's direction
                            to the previous snapshot.
        CURRENT_SNAPSHOT    Constant representing move's direction
                            to the current snapshot.
        INTRO_DELAY         Time delay after intro in [ms]
        ANIMATION_DELAY     Time delay between frames in ANIMATION mode in [ms]
        TIK_FREQ            Tik frequency, visualized in the map. Value defines
                            a number of the fields in the tik.
    """
    NEXT_SNAPSHOT = 1
    PREV_SNAPSHOT = -1
    CURRENT_SNAPSHOT = 0
    INTRO_DELAY = 1000
    ANIMATION_DELAY = 1000
    BAR_SPACE = 15

    # minimal size of the heap map window
    __MIN_ROWS = 40
    __MIN_COLS = 70

    # map's visualising symbols
    BAR_SYM = '#'
    BAR_PEAK_SYM = 'O'
    EMPTY_SYM = '-'

    # text's constants
    __Y_AXIS_TEXT = 'MEMORY [B]'
    __MENU_TEXT = '[Q] QUIT  [I] ENTER INTERACTIVE MODE'
    __INTERACTIVE_MENU_TEXT = '[Q] QUIT  [<] PREVIOUS  [>] NEXT  [A] ANIMATE'
    __ANIME_MENU_TEXT = '[S] STOP  [P] PAUSE  [R] RESTART'
    __ANIME_CONTINUE_TEXT = '[C] CONTINUE'
    __RESIZE_REQ_TEXT = "Increase the size of your screen, please"

    def __init__(self, window, heap):
        """ Initialize the FLOW GRAPH visualization object

            [{'fields': 0, 'peak': False, 'time': 0.0}]

        Arguments:
            window(any): initialized curses window
            heap(dict): the heap representation
        """
        # memory allocated peak
        self.__peak = max(item.get('sum_amount', 0)
                          for item in heap['snapshots'])
        # initialized curses window
        self.__window = window
        # heap representation
        self.__heap = heap
        # currently printed map's snapshot
        self.__current_snap = 0
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
        curses.napms(FlowGraphVisualization.INTRO_DELAY)

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

    def y_axis_info_print(self, rows, margin):
        """ Print the Y-axis information

        Arguments:
        """
        field_size = self.__peak // rows
        info_tik = 5

        self.__window.addstr(0, 0, FlowGraphVisualization.__Y_AXIS_TEXT)

        tik_cnt = 0
        for row in range(0, rows, info_tik):
            self.__window.addstr(rows - row - 1, 0, str(field_size * tik_cnt))
            tik_cnt += 1

    def __tik_info_text(self, length, tik_amount):
        """ Build tik information text

        Arguments:
           length(int): length of information text
           tik_amount(int): tik amount

        Returns:
            str: built tik information text
        """
        pass

    def animation_prompt(self):
        """ Animation feature of the HEAP MAP visualization """

        # TODO instead of non-blocing use timeout
        # set non_blocking window.getch()
        self.__window.nodelay(1)

        while True:
            # print ANIMATION MENU text
            self.menu_print(self.__ANIME_MENU_TEXT)

            # delay between individually heap map screens
            curses.napms(FlowGraphVisualization.ANIMATION_DELAY)

            key = self.__window.getch()

            self.following_snapshot(FlowGraphVisualization.NEXT_SNAPSHOT)

            if key in (ord('s'), ord('S')):
                # stop ANIMATION
                self.following_snapshot(FlowGraphVisualization.CURRENT_SNAPSHOT)
                break
            # restart animation from the 1st snapshot
            elif key in (ord('r'), ord('R')):
                self.__set_current_snap(1)
                self.following_snapshot(FlowGraphVisualization.CURRENT_SNAPSHOT)
            # stop animation until 'C' key is pressed
            elif key in (ord('p'), ord('P')):
                while self.__window.getch() not in (ord('c'), ord('C')):
                    self.menu_print(self.__ANIME_CONTINUE_TEXT)
            # change of the screen size occurred
            elif key == curses.KEY_RESIZE:
                self.following_snapshot(FlowGraphVisualization.CURRENT_SNAPSHOT)

        # empty buffer window.getch()
        while self.__window.getch() != -1:
            pass
        # set blocking window.getch()
        self.__window.nodelay(0)

    def graph_print(self, rows, cols, margin):
        """ Prints the screen representation matrix to the window

        Arguments:
            map_data(dict): representing information about map's snapshot
            rows(int): total number of the screen's rows
            cols(int): total number of the screen's columns
            add_length(int): length of the address info space
        """
        iterator = iter(self.__graph_data)

        record = next(iterator, None)

        bar_space = FlowGraphVisualization.BAR_SPACE
        for col in range(margin + bar_space, cols, bar_space):

            if record is None:
                break

            for row in range(rows - record['fields'] - 1, rows - 1):
                if record['peak']:
                    symbol = FlowGraphVisualization.BAR_PEAK_SYM
                else:
                    symbol = FlowGraphVisualization.BAR_SYM
                self.__window.addch(row, col, symbol)

            record = next(iterator, None)

        self.__window.hline(rows - 1, margin, 'X', cols)
        self.__window.vline(0, margin, 'X', rows)

        self.y_axis_info_print(rows, margin)

    def __set_current_snap(self, following_snap):
        """ Sets current snapshot

        Arguments:
            following_snap(int): number of the snapshot to set
        """
        if following_snap in range(1, self.__heap['max'] + 1):
            self.__current_snap = following_snap
            return True
        else:
            return False

    def move_graph(self, direction):
        """ 
        Arguments:
            direction(int): direction of the following snapshot (PREVIOUS/NEXT)

        Returns:
            bool: success of the operation
        """
        if not self.__set_current_snap(self.__current_snap + direction):
            return

        self.partial_view()

    def create_partial_decomposition(self, rows, cols):
        pass

    def partial_view(self):
        """ Redraw the heap map screen to represent the specified snapshot
            Tady proste vypočitam ktere snapshoty z pole použí
        """
        self.__window.clear()

        try:
            rows, cols, margin = self.__get_graph_size()
        except RuntimeError:
            self.resize_req_print()
            return

        # creating the flow graph screen decomposition
        self.create_partial_decomposition(rows, cols)

        # graph print
        self.graph_print(FlowGraphVisualization.__MIN_ROWS, curses.COLS, margin)

        # print interactive menu text
        self.menu_print(self.__INTERACTIVE_MENU_TEXT)

    def interactive_mode(self):
        # print partial view
        self.move_graph(FlowGraphVisualization.CURRENT_SNAPSHOT)

        while True:
            # catching key value
            key = self.__window.getch()

            # quit the interactive mode
            if key in (ord('q'), ord('Q')):
                break
            # previous snapshot
            elif key == curses.KEY_LEFT:
                self.move_graph(FlowGraphVisualization.PREV_SNAPSHOT)
            # next snapshot
            elif key == curses.KEY_RIGHT:
                self.move_graph(FlowGraphVisualization.NEXT_SNAPSHOT)
            # start of the animation
            elif key in (ord('a'), ord('A')):
                pass
                # self.animation_prompt()
            # change of the screen size occurred
            elif key == curses.KEY_RESIZE:
                self.move_graph(FlowGraphVisualization.CURRENT_SNAPSHOT)

    def __get_graph_size(self):
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

        # number of the screen's rows == (minimum of rows) - (2*border lines)
        graph_rows = self.__MIN_ROWS - 2
        # number of the screen's columns == (terminal's current number of
        # the columns) - (size of Y-axis info)
        graph_cols = curses.COLS - max_y_axis_len

        return graph_rows, graph_cols, max_y_axis_len

    def create_global_decomposition(self, rows, cols):
        self.__graph_data = []
        bars = cols // FlowGraphVisualization.BAR_SPACE

        # calculating field size
        field_size = self.__peak / rows

        if self.__heap['max'] > bars:
            approx_bars = int(math.ceil(self.__heap['max'] / bars))
            bars_cnt = 0
            was_peak = False
            avg_sum = 0
            for snap in self.__heap['snapshots']:
                bars_cnt += 1
                avg_sum += snap['sum_amount'] / field_size
                if snap['sum_amount'] == self.__peak:
                    was_peak = True
                if bars_cnt == approx_bars:
                    data = {}
                    data['fields'] = int(avg_sum / approx_bars)
                    data['time'] = snap['time']
                    data['peak'] = True if was_peak else False
                    self.__graph_data.append(data)
                    bars_cnt = 0
                    avg_sum = 0
                    was_peak = False

        else:
            for snap in self.__heap['snapshots']:
                data = {}
                data['fields'] = int(math.ceil(snap['sum_amount'] / field_size))
                data['time'] = snap['time']
                data['peak'] = True if snap['sum_amount'] == self.__peak else False
                self.__graph_data.append(data)

    def global_view(self):
        """ Redraw global or partial view of the allocation's FLOW
        """
        self.__window.clear()

        try:
            rows, cols, margin = self.__get_graph_size()
        except RuntimeError:
            self.resize_req_print()
            return

        # creating the flow graph screen decomposition
        self.create_global_decomposition(rows, cols)

        # graph print
        self.graph_print(FlowGraphVisualization.__MIN_ROWS, curses.COLS, margin)

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
