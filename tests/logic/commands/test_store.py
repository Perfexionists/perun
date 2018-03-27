import os
import pytest

import perun.logic.store as store
import perun.utils.helpers as helpers
import perun.utils.exceptions as exceptions

__author__ = 'Tomas Fiedor'


@pytest.mark.usefixtures('cleandir')
def test_malformed_indexes(tmpdir, monkeypatch):
    """Tests malformed indexes"""
    index_file = os.path.join(str(tmpdir), "index")
    store.touch_index(index_file)

    monkeypatch.setattr('perun.utils.helpers.INDEX_VERSION', helpers.INDEX_VERSION + 1)
    with open(index_file, 'rb') as index_handle:
        with pytest.raises(exceptions.MalformedIndexFileException):
            store.print_index_from_handle(index_handle)

    index_file = os.path.join(str(tmpdir), "index2")
    store.touch_index(index_file)
    monkeypatch.setattr('perun.utils.helpers.INDEX_MAGIC_PREFIX', helpers.INDEX_MAGIC_PREFIX.upper())
    with open(index_file, 'rb') as index_handle:
        with pytest.raises(exceptions.MalformedIndexFileException):
            store.print_index_from_handle(index_handle)


@pytest.mark.usefixtures('cleandir')
def test_correct_index(tmpdir):
    """Test correct working with index"""
    index_file = os.path.join(str(tmpdir), "index")
    store.touch_index(index_file)
    store.print_index(index_file)
