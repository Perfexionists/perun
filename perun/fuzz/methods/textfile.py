"""Collects fuzzing rules specific for text files."""

import random 

__author__ = 'Matus Liscinsky'


def fuzz_double_line(lines):
    """ Doubles the size of a line by its duplicating, 1-10 times.
    
    Example:
        "The quick brown fox." -> "The quick brown fox.The quick brown fox."

    :param list lines: lines of the input file, which was chosen for mutating
    """
    for _ in range(random.randint(1,10)):
        rand = random.randrange(len(lines))
        lines[rand] = lines[rand][:-1] *2 + lines[rand][-1:]

def fuzz_append_ws(lines):
    """ Appends 100 spaces at to a line, 1-10 times.
    
    Example:
        "<author>Gambardella, Matthew</author>" -> "<author>Gambardella, Matthew</author>                    
                                                                            "

    :param list lines: lines of the input file, which was chosen for mutating
    """
    for _ in range(random.randint(1,10)):
        rand = random.randrange(len(lines))
        lines[rand] = lines[rand][:-1] + " "*100 + lines[rand][-1:]

def fuzz_bloat_word(lines):
    """ Creates big words by removing spaces of a line, 1-10 times.
   
    Example:
        "The quick brown fox." -> "Thequickbrownfox."

    :param list lines: lines of the input file, which was chosen for mutating
    """    
    for _ in range(random.randint(1,10)):    
        rand = random.randrange(len(lines))
        lines[rand] = lines[rand].replace(" ","")

def multiplicate_ws(lines):
    """ Replaces every single white space with 10 white spaces, 1-10 times.
   
    Example:
        "The quick brown fox." -> "The quick brown fox.,                                       
                                                                            
                    The quick brown fox."

    :param list lines: lines of the input file, which was chosen for mutating
    """    
    for _ in range(random.randint(1,10)):
        rand = random.randrange(len(lines))
        lines[rand] = lines[rand].replace(" "," "*10, 10)

def prepend_ws(lines):
    """ Prepend a line with 100 white spaces, 1-10 times.
   
    Example:
        "The quick brown fox." -> "                      
                                                           The quick brown fox."

    :param list lines: lines of the input file, which was chosen for mutating
    """ 
    for _ in range(random.randint(1,10)):
        rand = random.randrange(len(lines))
        lines[rand] = " "*100 + lines[rand]

def fuzz_duplicate_line(lines):
    """ Duplicate random line in file, 1-10 times.
   
    Example:
        "The quick brown fox." -> "The quick brown fox."
                                  "The quick brown fox."

    :param list lines: lines of the input file, which was chosen for mutating
    """ 
    for _ in range(random.randint(1,10)):
        rand = random.randrange(len(lines))
        lines.insert(rand, lines[random.randint(0,len(lines)-1)])

def fuzz_sort_line(lines):
    """ Sorts the words of a line alphabetically, 1-10 times.
   
    Example:
        "The quick brown fox." -> "brown fox quick The"

    :param list lines: lines of the input file, which was chosen for mutating
    """ 
    for _ in range(random.randint(1,10)):
        rand = random.randrange(len(lines))
        words = lines[rand].split() 
        lines[rand] = " ".join(sorted(words))
        
def repeat_word(lines):
    """ 10 times repeats a random word and append it to a line, 1-10 times.
   
    Example:
        "The quick brown fox." -> "The quick brown fox.brown brown brown brown

    :param list lines: lines of the input file, which was chosen for mutating
    """ 
    for _ in range(random.randint(1,10)):
        rand = random.randrange(len(lines))
        try:
            word = random.choice(lines[rand].split())
            lines[rand] = lines[rand][:-1] + (" "+word)*10 + lines[rand][-1:]
        except IndexError:
            pass

def del_line(lines):
    """ Deletes random line, 1-10 times.
    Example:
        "The quick brown fox." -> ""

    :param list lines: lines of the input file, which was chosen for mutating
    """ 
    for _ in range(random.randint(1,10)):
        if len(lines):
            del lines[random.randint(0, len(lines)-1)]

def del_word(lines):
    """ Deletes random word of line, 1-10 times.
    Example:
        "The quick brown fox." -> " quick brown fox."

    :param list lines: lines of the input file, which was chosen for mutating
    """ 
    for _ in range(random.randint(1,10)):
        rand = random.randrange(len(lines))
        try:
            word = random.choice(lines[rand].split())
            lines[rand] = lines[rand].replace(word,"")
        except IndexError:
            pass

def del_char(lines):
    """ Deletes random character from random line, 1-10 times.
    Example:
        "The quick brown fox." -> "The quick brown fo."

    :param list lines: lines of the input file, which was chosen for mutating
    """     
    for _ in range(random.randint(1,10)):
        rand = random.randrange(len(lines))
        try:
            char = lines[rand][random.randrange(len(lines[rand]))]
            lines[rand] = lines[rand].replace(char, "")
        except ValueError:
            pass


fuzzing_methods = [ (fuzz_double_line, "Double the size of random line"), 
                    (fuzz_append_ws, "Append WS at the end of the line"), 
                    (fuzz_bloat_word, "Remove WS of random line"), 
                    (multiplicate_ws, "Multiplicate WS of random line"), 
                    (prepend_ws, "Prepend WS to random line"), 
                    (fuzz_duplicate_line, "Duplicate random line"), 
                    (fuzz_sort_line, "Sort words of random line"), 
                    (repeat_word, "Multiplicate word of random line"), 
                    (del_line, "Remove random line"), 
                    (del_word, "Remove random word of line"), 
                    (del_char, "Remove random character of line ")]


