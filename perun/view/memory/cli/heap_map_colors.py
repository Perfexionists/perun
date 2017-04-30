"""This module implement colors module for the HEAP MAP visualization"""
import curses
from random import randint

__author__ = 'Radim Podola'


class HeapMapColors(object):
    """ Class providing operations with colors used in the heap map.

        Another colors module can be add
        by implementing it's initialization method.
        For now, only curses colors module is implemented.

    Attributes:
        border        Color representing border.
        free_field    Color representing free field.
        info_text     Color representing informative text.
        CURSES_COLORS Constant for initializing curses color module.
    """
    CURSES_COLORS = 1

    def __init__(self, colors_type):
        """ Initialize HEAP MAP COLORS object.

        Arguments:
            colors_type(int): type of colors
        """
        if colors_type == HeapMapColors.CURSES_COLORS:
            self.__init_curses_colors()

    def __init_curses_colors(self):
        """ Initialize colors over curses colors module.

            Initialize the curses colors module
            and the colors for later use in the heap map.

            16 == black
            -1 == implicit color
        """
        # initializing the curses color module
        curses.start_color()
        curses.use_default_colors()

        # good visible colors
        self.__good_colors = (
            1, 2, 3, 4, 5, 6, 7, 11, 14, 17, 21, 19,
            22, 23, 27, 33, 30, 34, 45, 41, 46, 49,
            51, 52, 54, 56, 58, 59, 62, 65, 71, 76,
            89, 91, 94, 95, 124, 125, 126, 127, 129,
            130, 131, 154, 156, 159, 161, 166, 167,
            178, 195, 197, 199, 203, 208, 210, 211,
            214, 220, 226, 229, 255)
        # structure for saving corresponding allocation
        # with their specific color representation
        self.__color_records = []

        start_pair_number = 1
        for i in self.__good_colors:
            curses.init_pair(start_pair_number, 16, i)
            start_pair_number += 1

        # border color
        curses.init_pair(start_pair_number, 16, 16)
        self.border = start_pair_number
        start_pair_number += 1
        # free field color
        curses.init_pair(start_pair_number, -1, 8)
        # for better grey scale printing
        curses.init_pair(start_pair_number, 16, 7)
        self.free_field = start_pair_number
        start_pair_number += 1
        # info text color
        curses.init_pair(start_pair_number, -1, 16)
        self.info_text = start_pair_number

        # HEAT colors from min to most
        self.__heat_colors = (44, 8, 59, 54, 52, 1, 37, 24)

    def heap_field_color(self, uid):
        """ Pick a right color for the given field.

        Arguments:
            uid(dict): allocation's information

        Returns:
            int: number of the picked color
        """
        if uid is None:
            return self.free_field

        for item in self.__color_records:
            if (uid['function'] == item['uid']['function'] and
                    uid['source'] == item['uid']['source']):
                return item['color']

        color = randint(1, len(self.__good_colors))
        self.__color_records.append({'uid': uid, 'color': color})

        return color

    def heat_field_color(self, access):
        """ Pick a right shade of HEAT color for the given number of access.

        Arguments:
            access(int): number of access

        Returns:
            int: number of the picked color
        """
        if access >= len(self.__heat_colors):
            return self.__heat_colors[-1]
        else:
            return self.__heat_colors[access]

    def demonstrate_curses_colors(self, window):
        """ Demonstrate curses good colors by print each of them to the window

        Arguments:
            window(any): initialized curses window
        """
        for i in range(1, len(self.__good_colors)):
            color_str = str(i) + ' '
            window.addnstr(color_str, len(color_str), curses.color_pair(i))


if __name__ == "__main__":
    pass
