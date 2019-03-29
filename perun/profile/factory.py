"""Profile factory optimizes the previous profile format

In particular, in the new format we propose to merge some regions into
so called resource types, which are dictionaries of persistent less
frequently changed aspects of resources. Moreover, we optimize other
regions and flatten the format.
"""

import collections

__author__ = 'Tomas Fiedor'

class Profile(collections.MutableMapping):
    """
    :ivar dict _storage: internal storage of the profile
    """
    def __init__(self, *args, **kwargs):
        """Initializes the internal storage

        :param list args: positional arguments for dictionary
        :param kwargs kwargs: keyword arguments for dictionary
        """
        super().__init__()
        self._storage = dict(*args, **kwargs)

    def __getitem__(self, item):
        """Returns the item stored in profile

        This does a translation from the internal storage, which keeps some
        regions as chunks either in resource or config map.

        :param str item: key of the item we are getting
        :return: item stored in the profile
        """
        return self._storage[item]

    def __setitem__(self, key, value):
        """Sets the value into the storage under the key.

        Internally this finds a similar regions and registers them in either
        resource or config map.

        :param str key: key of the value
        :param object value:  object we are setting in the profile
        :return:
        """
        self._storage[key] = value

    def __delitem__(self, key):
        """Deletes the item in the storage

        :param str key: key to be deleted
        """
        del self._storage[key]

    def __iter__(self):
        """Iterates through all of the stuff in storage.

        :return: storage iterator
        """
        return self._storage.__iter__()

    def __len__(self):
        """Returns the size of the internal storage

        :return: size of the internal storage
        """
        return len(self._storage)

    def serialize(self):
        """Returns serializable representation of the profile

        :return: serializable representation (i.e. the actual storage)
        """
        return self._storage
