""" The core of the regression analyzer. """

import linear
import visualizer
import data_provider


# pts = [(132, 46), (129, 48), (120, 51), (113.2, 52.1), (105, 54), (92, 52), (84, 59), (83.2, 58.7), (88.4, 61.6),
#        (59, 64), (80, 61.4), (81.5, 54.6), (71, 58.8), (69.2, 58)]
# pts = [(2, 5), (1, 6), (3, 7), (4, 10)]

# The testing profile data dictionary
res = [
    {'amount': 74, 'subtype': 'time delta', 'structure-unit-size': 0,
     'uid': 'SLList_init(SLList*)', 'type': 'mixed'},
    {'amount': 21, 'subtype': 'time delta', 'structure-unit-size': 0,
     'uid': 'SLList_insert(SLList*, int)', 'type': 'mixed'},
    {'amount': 13, 'subtype': 'time delta', 'structure-unit-size': 1,
     'uid': 'SLList_insert(SLList*, int)', 'type': 'mixed'},
    {'amount': 13, 'subtype': 'time delta', 'structure-unit-size': 2,
     'uid': 'SLList_insert(SLList*, int)', 'type': 'mixed'},
    {'amount': 13, 'subtype': 'time delta', 'structure-unit-size': 3,
     'uid': 'SLList_insert(SLList*, int)', 'type': 'mixed'},
    {'amount': 13, 'subtype': 'time delta', 'structure-unit-size': 4,
     'uid': 'SLList_insert(SLList*, int)', 'type': 'mixed'},
    {'amount': 13, 'subtype': 'time delta', 'structure-unit-size': 5,
     'uid': 'SLList_insert(SLList*, int)', 'type': 'mixed'},
    {'amount': 13, 'subtype': 'time delta', 'structure-unit-size': 6,
     'uid': 'SLList_insert(SLList*, int)', 'type': 'mixed'},
    {'amount': 14, 'subtype': 'time delta', 'structure-unit-size': 7,
     'uid': 'SLList_insert(SLList*, int)', 'type': 'mixed'},
    {'amount': 13, 'subtype': 'time delta', 'structure-unit-size': 8,
     'uid': 'SLList_insert(SLList*, int)', 'type': 'mixed'},
    {'amount': 13, 'subtype': 'time delta', 'structure-unit-size': 9,
     'uid': 'SLList_insert(SLList*, int)', 'type': 'mixed'},
    {'amount': 12, 'subtype': 'time delta', 'structure-unit-size': 10,
     'uid': 'SLList_search(SLList*, int)', 'type': 'mixed'},
    {'amount': 15, 'subtype': 'time delta', 'structure-unit-size': 10,
     'uid': 'SLList_destroy(SLList*)', 'type': 'mixed'},
    {'amount': 27, 'subtype': 'time delta', 'structure-unit-size': 0,
     'uid': 'SLListcls::SLListcls()', 'type': 'mixed'},
    {'amount': 13, 'subtype': 'time delta', 'structure-unit-size': 0,
     'uid': 'SLListcls::Insert(int)', 'type': 'mixed'},
    {'amount': 13, 'subtype': 'time delta', 'structure-unit-size': 1,
     'uid': 'SLListcls::Insert(int)', 'type': 'mixed'},
    {'amount': 13, 'subtype': 'time delta', 'structure-unit-size': 2,
     'uid': 'SLListcls::Insert(int)', 'type': 'mixed'},
    {'amount': 13, 'subtype': 'time delta', 'structure-unit-size': 3,
     'uid': 'SLListcls::Insert(int)', 'type': 'mixed'},
    {'amount': 13, 'subtype': 'time delta', 'structure-unit-size': 4,
     'uid': 'SLListcls::Insert(int)', 'type': 'mixed'},
    {'amount': 13, 'subtype': 'time delta', 'structure-unit-size': 5,
     'uid': 'SLListcls::Insert(int)', 'type': 'mixed'},
    {'amount': 14, 'subtype': 'time delta', 'structure-unit-size': 6,
     'uid': 'SLListcls::Insert(int)', 'type': 'mixed'},
    {'amount': 14, 'subtype': 'time delta', 'structure-unit-size': 7,
     'uid': 'SLListcls::Insert(int)', 'type': 'mixed'},
    {'amount': 13, 'subtype': 'time delta', 'structure-unit-size': 8,
     'uid': 'SLListcls::Insert(int)', 'type': 'mixed'},
    {'amount': 13, 'subtype': 'time delta', 'structure-unit-size': 9,
     'uid': 'SLListcls::Insert(int)', 'type': 'mixed'},
    {'amount': 14, 'subtype': 'time delta', 'structure-unit-size': 10,
     'uid': 'SLListcls::Search(int)', 'type': 'mixed'}
]

# Parse the dictionary data
points_generator = data_provider.profile_dictionary_provider(res)
for name, points in points_generator:
    # Fit and visualize the function data
    regression = linear.fit_lines(points)
    if regression is not None:
        visualizer.visualize_regression(regression, 'Function: {0}'.format(name), True, 'p')
