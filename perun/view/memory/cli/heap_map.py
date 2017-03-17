"""This module implement the heap map visualization of the profile"""
import os


__author__ = 'Radim Podola'


def start_heap_map(profile):
    try:
        rows, columns = os.popen('stty size', 'r').read().split()
        rows = int(rows)
        columns = int(columns)
    except ValueError:
        rows = 40
        columns = 100

    for x in range(rows):
        if x == 0:
            print('#'*columns)
        elif x == rows - 1:
            print('#'*columns)
        else:
            for y in range(columns):
                if y == 0:
                    print('#', end='')
                elif y == columns - 1:
                    print('#')
                else:
                    print('+', end='')


    print(rows, columns)


if __name__ == "__main__":
    pass
