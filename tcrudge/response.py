import json

import msgpack

from tcrudge.utils.json import json_serial


def response_json(handler, answer):
    # Default JSON answer
    handler.set_header('Content-Type', 'application/json')
    return json.dumps(answer, default=json_serial)


def response_msgpack(handler, answer):
    # Optional MSGPACK answer
    handler.set_header('Content-Type', 'application/x-msgpack')
    return msgpack.packb(answer)
