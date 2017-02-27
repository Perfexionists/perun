import subprocess
import json

version = 'a5cf40ebf33610c97083b209fc12a36adc3a99ff'
file = './test'
workload = '-a 5'


def run(bin, args):
    """
    Arguments:
        bin(string): binary file to profile
        args(string): executing arguments

    Returns:
        int: return code of executed binary
    """
    syscall = 'LD_PRELOAD="$PWD/malloc.so" ' + bin + ' ' + args

    return subprocess.call(syscall, shell=True)


def make_profile(file, workload, version):
    """
    Arguments:
        file(string): binary file to profile
        workload(string): executing arguments
        version(string): minor version of profile

    Returns:
        bool: True if log was created, False if not
    """
    data = {'type': 'memory'}
    data['minor_version'] = version
    data['file'] = file
    data['workload'] = workload
    data['global'] = {}
    data['snapshots'] = []

    try:
        with open('memory.perf', mode='w') as f:
            json.dump(data, f, indent=2)
    except IOError:
        return False

    return True


print(run(file, workload))
make_profile(file, workload, version)
