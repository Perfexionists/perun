"""This module contains methods needed by Perun logic"""
import sys
import getopt
import json
from perun.view.memory.cli.flow import get_flow
from perun.view.memory.cli.top import get_top
from perun.view.memory.cli.most import get_most
from perun.view.memory.cli.sum import get_sum
from perun.view.memory.cli.func import get_func
import perun.view.memory.cli.heap_map

__author__ = 'Radim Podola'
__supported_modes = ("flow", "top", "most", "sum", "func", "heap")
__supported_long_opts = ["mode=",
                         "help",
                         "from=",
                         'to=',
                         'top=',
                         'all',
                         "function="]


def usage():
    """
    FLOW Seznam alokací (včetně trasy) v~časové ose.
        Parametrem -s lze kontrolovat časový rozestup.
    TOP seznam největších alokací (včetně trasy).
        Parametrem -t(--top=) lze udávat počet zobrazených záznamů.
    MOST Seznam funkcí, kde byly alokace nejčetněji.
        Parametrem -t(--top) lze udávat počet zobrazených záznamů.
    SUM Seznam funkcí s~největší celkovou hodnotou alokované paměti.
        Parametrem -t(--topé) lze udávat počet zobrazených záznamů.
    FUNC Alokace vybrané funkce (včetně trasy).
        Parametr --all zobrazi i~alokace, kterých se funkce pouze účastnila v~trase.
    HEAP Heap mapa paměti v čase (snapshots)
    """
    print("The simple interpretation tool for the memory profile")
    print("\nSimple description ... ")
    print("\nUsage: > options profile.perf")
    print("Options: -h | --help")
    print("Options: -m flow | --mode=flow [-f time | --from=time] "
          "[-t time | --to=time]")
    print("Options: -m top | --mode=top [-t value | --top=value]")
    print("Options: -m most | --mode=most [-t value | --top=value]")
    print("Options: -m sum | --mode=sum [-t value | --top=value]")
    print("Options: -m func | --mode=func --function=name [-a | --all]")
    print("Options: -m heap | --mode=heap")
    print("Mode parameter defines the operation with the profile")
    print("Value defines number of the records to print, default value is 10")
    print("Time defines timestamp in the timeline of printed records,"
          " as default is printed the whole timeline")
    print("If --all parameter is specified, "
          "all the allocations are printed out "
          "(even with partial participation in the call trace)")
    print("Function parameter defines name of the function to focus")


def err_exit(msg, print_help=False):
    print(msg)
    if print_help:
        usage()
    sys.exit(2)


def parse_args(argv):
    """ Parse arguments
    Arguments:
        argv(list): arguments to parse

    Returns:
       dict: parsed arguments
    """
    try:
        opts, args = getopt.getopt(argv,
                                   "m:hf:t:a",
                                   __supported_long_opts)
    except getopt.GetoptError as err:
        err_exit(str(err), True)

    mode = None
    from_time = None
    to_time = None
    t_param = None
    top = None
    get_all = False
    function = None
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-m", "--mode"):
            mode = a
        elif o in ("-f", "--from"):
            from_time = a
        elif o == "--to":
            to_time = a
        elif o == "-t":
            t_param = a
        elif o == "--top":
            top = a
        elif o in ("-a", "--all"):
            get_all = True
        elif o == "--function":
            function = a
        else:
            assert False

    if not args:
        err_exit("Error: The profile not provided", True)
    if len(args) > 1:
        err_exit("Error: Bad args", True)
    if not mode:
        err_exit("Error: Mode not defined", True)
    if mode not in __supported_modes:
        err_exit("Error: Mode not supported", True)
    if mode == "func" and not function:
        err_exit("Error: Function not defined", True)

    if mode and t_param:
        if mode == "flow":
            to_time = t_param
        else:
            top = t_param
    if not top:
        top = 10

    profile = args[0]

    return {"mode": mode, "from": from_time, "to": to_time, "top": top,
            "all": get_all, "function": function, "profile": profile}


def show():

    output = None

    args = parse_args(sys.argv[1:])
    mode = args["mode"]
    top = int(args["top"])
    with open(args["profile"]) as prof_file:
        profile = json.load(prof_file)

    if mode == "flow":
        output = get_flow(profile, args["from"], args["to"])
    elif mode == "top":
        output = get_top(profile, top)
    elif mode == "most":
        output = get_most(profile, top)
    elif mode == "sum":
        output = get_sum(profile, top)
    elif mode == "func":
        output = get_func(profile, args["function"], args["all"])
    elif mode == "heap":
        perun.view.memory.cli.heap_map.print_heap_map(profile)
    else:
        assert False

    if output:
        print(output)

if __name__ == "__main__":
    show()
