"""This module implement the heap map visualization of the profile"""
import os
import time
import curses
import curses.textpad

__author__ = 'Radim Podola'


INTRO = "HEAP MAP!"
MENU = '[Q] QUIT  [<] PREVIOUS  [>] NEXT  [A] ANIMATE  [S] SAVE'
RESIZE_REQ = "Resize screen up, please"


def get_field():

    return 's'


def get_heap_map(rows, cols, snap):
    # todo misto barevneho rozlišeni random asci znaky

    map = ''

    for x in range(rows):
        if x == 0:
            map += '#'*cols + '\n'
        elif x == rows - 1:
            map += '#'*cols + '\n'
        else:
            for y in range(cols):
                if y == 0:
                    map += '#'
                elif y == cols - 1:
                    map += '#' + '\n'
                else:
                    map += get_field()

    return map


def heap_map_prompt(stdscr, profile):
    rows, cols = 40, 100
    snapshot = 1

    curses.use_default_colors()
    # set cursor invisible
    curses.curs_set(0)
    # INTRO screen
    stdscr.addstr(int(curses.LINES/2),
                  int((curses.COLS - len(INTRO))/2),
                  INTRO, curses.A_BLINK)
    stdscr.refresh()
    time.sleep(2)

    while True:
        curses.update_lines_cols()
        stdscr.clear()
        try:
            stdscr.addstr(curses.LINES - rows - 1, 0,
                          get_heap_map(rows, cols, snapshot))
            map_text =  ' SNAPSHOT: ' + str(snapshot) + '/' + str(profile['max']) + ' '
            stdscr.addstr(curses.LINES - rows - 1,
                          int((cols - len(map_text))/2),
                          map_text)
            stdscr.addstr(curses.LINES - 1,
                          int((curses.COLS - len(MENU))/2),
                          MENU, curses.A_BOLD)
        except curses.error:
            stdscr.clear()
            stdscr.addstr(int(curses.LINES/2),
                          int((curses.COLS - len(RESIZE_REQ))/2),
                          RESIZE_REQ)
            stdscr.addstr('\n')
            stdscr.addstr(curses.LINES - 1,
                          int((curses.COLS - len(MENU))/2),
                          MENU, curses.A_BOLD)

        stdscr.refresh()
        key = stdscr.getch()
        if key == ord('q') or key == ord('Q'):
            break
        elif key == curses.KEY_LEFT:
            if snapshot > 1:
                snapshot -= 1
        elif key == curses.KEY_RIGHT:
            if snapshot < profile['max']:
                snapshot += 1
        elif key == ord('s') or key == ord('S'):
            pass
        elif key == ord('a') or key == ord('A'):
            pass



def heap_map(profile):
    """ curses.wrapper handle initializations of the console and
    restoring settings when exceptions is thrown

    stdscr = curses.initscr()

    turn off automatic echoing of keys to the screen
    curses.noecho()

    react to keys instantly, without requiring the Enter key to be pressed
    curses.cbreak()

    enable keypad mode for special keys s.a. HOME
    stdscr.keypad(True)

    Arguments:
        ():

    Returns:

    """
    calculated = calculate_map(profile)

    # after integration remove try block
    try:
        curses.wrapper(heap_map_prompt, calculated)
    except Exception as e:
        print(str(e))


def calculate_map(profile):
    """ Will calculate map for every snapshot from profile,
        saving it to some global list??

        List will provide mapping between address and func
    Arguments:
        ():

    Returns:
        dict: parsed and calculated profile
    """
    return {'max': 15}


if __name__ == "__main__":
    heap_map('sadasd')