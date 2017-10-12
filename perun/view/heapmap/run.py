"""Heap map visualization of the profiles."""

from copy import deepcopy

import click

import perun.profile.convert as heap_representation
import perun.view.heapmap.heap_map as hm
from perun.utils.helpers import pass_profile

__author__ = 'Radim Podola'


def _call_heap(profile):
    """ Call interactive heap map visualization

    Arguments:
        profile(dict): memory profile with records
    """
    heap_map = heap_representation.to_heap_map_format(deepcopy(profile))
    heat_map = heap_representation.to_heat_map_format(profile)
    hm.heap_map(heap_map, heat_map)


@click.command()
@pass_profile
def heapmap(profile, **_):
    """Heap map visualization of the profile."""
    _call_heap(profile)
