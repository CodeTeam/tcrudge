import datetime
import uuid


def json_serial(obj):
    """
    JSON serializer for objects not serializable by default json code.

    :param obj: object to serialize
    :type obj: date, datetime or UUID

    :return: formatted and serialized object
    :rtype: str
    """
    if isinstance(obj, datetime.datetime) or isinstance(obj, datetime.date):
        # Datetime serializer
        return obj.isoformat()
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    raise TypeError("Type %s not serializable" % type(obj))
