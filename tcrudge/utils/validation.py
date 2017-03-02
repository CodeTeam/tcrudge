"""
Module for common validation tools.
"""


def validate_integer(val, min_value=None, max_value=None, default=None):
    """
    Validates the input val parameter.

    If it is can not be converted to integer, returns default_value.

    If it is less than min_value, returns min_value.

    If it is greater than max_value, returns max_value.

    :param val: number to validate
    :type val: int, float, digital string

    :param min_value: min value of validation range
    :type min_value: int

    :param max_value: max value of validation range
    :type max_value: int

    :param default: default value to return in case of exception
    :type default: int

    :return: None, min, max, default or result - int
    :rtype: NoneType, int
    """
    try:
        result = int(val)  # TODO - check for non int in values
    except (TypeError, ValueError):
        return default
    if min_value is not None and result < min_value:
        result = min_value
    if max_value is not None and result > max_value:
        result = max_value
    return result


def prepare(handler):
    """
    Works for GET requests only
 
    Validates the request's GET method to define 
    if there are X-Limit and X-Offset headers to 
    extract them and concat with handler directly
    """
    # Headers are more significant when taking limit and offset
    if handler.request.method == 'GET':
        # No more than MAX_LIMIT records at once
        # Not less than 1 record at once
        limit = handler.request.headers.get('X-Limit',
                                         handler.get_query_argument('limit',
                                                                    handler.default_limit))
        handler.limit = validate_integer(limit, 1, handler.max_limit,
                                         handler.default_limit)

        # Offset should be a non negative integer
        offset = handler.request.headers.get('X-Offset',
                                          handler.get_query_argument('offset',
                                                                     0))
        handler.offset = validate_integer(offset, 0, None, 0)

        # Force send total amount of items
        handler.total = 'X-Total' in handler.request.headers or \
                     handler.get_query_argument('total', None) == '1'
