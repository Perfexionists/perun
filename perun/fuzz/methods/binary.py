"""Collects fuzzing rules specific for binary files."""

import random

__author__ = 'Matus Liscinsky'

RULES_ITERATIONS = 10

def insert_byte(lines):
    """ Selects random line and inserts a random byte to any position.

    Example:
        Defenestration -> Def%enestration

    :param list lines: lines of the file in list
    """
    for _ in range(random.randint(1, RULES_ITERATIONS)):
        rand = random.randrange(len(lines))
        index = random.randrange(len(lines[rand]))
        num = random.randrange(255)
        byte = chr(num).encode()
        lines[rand] = lines[rand][:index] + byte + lines[rand][index:]


def remove_byte(lines):
    """ Selects random line and removes random byte.

    Example:
        #ef15ac -> ef15ac 

    :param list lines: lines of the file in list
    """
    for _ in range(random.randint(1, RULES_ITERATIONS)):
        rand = random.randrange(len(lines))
        index = random.randrange(len(lines[rand]))
        lines[rand] = lines[rand][:index] + lines[rand][index+1:]


def byte_swap(lines):
    """ Selects two random lines and switch theirs random bytes.

    Example:
    before:
        Defenestration
        #ef15ac
    after:
        Def5nestration
        #ef1eac

    :param list lines: lines of the file in list
    """
    for _ in range(random.randint(1, RULES_ITERATIONS)):
        line_num1 = random.randrange(len(lines))
        line_num2 = random.randrange(len(lines))

        a = chr(lines[line_num1][random.randrange(len(lines[line_num1]))])
        b = chr(lines[line_num2][random.randrange(len(lines[line_num2]))])

        lines[line_num1] = lines[line_num1].replace(a.encode(), b.encode())
        lines[line_num2] = lines[line_num2].replace(b.encode(), a.encode())


def bite_flip(lines):
    """ Selects random line and flips random bite.

    Example:
    before:
        Defenestration
    after:
        Defenestratinn

    :param list lines: lines of the file in list
    """
    for _ in range(random.randint(1, RULES_ITERATIONS)):
        rand = random.randrange(len(lines))
        index = random.randrange(len(lines[rand]))

        char_ascii_val = lines[rand][index]
        char_ascii_val = char_ascii_val ^ (1 << (random.randrange(8)))
        lines[rand] = lines[rand][:index] + \
            chr((char_ascii_val)).encode() + lines[rand][index + 1:]


def remove_zero_byte(lines):
    """ Selects random line and removes first occasion of zero byte.

    Example:
        This is C string.\0 You are gonna love it.\0 -> This is string. You are gonna love it.\0

    :param list lines: lines of the file in list
    """
    for _ in range(random.randint(1, RULES_ITERATIONS)):
        rand = random.randrange(len(lines))
        lines[rand] = lines[rand].replace(b"\0", b"", 1)


def insert_zero_byte(lines):
    """ Selects random line and inserts zero byte to any position.

    Example:
        This is C string.\0You are gonna love it.\0 -> This is C\0 string.\0You are gonna love it.\0 

    :param list lines: lines of the file in list
    """
    for _ in range(random.randint(1, RULES_ITERATIONS)):
        rand = random.randrange(len(lines))
        index = random.randrange(len(lines[rand]))
        lines[rand] = lines[rand][:index] + b'\0' + lines[rand][index:]


fuzzing_methods = [(remove_zero_byte, "Remove zero byte"),
                   (insert_zero_byte, "Insert zero byte to random position"),
                   (insert_byte, "Insert a random byte to random position"),
                   (remove_byte, "Remove random byte"),
                   (byte_swap, "Switch two random bytes"),
                   (bite_flip, "Flip random bite")]
