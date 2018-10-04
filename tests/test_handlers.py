import datetime
import json

import peewee
import pytest
from playhouse.shortcuts import model_to_dict
from tornado.httpclient import HTTPError

from tcrudge.decorators import perm_roles
from tcrudge.handlers import ApiListHandler, ApiItemHandler
from tcrudge.models import BaseModel
from tcrudge.utils.json import json_serial
from tests.conftest import db

TEST_DATA = [
    {
        'tf_text': 'Test field 1',
        'tf_integer': 10,
        'tf_datetime': datetime.datetime(2016, 5, 5, 11),
        'tf_boolean': True,
    },
    {
        'tf_text': 'Test field 2',
        'tf_integer': 20,
        'tf_datetime': datetime.datetime(2016, 1, 10, 12),
        'tf_boolean': True,
    },
    {
        'tf_text': 'Test field 3',
        'tf_integer': -10,
        'tf_datetime': datetime.datetime(2016, 9, 15, 12),
        'tf_boolean': False,
    },
]

TEST_INVALID_DATA = [
    {
        'tf_text': 'Test field 4',
        'tf_integer': -10,
        'tf_datetime': '',
        'tf_boolean': False,
    },
]


class ApiTestModel(BaseModel):
    tf_text = peewee.TextField()
    tf_integer = peewee.IntegerField(null=True)
    tf_datetime = peewee.DateTimeField(default=datetime.datetime.now)
    tf_boolean = peewee.BooleanField()
    tf_decimal = peewee.FloatField(null=True)

    class Meta:
        database = db
        excluded = ['tf_boolean']

    async def _delete(self, app):
        await app.objects.delete(self)


class ApiTestModelFK(BaseModel):
    tf_foreign_key = peewee.ForeignKeyField(ApiTestModel, backref='rel_items')

    class Meta:
        database = db


class ApiListTestHandler(ApiListHandler):
    model_cls = ApiTestModel

    @property
    def post_schema_input(self):
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ['tf_text', 'tf_datetime', 'tf_boolean'],
            "properties": {
                'tf_text': {"type": "string"},
                'tf_integer': {"type": "integer"},
                'tf_datetime': {"type": "string", "format": "datetime"},
                'tf_boolean': {"type": "boolean"}
            }
        }


class ApiListTestHandlerPrefetch(ApiListHandler):
    model_cls = ApiTestModel

    async def serialize(self, m):
        result = await super(ApiListTestHandlerPrefetch, self).serialize(m)
        result['rel_items'] = []
        for prefetched_item in m.rel_items:
            result['rel_items'].append(model_to_dict(prefetched_item, recurse=False))
        return result

    def get_queryset(self, paginate=True):
        # Set prefetch queries
        self.prefetch_queries.append(
            ApiTestModelFK.select()
        )
        return super(ApiListTestHandlerPrefetch, self).get_queryset(paginate)


class ApiItemTestHandler(ApiItemHandler):
    model_cls = ApiTestModel


class ApiListTestFKHandler(ApiListHandler):
    model_cls = ApiTestModelFK


class ApiListTestFKHandlerCustomSchema(ApiListHandler):
    model_cls = ApiTestModelFK

    post_schema_input = {
        'properties': {
            'tf_foreign_key': {'anyOf': [{'type': 'integer'},
                                         {'pattern': '^[+-]?[0-9]+$', 'type': 'string'}]
                              }
        },
        'required': ['tf_foreign_key'],
        'additionalProperties': False, 'type': 'object'
        }

class ApiListTestHandlerOverriddenOrderby(ApiListHandler):
    model_cls = ApiTestModel

    def qs_order_by(cls, qs, value, process_value=True):  # checking that we go to the overridden method
        qs = qs.where(1 != 1)  # if no data - ok
        return qs


class ApiItemTestFKHandler(ApiItemHandler):
    model_cls = ApiTestModelFK


class DecTestHandler(ApiListHandler):
    model_cls = ApiTestModel

    @perm_roles(['admin'])
    async def get(self):
        await super().get()


@pytest.fixture(scope='session')
def app_base_handlers(request, app, async_db):
    """
    Fixture modifies application handlers adding base API handlers and creates table for test models
    """
    app.add_handlers(".*$", [(r'^/test/api_test_model/?$', ApiListTestHandler)])
    app.add_handlers(".*$", [(r'^/test/api_test_model/([^/]+)/?$', ApiItemTestHandler)])
    app.add_handlers(".*$", [(r'^/test/api_test_model_fk/?$', ApiListTestFKHandler)])
    app.add_handlers(".*$", [(r'^/test/api_test_model_fk_custom_schema/?$', ApiListTestFKHandlerCustomSchema)])
    app.add_handlers(".*$", [(r'^/test/api_test_model_fk/([^/]+)/?$', ApiItemTestFKHandler)])
    app.add_handlers(".*$", [(r'^/test/api_test_model_prefetch/?$', ApiListTestHandlerPrefetch)])
    app.add_handlers(".*$", [(r'^/test/api_test_model_dec/?$', DecTestHandler)])
    app.add_handlers(".*$", [(r'^/test/api_test_model_overridden_orderby/?$', ApiListTestHandlerOverriddenOrderby)])

    with async_db.allow_sync():
        ApiTestModel.create_table()
        ApiTestModelFK.create_table()

    def teardown():
        with async_db.allow_sync():
            ApiTestModelFK.drop_table()
            ApiTestModel.drop_table()

    request.addfinalizer(teardown)

    return app


@pytest.fixture
def test_data(async_db):
    """
    Helper fixture to create test data
    """
    res = []
    with async_db.allow_sync():
        for data in TEST_DATA:
            res.append(ApiTestModel.create(**data))
    return res


def test_generate_schema():
    """
    Helper fixture to create test data
    """
    schema = ApiTestModel.to_schema()
    assert {
               'properties': {
                   'tf_datetime': {'type': 'string'},
                   'tf_decimal': {'anyOf': [{'type': 'number'},
                                            {'pattern': '^[+-]?([0-9]*[.])?[0-9]+$', 'type': 'string'},
                                            {'type': 'null'}]},
                   'tf_integer': {'anyOf': [{'type': 'integer'}, {'pattern': '^[+-]?[0-9]+$', 'type': 'string'},
                                            {'type': 'null'}]},
                   'id': {'anyOf': [{'type': 'integer'}, {'pattern': '^[+-]?[0-9]+$', 'type': 'string'}]},
                   'tf_text': {'type': 'string'}}, 'required': ['id', 'tf_datetime', 'tf_text'],
               'additionalProperties': False, 'type': 'object'
           } == schema

    schema1 = ApiTestModel.to_schema(excluded=['id'])
    assert {
               'properties': {
                   'tf_datetime': {'type': 'string'},
                   'tf_decimal': {'anyOf': [{'type': 'number'},
                                            {'pattern': '^[+-]?([0-9]*[.])?[0-9]+$', 'type': 'string'},
                                            {'type': 'null'}]},
                   'tf_integer': {'anyOf': [{'type': 'integer'}, {'pattern': '^[+-]?[0-9]+$', 'type': 'string'},
                                            {'type': 'null'}]},
                   'tf_text': {'type': 'string'}}, 'required': ['tf_datetime', 'tf_text'],
               'additionalProperties': False, 'type': 'object'
           } == schema1

    schema2 = ApiTestModelFK.to_schema(excluded=['id'])
    assert {
        'properties': {
            'tf_foreign_key': {'anyOf': [{'type': 'integer'},
                                         {'pattern': '^[+-]?[0-9]+$', 'type': 'string'}]
                              }
        },
        'required': ['tf_foreign_key'],
        'additionalProperties': False, 'type': 'object'
        } == schema2


@pytest.mark.gen_test
async def test_perm_roles_decorator(http_client, base_url, app_base_handlers, monkeypatch):
    with pytest.raises(HTTPError) as e:
        await http_client.fetch(base_url + '/test/api_test_model_dec/', method='GET')

    async def success_get_roles(self):
        return ['admin']

    monkeypatch.setattr(DecTestHandler, 'get_roles', success_get_roles)
    res = await http_client.fetch(base_url + '/test/api_test_model_dec/', method='GET')
    assert res.code == 200

    async def error_is_auth(self):
        return False

    monkeypatch.setattr(DecTestHandler, 'is_auth', error_is_auth)

    with pytest.raises(HTTPError) as e:
        await http_client.fetch(base_url + '/test/api_test_model_dec/', method='GET')


@pytest.mark.gen_test
@pytest.mark.usefixtures('app_base_handlers', 'test_data', 'clean_table')
@pytest.mark.parametrize('clean_table', [(ApiTestModel,)], indirect=True)
async def test_base_api_list_head(http_client, base_url):
    # Fetch data
    res = await http_client.fetch(base_url + '/test/api_test_model', method='HEAD')

    assert res.code == 200
    assert 'X-Total' in res.headers
    assert int(res.headers['X-Total']) == len(TEST_DATA)


@pytest.mark.gen_test
@pytest.mark.usefixtures('app_base_handlers', 'test_data', 'clean_table')
@pytest.mark.parametrize('clean_table', [(ApiTestModel,)], indirect=True)
@pytest.mark.parametrize(['url_param', 'cnt'], [('tf_integer__gt=0', 2),
                                                ('tf_datetime__gte=2016-9-15', 1),
                                                ('tf_datetime__gt=2016-9-15%2023:59:59', 0),
                                                ('tf_integer__gte=10', 2),
                                                ('tf_text__ne=Test%20field%201', 2),
                                                ('tf_integer__lt=-10', 0),
                                                ('tf_integer__lte=-10', 1),
                                                ('tf_integer__in=1,2,-10', 1),
                                                ('-tf_text__isnull=', 3),
                                                ('tf_text__isnull', 0),
                                                ('tf_text__like=test%25', 0),
                                                ('tf_text__ilike=test%25', 3),
                                                ('limit=1', 1),
                                                ('limit=2&offset=1', 2),
                                                ('order_by=tf_integer', 3),
                                                ('order_by=tf_text,-tf_integer,', 3),
                                                ('tf_boolean=0', 1),
                                                ])
async def test_base_api_list_filter(http_client, base_url, url_param, cnt, monkeypatch):
    monkeypatch.setattr(ApiListTestHandler, 'get_schema_input', {})
    res = await http_client.fetch(base_url + '/test/api_test_model/?%s' % url_param)

    assert res.code == 200
    data = json.loads(res.body.decode())
    assert data['success']
    assert data['errors'] == []
    assert len(data['result']['items']) == cnt


@pytest.mark.gen_test
@pytest.mark.usefixtures('clean_table')
@pytest.mark.parametrize('clean_table', [(ApiTestModelFK, ApiTestModel)], indirect=True)
@pytest.mark.parametrize('total', ['0', '1'])
async def test_base_api_list_prefetch(http_client, base_url, test_data, app_base_handlers, total):
    # Create test FK models
    for i in range(5):
        await app_base_handlers.objects.create(ApiTestModelFK, tf_foreign_key=test_data[0])

    res = await http_client.fetch(base_url + '/test/api_test_model_prefetch/?total=%s' % total)

    assert res.code == 200
    data = json.loads(res.body.decode())
    assert data['success']
    assert data['errors'] == []
    # Check prefetch
    assert len(data['result']['items'][0]['rel_items']) == 5


@pytest.mark.gen_test
@pytest.mark.usefixtures('app_base_handlers', 'test_data', 'clean_table')
@pytest.mark.parametrize('clean_table', [(ApiTestModel,)], indirect=True)
async def test_base_api_list_filter_default(http_client, base_url, monkeypatch):
    monkeypatch.setattr(ApiListTestHandler, 'default_filter', {'tf_integer__gt': 0})
    monkeypatch.setattr(ApiListTestHandler, 'default_order_by', ('tf_text',))
    res = await http_client.fetch(base_url + '/test/api_test_model/')

    assert res.code == 200
    data = json.loads(res.body.decode())
    assert data['success']
    assert data['errors'] == []
    assert len(data['result']['items']) == 2


@pytest.mark.gen_test
@pytest.mark.usefixtures('app_base_handlers', 'test_data', 'clean_table')
@pytest.mark.parametrize('clean_table', [(ApiTestModel,)], indirect=True)
async def test_base_api_list_force_total_header(http_client, base_url):
    res = await http_client.fetch(base_url + '/test/api_test_model/', headers={'X-Total': ''})

    assert res.code == 200
    data = json.loads(res.body.decode())
    assert data['errors'] == []
    assert data['success']
    assert data['pagination']['total'] == len(data['result']['items']) == len(TEST_DATA)


@pytest.mark.gen_test
@pytest.mark.usefixtures('app_base_handlers', 'test_data', 'clean_table')
@pytest.mark.parametrize('clean_table', [(ApiTestModel,)], indirect=True)
async def test_base_api_list_force_total_query(http_client, base_url):
    res = await http_client.fetch(base_url + '/test/api_test_model/?total=1')

    assert res.code == 200
    data = json.loads(res.body.decode())
    assert data['errors'] == []
    assert data['success']
    assert data['pagination']['total'] == len(data['result']['items']) == len(TEST_DATA)


@pytest.mark.gen_test
@pytest.mark.usefixtures('app_base_handlers')
@pytest.mark.parametrize('url_param', [('tf_bad_field=Some_data',),
                                       ('tf_integer=ABC',),
                                       ])
async def test_base_api_list_filter_bad_request(http_client, base_url, url_param):
    with pytest.raises(HTTPError) as e:
        await http_client.fetch(base_url + '/test/api_test_model/?%s' % url_param)
    assert e.value.code == 400
    data = json.loads(e.value.response.body.decode())
    assert data['result'] is None
    assert not data['success']
    assert len(data['errors']) == 1
    assert data['errors'][0]['message'] == 'Validation failed'


@pytest.mark.gen_test
@pytest.mark.usefixtures('app_base_handlers')
@pytest.mark.parametrize('url_param', [
    ('order_by=some_bad_field',),
])
async def test_base_api_list_filter_bad_request1(http_client, base_url, url_param):
    with pytest.raises(HTTPError) as e:
        await http_client.fetch(base_url + '/test/api_test_model/?%s' % url_param)
    assert e.value.code == 400
    data = json.loads(e.value.response.body.decode())
    assert data['result'] is None
    assert not data['success']
    assert len(data['errors']) == 1
    assert data['errors'][0]['message'] == 'Bad query arguments'


@pytest.mark.gen_test
@pytest.mark.usefixtures('app_base_handlers')
@pytest.mark.parametrize('url_param', [
    ('order_by=<some_bad_field>`1`</some_bad_field>',),
])
async def test_base_api_list_filter_bad_request1(http_client, base_url, url_param):
    with pytest.raises(HTTPError) as e:
        await http_client.fetch(base_url + '/test/api_test_model/?%s' % url_param)
    assert e.value.code == 400
    data = json.loads(e.value.response.body.decode())
    assert data['result'] is None
    assert not data['success']
    assert len(data['errors']) == 1
    assert 'lt;' in data['errors'][0]['detail']
    assert 'gt;' in data['errors'][0]['detail']


@pytest.mark.gen_test
@pytest.mark.usefixtures('app_base_handlers', 'clean_table')
@pytest.mark.parametrize('clean_table', [(ApiTestModel,)], indirect=True)
@pytest.mark.parametrize(['body', 'message'], [(b'', 'Request body is not a valid json object'),
                                               (json.dumps({}).encode(), 'Validation failed'),
                                               ])
async def test_base_api_list_bad_request(http_client, base_url, body, message):
    with pytest.raises(HTTPError) as e:
        await http_client.fetch(base_url + '/test/api_test_model/', method='POST', body=body)
    assert e.value.code == 400
    data = json.loads(e.value.response.body.decode())
    assert data['result'] is None
    assert not data['success']
    for error in data['errors']:
        print(error)
        assert error['message'] == message


@pytest.mark.gen_test
@pytest.mark.usefixtures('app_base_handlers', 'clean_table')
@pytest.mark.parametrize('clean_table', [(ApiTestModelFK,)], indirect=True)
async def test_base_api_list_bad_fk(http_client, base_url):
    # Create model with invalid FK
    data = {
        'tf_foreign_key': 1
    }
    with pytest.raises(HTTPError) as e:
        await http_client.fetch(base_url + '/test/api_test_model_fk/', method='POST', body=json.dumps(data).encode())
    assert e.value.code == 400
    data = json.loads(e.value.response.body.decode())
    assert data['result'] is None
    assert not data['success']
    assert len(data['errors']) == 1
    assert data['errors'][0]['message'] == 'Invalid parameters'


@pytest.mark.gen_test
@pytest.mark.usefixtures('app_base_handlers', 'clean_table')
@pytest.mark.parametrize('clean_table', [(ApiTestModelFK,)], indirect=True)
async def test_base_api_list_bad_fk_invalid_integer(http_client, base_url):
    # Create model with invalid FK
    data = {
        'tf_foreign_key': ''
    }
    with pytest.raises(HTTPError) as e:
        await http_client.fetch(base_url + '/test/api_test_model_fk/', method='POST', body=json.dumps(data).encode())
    assert e.value.code == 400
    data = json.loads(e.value.response.body.decode())
    assert data['result'] is None
    assert not data['success']
    assert len(data['errors']) == 1
    assert data['errors'][0]['message'] == 'Validation failed'


@pytest.mark.gen_test
@pytest.mark.usefixtures('app_base_handlers', 'clean_table')
@pytest.mark.parametrize('clean_table', [(ApiTestModelFK,)], indirect=True)
async def test_base_api_list_bad_fk_invalid_integer_custom_schema(http_client, base_url):
    # Create model with invalid FK
    data = {
        'tf_foreign_key': ''
    }
    with pytest.raises(HTTPError) as e:
        await http_client.fetch(base_url + '/test/api_test_model_fk_custom_schema/', method='POST', body=json.dumps(data).encode())
    assert e.value.code == 400
    data = json.loads(e.value.response.body.decode())
    assert data['result'] is None
    assert not data['success']
    assert len(data['errors']) == 1
    assert data['errors'][0]['message'] == 'Validation failed'


@pytest.mark.gen_test
@pytest.mark.usefixtures('clean_table')
@pytest.mark.parametrize('clean_table', [(ApiTestModel,)], indirect=True)
async def test_base_api_list_post(http_client, base_url, app_base_handlers):
    data = TEST_INVALID_DATA[0]
    resp = await http_client.fetch(base_url + '/test/api_test_model/', method='POST',
                                   body=json.dumps(data, default=json_serial).encode())
    assert resp.code == 400
    data = json.loads(e.value.response.body.decode())
    assert data['result'] is None
    assert not data['success']
    assert len(data['errors']) == 1
    assert data['errors'][0]['message'] == 'Invalid parameters'

@pytest.mark.gen_test
@pytest.mark.usefixtures('clean_table')
@pytest.mark.parametrize('clean_table', [(ApiTestModel,)], indirect=True)
async def test_base_api_list_post(http_client, base_url, app_base_handlers):
    data = TEST_DATA[0]
    resp = await http_client.fetch(base_url + '/test/api_test_model/', method='POST',
                                   body=json.dumps(data, default=json_serial).encode())
    assert resp.code == 200
    data = json.loads(resp.body.decode())
    assert data['errors'] == []
    assert data['success']
    item_id = data['result']['id']
    # Fetch item from database
    await app_base_handlers.objects.get(ApiTestModel, id=item_id)


@pytest.mark.gen_test
@pytest.mark.parametrize('item_id', [('1',), ('ABC',)])
async def test_base_api_item_not_found(http_client, base_url, item_id):
    with pytest.raises(HTTPError) as e:
        await http_client.fetch(base_url + '/test/api_test_model/%s' % item_id)
    assert e.value.code == 404


@pytest.mark.gen_test
@pytest.mark.usefixtures('app_base_handlers', 'clean_table')
@pytest.mark.parametrize('clean_table', [(ApiTestModel,)], indirect=True)
async def test_base_api_item_get(http_client, base_url, test_data):
    resp = await http_client.fetch(base_url + '/test/api_test_model/%s' % test_data[0].id)
    assert resp.code == 200
    data = json.loads(resp.body.decode())
    assert data['success']
    assert data['errors'] == []
    for k, v in TEST_DATA[0].items():
        if isinstance(v, datetime.datetime):
            assert data['result'][k] == v.isoformat()
        else:
            assert data['result'][k] == v


@pytest.mark.gen_test
@pytest.mark.usefixtures('app_base_handlers', 'clean_table')
@pytest.mark.parametrize('clean_table', [(ApiTestModel,)], indirect=True)
async def test_base_api_item_get_msgpack(http_client, base_url, test_data):
    resp = await http_client.fetch(base_url + '/test/api_test_model/%s' % test_data[0].id,
                                   headers={'Accept': 'application/x-msgpack'})
    assert resp.code == 200
    import msgpack
    data = msgpack.loads(resp.body)
    print(data)
    assert data[b'success']
    assert data[b'errors'] == []
    for k, v in TEST_DATA[0].items():
        if isinstance(v, datetime.datetime):
            assert data[b'result'][k.encode()] == v.isoformat().encode()
        elif isinstance(v, (bool, int)):
            assert data[b'result'][k.encode()] == v
        else:
            assert data[b'result'][k.encode()] == v.encode()


@pytest.mark.gen_test
@pytest.mark.usefixtures('clean_table')
@pytest.mark.parametrize('clean_table', [(ApiTestModel,)], indirect=True)
async def test_base_api_list_overridden_orderby(http_client, base_url):
    data = TEST_DATA[0]
    await http_client.fetch(base_url + '/test/api_test_model/', method='POST',
                            body=json.dumps(data, default=json_serial).encode())
    res = await http_client.fetch(base_url + '/test/api_test_model_overridden_orderby/?order_by=ololo')
    assert res.code == 200
    data = json.loads(res.body.decode())
    assert data['result'] == {'items': []}
    assert data['success']


@pytest.mark.gen_test
@pytest.mark.usefixtures('clean_table')
@pytest.mark.parametrize('clean_table', [(ApiTestModel,)], indirect=True)
async def test_base_api_item_put(http_client, base_url, app_base_handlers, test_data, monkeypatch):
    # Update data
    upd_data = {
        'tf_text': 'Data changed',
        'tf_integer': 110,
        'tf_datetime': datetime.datetime(2015, 5, 5, 11),
        'tf_boolean': False
    }
    monkeypatch.setattr(ApiItemHandler, 'put_schema_input', {})
    resp = await http_client.fetch(base_url + '/test/api_test_model/%s' % test_data[0].id, method='PUT',
                                   body=json.dumps(upd_data, default=json_serial).encode())
    assert resp.code == 200
    data = json.loads(resp.body.decode())
    assert data['success']
    assert data['errors'] == []

    # Fetch item from database
    item = await app_base_handlers.objects.get(ApiTestModel, id=test_data[0].id)
    for k, v in upd_data.items():
        assert getattr(item, k) == v


@pytest.mark.gen_test
@pytest.mark.usefixtures('clean_table')
@pytest.mark.parametrize('clean_table', [(ApiTestModelFK, ApiTestModel)], indirect=True)
async def test_base_api_item_put_bad_fk(http_client, base_url, app_base_handlers, test_data):
    # Create new ApiTestModelFK
    item = await app_base_handlers.objects.create(ApiTestModelFK, tf_foreign_key=test_data[0].id)

    # Try to update with invalid FK
    upd_data = {
        'tf_foreign_key': 12345
    }
    with pytest.raises(HTTPError) as e:
        await http_client.fetch(base_url + '/test/api_test_model_fk/%s' % item.id, method='PUT',
                                body=json.dumps(upd_data).encode())
    assert e.value.code == 400


@pytest.mark.gen_test
@pytest.mark.usefixtures('clean_table')
@pytest.mark.parametrize('clean_table', [(ApiTestModel,)], indirect=True)
async def test_base_api_item_delete(http_client, base_url, app_base_handlers, test_data):
    resp = await http_client.fetch(base_url + '/test/api_test_model/%s' % test_data[0].id, method='DELETE')
    assert resp.code == 200
    data = json.loads(resp.body.decode())
    assert data['success']
    assert data['errors'] == []
    assert data['result'] == 'Item deleted'
    # Check that item has been deleted
    with pytest.raises(ApiTestModel.DoesNotExist):
        await app_base_handlers.objects.get(ApiTestModel, id=test_data[0].id)


@pytest.mark.gen_test
@pytest.mark.usefixtures('clean_table', 'app_base_handlers')
@pytest.mark.parametrize('clean_table', [(ApiTestModel,)], indirect=True)
async def test_base_api_item_delete_405(http_client, base_url, test_data, monkeypatch):
    # Removing delete from this CRUD
    monkeypatch.delattr(ApiTestModel, '_delete')

    with pytest.raises(HTTPError) as e:
        await http_client.fetch(base_url + '/test/api_test_model/%s' % test_data[0].id, method='DELETE')
    assert e.value.code == 405


@pytest.mark.gen_test
@pytest.mark.usefixtures('clean_table', 'app_base_handlers')
@pytest.mark.parametrize('clean_table', [(ApiTestModel,)], indirect=True)
async def test_base_api_list_post_405(http_client, base_url, monkeypatch):
    # Removing post from this CRUD
    monkeypatch.delattr(BaseModel, '_create')
    data = TEST_DATA[0]
    with pytest.raises(HTTPError) as e:
        await http_client.fetch(base_url + '/test/api_test_model/', method='POST',
                                body=json.dumps(data, default=json_serial).encode())
    assert e.value.code == 405


@pytest.mark.gen_test
@pytest.mark.usefixtures('clean_table', 'app_base_handlers')
@pytest.mark.parametrize('clean_table', [(ApiTestModel,)], indirect=True)
async def test_base_api_item_put_405(http_client, base_url, test_data, monkeypatch):
    # Remove put from this CRUD
    monkeypatch.delattr(BaseModel, '_update')
    monkeypatch.setattr(ApiItemHandler, 'put_schema_input', {})
    # Update data
    upd_data = {
        'tf_text': 'Data changed',
        'tf_integer': 110,
        'tf_datetime': datetime.datetime(2015, 5, 5, 11),
        'tf_boolean': False
    }
    with pytest.raises(HTTPError) as e:
        await http_client.fetch(base_url + '/test/api_test_model/%s' % test_data[0].id, method='PUT',
                                body=json.dumps(upd_data, default=json_serial).encode())
    assert e.value.code == 405


@pytest.mark.gen_test
@pytest.mark.usefixtures('clean_table', 'app_base_handlers', 'test_data')
@pytest.mark.parametrize('clean_table', [(ApiTestModel,)], indirect=True)
async def test_api_list_validate_get(http_client, base_url, monkeypatch):
    monkeypatch.setattr(ApiListTestHandler, 'get_schema_input',
                        {
                            'type': 'object',
                            'additionalProperties': False,
                            'properties': {}
                        })
    with pytest.raises(HTTPError) as e:
        await http_client.fetch(base_url + '/test/api_test_model/?a=1')
    assert e.value.code == 400
    data = json.loads(e.value.response.body.decode())
    assert not data['success']
    assert len(data['errors']) == 1
    assert data['errors'][0]['message'] == 'Validation failed'
