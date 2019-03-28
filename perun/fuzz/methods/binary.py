"""Collects fuzzing rules specific for binary files."""

import random

__author__ = 'Matus Liscinsky'


def add_byte(lines):
    """ Selects random line and adds random byte to any position, 1-10 times.
        
    Example:
        Defenestration -> Def%enestration
    
    :param list lines: lines of the file in list
    """
    for _ in range(random.randint(1,10)):
        rand = random.randrange(len(lines))
        index = random.randrange(len(lines[rand]))
        num = random.randrange(255)
        byte = chr(num).encode()
        lines[rand] = lines[rand][:index] + byte + lines[rand][index:]



def remove_byte(lines):
    """ Selects random line and removes random byte, 1-10 times.
    
    Example:
        #ef15ac -> ef15ac 

    :param list lines: lines of the file in list
    """
    for _ in range(random.randint(1,10)):
        rand = random.randrange(len(lines))
        index = random.randrange(len(lines[rand]))
        lines[rand] = lines[rand][:index] + lines[rand][index+1:]

def byte_swap(lines):
    """ Selects 2 random lines and switch theirs random bytes, 1-10 times.
    
    Example:
    before:
        Defenestration
        #ef15ac
    after:
        Def5nestration
        #ef1eac

    :param list lines: lines of the file in list
    """
    for _ in range(random.randint(1,10)):
        line_num1 = random.randrange(len(lines))
        line_num2 = random.randrange(len(lines))

        a = chr(lines[line_num1][random.randrange(len(lines[line_num1]))])
        b = chr(lines[line_num2][random.randrange(len(lines[line_num2]))])

        lines[line_num1] = lines[line_num1].replace(a.encode(), b.encode())
        lines[line_num2] = lines[line_num2].replace(b.encode(), a.encode())
       
def remove_zero_byte(lines):
    """ Selects random line and removes first occasion of zero byte, 1-10 times.
    
    Example:
        This is C string.\0 You are gonna love it.\0 -> This is string. You are gonna love it.\0

    :param list lines: lines of the file in list
    """
    for _ in range(random.randint(1,10)):
        rand = random.randrange(len(lines))
        lines[rand] = lines[rand].replace(b"\0", b"", 1)


def add_zero_byte(lines):
    """ Selects random line and adds zero byte to any position, 1-10 times.
    
    Example:
        This is C string.\0You are gonna love it.\0 -> This is C\0 string.\0You are gonna love it.\0 

    :param list lines: lines of the file in list
    """
    for _ in range(random.randint(1,10)):
        rand = random.randrange(len(lines))
        index = random.randrange(len(lines[rand]))
        lines[rand] = lines[rand][:index] + b'\0' + lines[rand][index:]


fuzzing_methods = [(remove_zero_byte, "Selects random line and removes first occasion of zero byte"),
                   (add_zero_byte, "Selects random line and adds zero byte to any position"),
                   (add_byte, "Selects random line and adds random byte to any position"),
                   (remove_byte, "Selects random line and removes random byte"),
                   (byte_swap, "Selects 2 random lines and switch theirs random bytes")]

