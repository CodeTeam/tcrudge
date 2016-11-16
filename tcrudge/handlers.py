"""
Module contains basic handlers.
"""

import json
import operator
import traceback
from abc import ABCMeta, abstractmethod

import peewee
from jsonschema import validate, exceptions
from playhouse.shortcuts import model_to_dict
from tornado import web
from tornado.gen import multi

from tcrudge.models import FILTER_MAP
from tcrudge.response import response_json, response_msgpack
from tcrudge.utils.validation import validate_integer


class BaseHandler(web.RequestHandler):
    """
    Base helper class. Provides basic handy reponses.

    To be used for customized handlers that don't fit REST API recommendations.

    Functions to handle different response formats must receive two arguments:
    - handler: subclass of tornado.web.RequestHandler;
    - answer: dictionary with response data.
    """

    response_callbacks = {
        'application/json': response_json,
        'application/x-msgpack': response_msgpack,
    }

    def get_response(self, result=None, errors=None, **kwargs):
        """
        Method returns conventional formatted byte answer
        """
        _errors = errors or []
        # Set success flag
        success = not _errors

        answer = {
            'result': result,
            'errors': _errors,
            'success': success,
        }

        accept = self.request.headers.get('Accept', 'application/json')
        # Get callback
        callback = self.response_callbacks.get(accept, response_json)
        return callback(self, {**answer, **kwargs})

    def response(self, result=None, errors=None, **kwargs):
        """
        Method writes the response and finishes the request.
        """
        self.write(self.get_response(result, errors, **kwargs))
        self.finish()

    def write_error(self, status_code, **kwargs):
        """
        Method gets traceback, writes it into response, finishes response.
        """
        if self.settings.get("serve_traceback") and "exc_info" in kwargs:  # pragma: no cover
            # in debug mode, try to send a traceback
            self.set_header('Content-Type', 'text/plain')
            for line in traceback.format_exception(*kwargs["exc_info"]):
                self.write(line)
            self.finish()
        else:
            self.finish(self._reason)

    def validate(self, data, schema):
        """
        Method to validate parameters
        Raises HTTPError(400) with error info for invalid data
        :param data: bytes or dict
        :param schema: dict, valid json schema
          (http://json-schema.org/latest/json-schema-validation.html)
        :return: None if data is not valid. Else dict(data)
        """
        try:
            # Get and parse arguments
            if isinstance(data, dict):
                _data = data  # pragma: no cover
            else:
                _data = json.loads(data.decode())
            validate(_data, schema)
        except ValueError:
            # json.loads error
            raise web.HTTPError(400, reason=self.get_response(
                errors=[{'code': '', 'message': 'Request body is not a valid json object'}]))
        except exceptions.ValidationError as exc:
            # data does not pass validation
            raise web.HTTPError(400, reason=self.get_response(
                errors=[{'code': '', 'message': 'Validation failed', 'detail': str(exc)}]))
        return _data

    async def bad_permissions(self):
        """
        Returns answer of access denied.
        """
        raise web.HTTPError(
            401,
            reason=self.get_response(errors=[{'code': '', 'message': 'Access denied'}])
        )

    async def is_auth(self):
        """
        Validate user authorized.
        """
        # await self.bad_permissions()
        return True

    async def get_roles(self):
        """
        Get roles.
        """
        return []


class ApiHandler(BaseHandler, metaclass=ABCMeta):
    """
    Base helper class for API functions.
    model_cls MUST be defined.
    """

    # Fields to be excluded by default from serialization
    exclude_fields = ()

    # Serializer recursion
    recurse = False

    # Serializer max depth
    max_depth = None

    @property
    @abstractmethod
    def model_cls(self):  # pragma: no cover
        """
        Model class must be defined. Otherwise it'll crash a little later even
        if nothing seems to be accessing a model class. If you think you don't
        need a model class, consider the architecture. Maybe it doesn't
        fit REST. In that case use BaseHandler.
        https://github.com/CodeTeam/tcrudge/issues/6
        """
        raise NotImplementedError('Model class must be defined.')

    @property
    def get_schema_output(self):  # pragma: no cover
        """
        Maybe you'd ask: "What's a get-schema?"
        The answer is that we wanted to check input of every request method
        in a homologous way. So we decided to describe any input and output
        using JSON schema.
        """
        return {}

    async def serialize(self, model):
        """
        Method to serialize a model.
        By default all fields are serialized by model_to_dict.
        The model can be any model you'll pass through this method.
        """
        return model_to_dict(model,
                             recurse=self.recurse,
                             exclude=self.exclude_fields,
                             max_depth=self.max_depth)


class ApiListHandler(ApiHandler):
    """
    Base List API Handler.
    Supports C, L from CRUDL.
    """
    # Pagination settings
    # Default amount of items to be listed (if no limit passed by request
    # headers or querystring)
    default_limit = 50
    # Maximum amount of items to be listed (if limit passed by request is
    # greater than this amount - it will be truncated)
    max_limit = 100

    # Arguments that should not be passed to filter
    exclude_filter_args = ['limit', 'offset', 'total']

    def __init__(self, *args, **kwargs):
        super(ApiListHandler, self).__init__(*args, **kwargs)
        # Pagination params
        # Number of items to fetch
        self.limit = None
        # Number of items to skip
        self.offset = None
        # Should total amount of items be included in result?
        self.total = False
        # Prefetch queries
        self.prefetch_queries = []

    @property
    def get_schema_input(self):
        """
        JSON Schema to validate GET Url parameters
        :return: dict
        """
        return {
            "type" : "object",
            "additionalProperties": False,
            "properties" : {
                "total" : {"type": "string"},
                "limit" : {"type": "string"},
                "offset" : {"type": "string"},
                "order_by" : {"type" : "string"},
            },
        }

    @property
    def post_schema_input(self):
        """
        JSON Schema to validate POST request body.
        :return: dict
        """
        return {}

    @property
    def post_schema_output(self):  # pragma: no cover
        return self.model_cls.to_schema(excluded=['id'])

    @property
    def default_filter(self):
        """
        Default queryset WHERE clause. Used for list queries first.
        :return: dict
        """
        return {}

    @property
    def default_order_by(self):
        """
        Default queryset ORDER BY clause. Used for list queries first.
        """
        return ()

    def prepare(self):
        """
        Method to get and validate offset and limit params for GET REST request.
        """
        # Headers are more significant when taking limit and offset
        if self.request.method == 'GET':
            # No more than MAX_LIMIT records at once
            # Not less than 1 record at once
            limit = self.request.headers.get('X-Limit', self.get_query_argument('limit', self.default_limit))
            self.limit = validate_integer(limit, 1, self.max_limit, self.default_limit)

            # Offset should be a non negative integer
            offset = self.request.headers.get('X-Offset', self.get_query_argument('offset', 0))
            self.offset = validate_integer(offset, 0, None, 0)

            # Force send total amount of items
            self.total = 'X-Total' in self.request.headers or self.get_query_argument('total', None) == '1'

    @classmethod
    def __qs_filter(cls, qs, flt, value, process_value=True):
        """
        Set WHERE part of response.
        If required, Django-style filter is available via qs.filter()
        and peewee.DQ - this method provides joins.
        """
        neg = False
        if flt[0] in '-':
            # Register NOT filter clause
            neg = True
            flt = flt[1:]
        fld_name, _, k = flt.rpartition('__')
        if not fld_name:
            # No underscore, simple filter
            fld_name, k = k, ''

        # Get filter
        op = FILTER_MAP.get(k, operator.eq)

        if neg:
            _op = op
            op = lambda f, x: operator.inv(_op(f, x))

        # Get field from model
        # raised AttributeError should be handled on higher level
        fld = getattr(cls.model_cls, fld_name)

        # Additional value processing
        if process_value:
            _v = value.decode()
            if isinstance(fld, peewee.BooleanField) and _v in ('0', 'f'):
                # Assume that '0' and 'f' are FALSE for boolean field
                _v = False
            elif k == 'in':
                # Force set parameter to list
                _v = _v.split(',')
            elif k == 'isnull':
                # ISNULL. Force set parameter to None
                _v = None
        else:
            _v = value

        # Send parameter to ORM
        return qs.where(op(fld, _v))

    @classmethod
    def __qs_order_by(cls, qs, value, process_value=True):
        """
        Set ORDER BY part of response.
        """
        # Empty parameters are skipped
        if process_value:
            _v = (_ for _ in value.decode().split(',') if _)
        else:
            _v = (value,)
        for ordr in _v:
            if ordr[0] == '-':
                # DESC order
                fld = getattr(cls.model_cls, ordr[1:])
                qs = qs.order_by(fld.desc(), extend=True)
            else:
                # ASC order
                fld = getattr(cls.model_cls, ordr)
                qs = qs.order_by(fld, extend=True)
        return qs

    def get_queryset(self, paginate=True):
        """
        Get queryset for model.
        Override this method to change logic.
        """
        # Set limit / offset parameters
        qs = self.model_cls.select()
        if paginate:
            qs = qs.limit(self.limit).offset(self.offset)

        # Set default filter values
        for k, v in self.default_filter.items():
            qs = self.__qs_filter(qs, k, v, process_value=False)

        # Set default order_by values
        for v in self.default_order_by:
            qs = self.__qs_order_by(qs, v, process_value=False)

        for k, v in self.request.arguments.items():
            if k in self.exclude_filter_args:
                # Skipping special arguments (limit, offset etc)
                continue
            elif k == 'order_by':
                # Ordering
                qs = self.__qs_order_by(qs, v[0])
            else:
                # Filtration. All arguments passed with AND condition (WHERE <...> AND <...> etc)
                qs = self.__qs_filter(qs, k, v[0])
        return qs
    
    async def _get_items(self, qs):
        pagination = {'offset': self.offset}
        try:
            if self.total:
                # Execute requests to database in parallel (items + total)
                awaitables = []
                qs_total = self.get_queryset(paginate=False)
                if self.prefetch_queries:
                    # Support of prefetch queries
                    awaitables.append(self.application.objects.prefetch(qs, *self.prefetch_queries))
                else:
                    awaitables.append(self.application.objects.execute(qs))
                awaitables.append(self.application.objects.count(qs_total))
                items, total = await multi(awaitables)
                # Set total items number
                pagination['total'] = total
            else:
                if self.prefetch_queries:
                    items = await self.application.objects.prefetch(qs, *self.prefetch_queries)
                else:
                    items = await self.application.objects.execute(qs)
        except (peewee.DataError, ValueError):
            # Bad parameters
            raise web.HTTPError(400,
                                reason=self.get_response(errors=[{'code': '', 'message': 'Bad query arguments'}]))
        # Set number of fetched items
        pagination['limit'] = len(items)

        return items, pagination

    async def get(self):
        """
        Handle GET request.
        List items with given query parameters.
        """
        self.validate({k: self.get_argument(k) for k in self.request.query_arguments.keys()}, self.get_schema_input)
        try:
            qs = self.get_queryset()
        except AttributeError:
            # Wrong field name in filter or order_by
            raise web.HTTPError(400,
                                reason=self.get_response(errors=[{'code': '', 'message': 'Bad query arguments'}]))
        items, pagination = await self._get_items(qs)
        result = []
        for m in items:
            result.append(await self.serialize(m))
        self.response(result={'items': result}, pagination=pagination)

    async def head(self):
        """
        Handle HEAD request.
        Fetch total amount of items and return them in header.
        """
        self.validate({k: self.get_argument(k) for k in self.request.query_arguments.keys()}, self.get_schema_input)
        try:
            qs = self.get_queryset(paginate=False)
        except AttributeError:
            # Wrong field name in filter or order_by
            raise web.HTTPError(400,
                                reason=self.get_response(errors=[{'code': '', 'message': 'Bad query arguments'}]))
        try:
            total_num = await self.application.objects.count(qs)
        except (peewee.DataError, peewee.ProgrammingError, ValueError):
            # Bad parameters
            raise web.HTTPError(400,
                                reason=self.get_response(errors=[{'code': '', 'message': 'Bad query arguments'}]))
        self.set_header('X-Total', total_num)
        self.finish()

    async def post(self):
        """
        Handle POST request.
        Validate data and create new item.
        Returns it's id (PK).
        """
        data = self.validate(self.request.body, self.post_schema_input)
        try:
            item = await self.model_cls._create(self.application, data)
        except AttributeError:
            # We can only create item if model implements _create() method
            raise web.HTTPError(405,
                                reason=self.get_response(errors=[{'code': '', 'message': 'Method not allowed'}]))
        except (peewee.IntegrityError, peewee.DataError):
            raise web.HTTPError(400,
                                reason=self.get_response(errors=[{'code': '', 'message': 'Invalid parameters'}]))
        self.response(result=await self.serialize(item))


class ApiItemHandler(ApiHandler):
    """
    Base Item API Handler.
    Supports R, U, D from CRUDL.
    """

    @property
    def get_schema_input(self):
        """
        JSON Schema to validate DELETE request body.
        """
        return {
            "type" : "object",
            "additionalProperties": False,
            "properties" : {}
        }

    @property
    def put_schema_input(self):
        """
        JSON Schema to validate PUT request body.
        """
        return self.model_cls.to_schema(excluded=['id'])

    @property
    def delete_schema_input(self):
        """
        JSON Schema to validate DELETE request body.
        """
        return {
            "type" : "object",
            "additionalProperties": False,
            "properties" : {}
        }

    @property
    def put_schema_output(self):  # pragma: no cover
        return {}

    @property
    def delete_schema_output(self):  # pragma: no cover
        return {}

    async def get_item(self, item_id):
        """
        Fetch item from database by PK.
        Raises HTTP 404 if no item found.
        """
        try:
            return await self.application.objects.get(self.model_cls,
                                                      **{self.model_cls._meta.primary_key.name: item_id})
        except (self.model_cls.DoesNotExist, ValueError):
            raise web.HTTPError(404,
                                reason=self.get_response(errors=[{'code': '', 'message': 'Item not found'}]))

    async def get(self, item_id):
        """
        Handle GET request.
        Returns serialized object.
        """
        self.validate({k: self.get_argument(k) for k in self.request.query_arguments.keys()}, self.get_schema_input)
        item = await self.get_item(item_id)

        self.response(result=await self.serialize(item))

    async def put(self, item_id):
        """
        Handle PUT request.
        Validate data and update given item.
        Return HTTP 200 OK with result='success'.
        """
        item = await self.get_item(item_id)

        data = self.validate(self.request.body, self.put_schema_input)
        try:
            item = await item._update(self.application, data)
        except AttributeError:
            # We can only update item if model method _update() is implemented
            raise web.HTTPError(405,
                                reason=self.get_response(errors=[{'code': '', 'message': 'Method not allowed'}]))
        except (peewee.IntegrityError, peewee.DataError):
            raise web.HTTPError(400,
                                reason=self.get_response(errors=[{'code': '', 'message': 'Invalid parameters'}]))

        self.response(result=await self.serialize(item))

    async def delete(self, item_id):
        """
        Handle DELETE request.
        Model should define remove() method to handle delete logic. If method
        is not defined, HTTP 405 is raised.
        """
        # DELETE usually does not have body to validate.
        self.validate(self.request.body or {}, self.delete_schema_input)
        item = await self.get_item(item_id)
        try:
            # We can only delete item if model method _update() is implemented
            await item._delete(self.application)
        except AttributeError:
            raise web.HTTPError(405,
                                reason=self.get_response(errors=[{'code': '', 'message': 'Method not allowed'}]))

        self.response(result='Item deleted')
