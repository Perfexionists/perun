"""This module contains methods needed by Perun logic"""
import sys
import getopt
import json
import perun.view.memory.cli.interpretations as interpretations

__author__ = 'Radim Podola'
__supported_short_opts = 'm:hf:t:a'
__supported_long_opts = ("mode=",
                         "help",
                         "from=",
                         'to=',
                         'top=',
                         'all',
                         "function=")
SUPPORTED_MODES = ("flow", "top", "most", "sum", "func", "heap")


def usage(full=False):
    """ Print basic information about tool and usage to standard output.
    Arguments:
        full(bool): specify if also basic info about tool is printed
    """
    if full:
        print('Memory_print - The simple interpretation tool '
              'for the memory profile\n\n'
              'This tool is composed from several interpretation functions.\n'
              'Each of the provides a different point of view '
              'on the memory profile.\n'
              'For now, following functions are available:',
              *SUPPORTED_MODES, '\n')

    print('Usage: options profile.perf\n'
          'Options:\n'
          '[1]  -h|--help\n'
          '[2]  -m top|--mode=top [-t value|--top=value]\n'
          '[3]  -m most|--mode=most [-t value|--top=value]\n'
          '[4]  -m sum|--mode=sum [-t value|--top=value]\n'
          '[5]  -m flow|--mode=flow [-f time|--from=time]'
          '[-t time|--to=time]\n'
          '[6]  -m func|--mode=func --function=name [-a|--all]\n'
          '[7]  -m heap|--mode=heap\n'
          '\n'
          '[2-7] "mode" parameter defines the operation with the profile\n'
          '[2-4] "value" defines number of the records to print, default value'
          ' is 10\n'
          '[5] "time" defines timestamp in the timeline of printed records\n'
          '[6] "--all" defines that all the allocations including function are'
          ' printed out (even with partial participation in the call trace)\n'
          '[6] "function" parameter defines name of the function to search for'
          '\n')


def err_exit(msg, print_help=False):
    """ Print error message to standard error output and exit program
    Arguments:
        msg(string): error message to print
        print_help(bool): specify if also print usage information
    """
    print('Error: ', msg, file=sys.stderr)
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
                                   __supported_short_opts,
                                   __supported_long_opts)
    except getopt.GetoptError as err:
        err_exit(str(err))

    mode = None
    from_time = None
    to_time = None
    t_param = None
    top = None
    get_all = False
    function = None
    for o, a in opts:
        if o in ("-h", "--help"):
            usage(True)
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
        err_exit("The profile not provided")
    if len(args) > 1:
        err_exit("Bad args")
    if not mode:
        err_exit("Mode not defined")
    if mode not in SUPPORTED_MODES:
        err_exit("Mode not supported")
    if mode == "func" and not function:
        err_exit("Function not defined")

    if mode and t_param:
        if mode == "flow":
            to_time = t_param
        else:
            top = t_param
    if not top:
        top = 10

    profile = args[0]

    return {"mode": mode, "from_time": from_time, "to_time": to_time,
            "top": int(top), "all": get_all, "function": function}, profile


def show():
    """ Main function which handle selected options of Memory_print
    Returns:
        string: output of the selected interpretation
    """
    args, profile_name = parse_args(sys.argv[1:])
    mode = args["mode"]
    with open(profile_name) as prof_json:
        profile = json.load(prof_json)

    inter_func = getattr(interpretations, "get_%s" % mode)
    if inter_func:
        output = inter_func(profile, **args)
    else:
        assert False

    if output:
        print(output)


if __name__ == "__main__":
    show()
