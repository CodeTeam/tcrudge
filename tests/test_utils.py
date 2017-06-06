import datetime
import json
import uuid

import pytest

from tcrudge.utils.json import json_serial
from tcrudge.utils.validation import validate_integer
from tcrudge.utils.xhtml_escape import xhtml_escape_complex_object


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


@pytest.mark.parametrize(
    ('initial_val', 'valid_value'),
    (
        ('&<>"\'', '&amp;&lt;&gt;&quot;&#39;'),
        (('&', '<', '>', '"', '\''), ('&amp;', '&lt;', '&gt;', '&quot;', '&#39;')),
        (['&', '<', '>', '"', '\''], ('&amp;', '&lt;', '&gt;', '&quot;', '&#39;')),
        (
            {'1': '&', '2': '<', '3': '>', '4': '"', '5': '\''},
            {'1': '&amp;', '2': '&lt;', '3': '&gt;', '4': '&quot;', '5': '&#39;'},
        ),
        (
            {
                '1': '&',
                '2': {'1': ('&', ), '2': ['&', '<'], '3': {'3': '\''}},
            },
            {
                '1': '&amp;',
                '2': {'1': ('&amp;', ), '2': ('&amp;', '&lt;'), '3': {'3': '&#39;'}},
            }
        )
    )
)
def test_xhtml_escape_complex_object(initial_val, valid_value):
    result = xhtml_escape_complex_object(initial_val)
    assert result == valid_value


def test_xhtml_escape_complex_object_error():
    with pytest.raises(TypeError):
        xhtml_escape_complex_object(None)

