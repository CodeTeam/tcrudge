import datetime
import json
import uuid

import pytest

from tcrudge.utils.json import json_serial
from tcrudge.utils.validation import validate_integer


@pytest.mark.parametrize(['val', 'min_value', 'max_value', 'default', 'res'],
                         [(None, None, None, 5, 5),
                          ('Not integer', None, None, 0, 0),
                          ('-10', 4, None, None, 4),
                          (5, None, 1, None, 1)])
def test_validate_integer(val, min_value, max_value, default, res):
    assert validate_integer(val, min_value, max_value, default) == res


def test_serial():
    t = {'datetime': datetime.datetime(2016, 6, 1, 10, 33, 6),
         'date': datetime.date(2016, 8, 3),
         'uuid': uuid.uuid4()}
    json.dumps(t, default=json_serial)

    class A:
        pass

    t = {'unknown_type': A()}

    with pytest.raises(TypeError):
        json.dumps(t, default=json_serial)
