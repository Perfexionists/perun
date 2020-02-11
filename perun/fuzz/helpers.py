"""Collection of helper functions used in fuzzing"""

__author__ = 'Tomas Fiedor'


def insert_at_split(lines, index, split_position, inserted_bytes):
    """

    :param list lines:
    :param int index:
    :param int split_position:
    :param bytes inserted_bytes:
    :return:
    """
    lines[index] = lines[index][:split_position] + inserted_bytes + lines[index][split_position:]


def remove_at_split(lines, index, split_position):
    """

    :param list lines:
    :param int index:
    :param int split_position:
    :return:
    """
    lines[index] = lines[index][:split_position] + lines[index][split_position+1:]


def replace_at_split(lines, index, split_position, replaced_bytes):
    """
    :param list lines:
    :param int index:
    :param int split_position:
    :param bytes replaced_bytes:
    :return:
    """
    lines[index] = lines[index][:split_position] + replaced_bytes + lines[index][split_position+1:]
