"""
Module for common validation tools.
"""


def validate_integer(val, min_value=None, max_value=None, default=None):
    """
    Validates the input val parameter
    If it is can not be converted to integer, returns default_value
    If it is less than min_value, returns min_value
    If it is more than max_value, returns max_value
    """
    try:
        result = int(val)
    except (TypeError, ValueError):
        return default

    if min_value is not None and result < min_value:
        result = min_value

    if max_value is not None and result > max_value:
        result = max_value

    return result
