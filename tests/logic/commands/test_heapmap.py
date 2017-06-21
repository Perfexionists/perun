"""Basic tests for heap and heap map. Tests both logic and outputs to the terminal.

Uses custom mock object for curses, that implements basic stuff.
"""

import curses

from copy import deepcopy

import perun.utils.profile_converters as converters
import perun.view.heapmap.heap_map as heap_map
import perun.view.heapmap.heap_map_colors as heap_colours


class MockCursesWindow(object):
    """Mock object for testing window in the heap"""
    def __init__(self, lines, cols):
        """Initializes the mock object with line height and cols width"""
        self.lines = lines
        self.cols = cols

        # Top left corner
        self.cursor_x = 0
        self.cursor_y = 0

        self.matrix = [[' ']*cols for _ in range(1, lines+1)]

    character_stream = iter([
        curses.KEY_RIGHT, curses.KEY_LEFT, ord('4'), ord('6'), ord('8'), ord('5'), ord('h'),
        ord('q'), ord('q')
    ])

    def getch(self):
        """Returns character stream tuned for the testing of the logic"""
        return MockCursesWindow.character_stream.__next__()

    def getyx(self):
        """Returns the current cursor position"""
        return self.cursor_y, self.cursor_x

    def getmaxyx(self):
        """Returns the size of the mocked window"""
        return self.lines, self.cols

    def addch(self, y_coord, x_coord, symbol, *_):
        """Displays character at (y, x) coord

        Arguments:
            y_coord(int): y coordinate
            x_coord(int): x coordinate
            symbol(char): symbol displayed at (y, x)
        """
        if 0 <= x_coord < self.cols and 0 <= y_coord < self.lines:
            self.matrix[y_coord][x_coord] = symbol

    def addstr(self, y_coord, x_coord, dstr, *_):
        """Displays string at (y, x) coord

        Arguments:
            y_coord(int): y coordinate
            x_coord(int): x coordinate
            dstr(str): string displayed at (y, x)
        """
        x_coord = x_coord or self.cursor_x
        y_coord = y_coord or self.cursor_y
        str_limit = self.cols - x_coord
        self.addnstr(y_coord, x_coord, dstr, str_limit)

    def addnstr(self, y_coord, x_coord, dstr, str_limit, *_):
        """Displays string at (y, x) coord limited to str_limit

        Arguments:
            y_coord(int): y coordinate
            x_coord(int): x coordinate
            dstr(str): string displayed at (y, x)
            str_limit(int): limit length for dstr to be displayed in matrix
        """
        chars = list(dstr)[:str_limit]
        self.matrix[y_coord][x_coord:(x_coord+len(chars))] = chars

    def hline(self, y_coord, x_coord, symbol, line_len=None, *_):
        """Wrapper for printing the line and massaging the parameters

        Arguments:
            y_coord(int): y coordinate
            x_coord(int): x coordinate
            symbol(char): symbol that is the body of the horizontal line
            line_len(int): length of the line
        """
        if not line_len:
            self._hline(self.cursor_y, self.cursor_x, y_coord, x_coord)
        else:
            self._hline(y_coord, x_coord, symbol, line_len)

    def _hline(self, y_coord, x_coord, symbol, line_len):
        """Core function for printing horizontal line at (y, x) out of symbols

        Arguments:
            y_coord(int): y coordinate
            x_coord(int): x coordinate
            symbol(char): symbol that is the body of the horizontal line
            line_len(int): length of the line
        """
        chstr = symbol*line_len
        self.addnstr(y_coord, x_coord, chstr, line_len)

    def move(self, y_coord, x_coord):
        """Move the cursor to (y, x)

        Arguments:
            y_coord(int): y coordinate
            x_coord(int): x coordinate
        """
        self.cursor_x = x_coord
        self.cursor_y = y_coord

    def clear(self):
        """Clears the matrix"""
        self.matrix = [[' ']*self.cols for _ in range(1, self.lines+1)]

    def clrtobot(self):
        """Clears window from cursor to the bottom right corner"""
        self.matrix[self.cursor_y][self.cursor_x:self.cols] = [' ']*(self.cols-self.cursor_x)
        for line in range(self.cursor_y+1, self.lines):
            self.matrix[line] = [' ']*self.cols

    def refresh(self):
        """Refreshes the window, not needed"""
        pass

    def __str__(self):
        """Returns string representation of the map"""
        top_bar = "="*(self.cols + 2) + "\n"
        return top_bar + "".join(
            "|" + "".join(line) + "|\n" for line in self.matrix
        ) + top_bar


def donothing(*_):
    """Helper function for monkeypatching stuff to do nothing"""
    pass


def returnnothing(*_):
    """Helper function for monkeypatching stuff to return nothing"""
    return ''


def test_heat_map(monkeypatch, memory_profiles):
    """Test heap map without the logic and anything, hopefully will work

    Expecting no error and some layer of testing
    """
    monkeypatch.setattr(curses, 'curs_set', donothing)
    monkeypatch.setattr(curses, 'color_pair', returnnothing)

    lines, cols = 40, 80
    mock_window = MockCursesWindow(lines, cols)

    for memory_profile in memory_profiles:
        heat_map_representation = converters.create_heat_map(memory_profile)
        hm_visualization = heap_map.HeapMapVisualization(
            mock_window, heat_map_representation, heap_colours.HeapMapColors.NO_COLORS
        )
        hm_visualization.draw_heat_map()

        str_window = str(mock_window)
        assert str(heat_map_representation['stats']['min_address']) in str_window
        # Correctly shows the ticks
        for tick in map(str, range(0, 110, 17)):
            assert tick in str_window
        assert 'HEAT INFO' in str_window
        assert "Number of accesses" in str_window


def test_heap_map(monkeypatch, memory_profiles):
    """Test heap map without the logic and anything, according to the mock window

    Expecting no error and some output to the mocked curses window
    """
    monkeypatch.setattr(curses, 'curs_set', donothing)
    monkeypatch.setattr(curses, 'color_pair', returnnothing)

    lines, cols = 40, 80
    mock_window = MockCursesWindow(lines, cols)

    for memory_profile in memory_profiles:
        heap_map_representation = converters.create_heap_map(memory_profile)
        hm_visualization = heap_map.HeapMapVisualization(
            mock_window, heap_map_representation, heap_colours.HeapMapColors.NO_COLORS
        )
        hm_visualization.draw_heap_map()
        hm_visualization.following_snapshot(heap_map.HeapMapVisualization.NEXT_SNAPSHOT)

        str_window = str(mock_window)
        assert str(heap_map_representation['stats']['min_address']) in str_window
        # Correctly shows the ticks
        for tick in map(str, range(0, 110, 17)):
            assert tick in str_window
        assert "1/{}".format(len(memory_profile['snapshots'])) in str_window


def test_heap_and_heat_logic(monkeypatch, memory_profiles):
    """Test heap map and heat map together with their logics

    Expecting no error, printed information and everything correct
    """
    monkeypatch.setattr(curses, 'napms', donothing)
    monkeypatch.setattr(curses, 'curs_set', donothing)
    monkeypatch.setattr(curses, 'color_pair', returnnothing)

    lines, cols = 40, 80
    mock_window = MockCursesWindow(lines, cols)

    for memory_profile in memory_profiles:
        heap_map_repr = converters.create_heap_map(deepcopy(memory_profile))
        heat_map_repr = converters.create_heat_map(memory_profile)
        colour_mode = heap_colours.HeapMapColors.NO_COLORS
        heap_map.heap_map_logic(mock_window, heap_map_repr, heat_map_repr, colour_mode)
