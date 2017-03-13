"""This module contains methods needed by Perun logic"""
import getopt, sys
import perun.view.memory.cli.flow
import perun.view.memory.cli.peak
import perun.view.memory.cli.most
import perun.view.memory.cli.sum
import perun.view.memory.cli.func
import perun.view.memory.cli.heap_map

__author__ = 'Radim Podola'
__supported_modes = ("flow", "peak", "most", "sum", "func", "heap")


def usage():
    """
    FLOW Seznam alokací (včetně trasy) v~časové ose. Parametrem -s lze kontrolovat časový rozestup.
    PEAK seznam největších alokací (včetně trasy). Parametrem -t(--top=) lze udávat počet zobrazených záznamů.
    MOST Seznam funkcí, kde byly alokace nejčetněji. Parametrem -t(--top) lze udávat počet zobrazených záznamů.
    SUM Seznam funkcí s~největší celkovou hodnotou alokované paměti. Parametrem -t(--topé) lze udávat počet zobrazených záznamů.
    FUNC Alokace vybrané funkce (včetně trasy). Parametr --all zobrazi i~alokace, kterých se funkce pouze účastnila v~trase.
    HEAP Heap mapa paměti v čase (snapshots)
    """
    print("The simple interpretation tool for the memory profile")
    print("\nSimple description ... ")
    print("\nUsage: > options profile.perf")
    print("Options: -h | --help")
    print("Options: -m flow | --mode=flow [-f time | --from=time] [-t time | --to=time]")
    print("Options: -m peak | --mode=peak [-t value | --top=value]")
    print("Options: -m most | --mode=most [-t value | --top=value]")
    print("Options: -m sum | --mode=sum [-t value | --top=value]")
    print("Options: -m func | --mode=func --function=name [-a | --all]")
    print("Options: -m heap | --mode=heap")
    print("Mode parameter defines the operation with the profile")
    print("Value defines number of the records to print, default value is 10")
    print("Time defines timestamp in the timeline of printed records,"
          " as default is printed the whole timeline")
    print("If --all parameter is specified, all the allocations are printed out "
          "(even with partial participation in the call trace)")
    print("Function parameter defines name of the function to focus")


def parse_args():
    """
    Arguments:
        ():

    Returns:
       dict: Parsed arguments
    """
    try:
        opts, args = getopt.getopt(sys.argv[1:], "m:hf:t:a",
                     ["mode=", "help", "from=", 'to=', 'top=', 'all', "function="])
    except getopt.GetoptError as err:
        print(str(err))
        usage()
        sys.exit(2)
    mode = None
    from_time = None
    to_time = None
    t_param = None
    top = None
    all = False
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
            all = True
        elif o == "--function":
            function = a
        else:
            assert False

    if not args:
        print("Error: The profile not provided")
        usage()
        sys.exit(2)
    if len(args) > 1:
        print("Error: Bad args")
        usage()
        sys.exit(2)

    if not mode:
        print("Error: Mode not defined")
        usage()
        sys.exit(2)
    if mode not in __supported_modes:
        print("Error: Mode not supported")
        usage()
        sys.exit(2)
    if mode and t_param:
        if mode == "flow":
            to_time = t_param
        else:
            top = t_param
    if mode == "func" and not function:
        print("Error: Function not defined")
        usage()
        sys.exit(2)
    if not top:
        top = 10

    profile = args[0]

    return {"mode": mode, "from": from_time, "to": to_time, "top": top,
            "all": all, "function": function, "profile": profile}


def show():

    args = parse_args()
    mode = args["mode"]

    if mode == "flow":
        perun.view.memory.cli.flow.print_flow()
    elif mode == "peak":
        perun.view.memory.cli.peak.print_peak()
    elif mode == "most":
        perun.view.memory.cli.most.print_most()
    elif mode == "sum":
        perun.view.memory.cli.sum.print_sum()
    elif mode == "func":
        perun.view.memory.cli.func.print_func()
    else:
        perun.view.memory.cli.heap_map.print_heap_map()


if __name__ == "__main__":
    show()
