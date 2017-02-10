"""
Functions to handle different response formats must receive two arguments:
    * handler: subclass of tornado.web.RequestHandler;
    * answer: dictionary with response data.

And it should return bytes.
"""

import json

import msgpack

from tcrudge.utils.json import json_serial


def response_json(handler, response):
    """
    Default JSON response.

    Sets JSON content type to given handler.

    Serializes result with JSON serializer and sends JSON as response body.

    :return: Bytes of JSONised response
    :rtype: bytes
    """

    handler.set_header('Content-Type', 'application/json')
    return json.dumps(response, default=json_serial)


def response_msgpack(handler, response):
    """
    Optional MSGPACK response.

    Sets MSGPACK content type to given handler.

    Packs response with MSGPACK.

    :return: Bytes of MSGPACK packed response
    :rtype: bytes
    """
    handler.set_header('Content-Type', 'application/x-msgpack')
    return msgpack.packb(response, default=json_serial)
