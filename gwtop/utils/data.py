#!/usr/bin/env python
__author__ = 'paul'

def bytes2human(in_bytes, target_unit=None):
    """
    Convert a given number of bytes into a more consumable form
    :param in_bytes: bytes to convert (int)
    :param target_unit: target representation MB, GB, TB etc
    :return: string of the converted value with a suffix e.g. 5G
    """

    suffixes = ['K', 'M', 'G', 'T', 'P']

    rounding = {'K': 0, 'M': 0, 'G': 0, 'T': 1, 'P': 2}

    size = float(in_bytes)

    if size < 0:
        raise ValueError('number must be non-negative')

    divisor = 1024

    for suffix in suffixes:
        size /= divisor
        if size < divisor or suffix == target_unit:
            char1 = suffix[0]
            precision = rounding[char1]
            size = round(size, precision)
            fmt_string = '{0:.%df}{1}' % rounding[char1]

            return fmt_string.format(size, suffix)

    raise ValueError('number too large')
