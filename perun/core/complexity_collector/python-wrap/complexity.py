""" Temporary complexity collector starter module.

"""


import before
import collect

# Test configuration dictionary
config = {
    'target_dir': './target',
    'files': [
        '../../main.cpp',
        '../../SLList.h',
        '../../SLListcls.h'
    ],
    'rules': [
        'func1',
        'SLList_init',
        'SLList_insert',
        'SLList_search',
        'SLList_destroy'
    ],
    'file-name': 'trace.log',
    'init-storage-size': 20000,
    'sampling': [
        {'func': 'SLList_insert', 'sample': 2},
        {'func': 'func1', 'sample': 1}
    ]
}

collector = before.before(config)
code = collect.collect(collector)
print(code)

