"""Basic testing for generation of bars"""
import os
import pytest

import perun.view.bargraph.run as bargraphs

__author__ = 'Tomas Fiedor'


@pytest.mark.usefixtures('cleandir')
def test_bokeh_bars(memory_profiles):
    """Test creating bokeh bars

    Expecting no error.
    """
    for memory_profile in memory_profiles:
        bargraphs._create_bar_graphs(memory_profile, 'bars.html', 800)
        assert 'bars.html' in os.listdir(os.getcwd())

