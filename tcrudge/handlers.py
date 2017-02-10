"""
Module contains basic handlers:

* BaseHandler - to be used for custom handlers. For instance - RPC, if you wish.
* ApiHandler - Abstract for API handlers above.
* ApiListHandler - Create (POST), List view (GET).
* ApiItemHandler - detailed view (GET), Update (PUT), Delete (DELETE).
"""

import json
import operator
import traceback
from abc import ABCMeta, abstractmethod

import peewee
from jsonschema.validators import validator_for
from playhouse.shortcuts import model_to_dict
from tornado import web
from tornado.gen import multi
from tornado.escape import xhtml_escape

from tcrudge.exceptions import HTTPError
from tcrudge.models import FILTER_MAP
from tcrudge.response import response_json, response_msgpack
from tcrudge.utils.validation import validate_integer


class BaseHandler(web.RequestHandler):
    """
    Base helper class. Provides basic handy responses.

    To be used for customized handlers that don't fit REST API recommendations.

    Defines response types in relation to Accept header. Response interface is
    described in corresponding module.

    By default, inherited handlers have callback functions for JSON and
    MessagePack responses.
    """

    response_callbacks = {
        'application/json': response_json,
        'application/x-msgpack': response_msgpack,
    }

    def get_response(self, result=None, errors=None, **kwargs):
        """
        Method returns conventional formatted byte answer.

        It gets Accept header, returns answer processed by callback.

        :param result: contains result if succeeded
        :param errors: contains errors if any
        :param kwargs: other answer attributes
        :return: byte answer of appropriate content type
        :rtype: bytes

        """
        _errors = [{k: xhtml_escape(v) for k, v in i.items()} for i in errors] if errors else []
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

        :param result: contains result if succeeded
        :param errors: contains errors if any
        :param kwargs: other answer attributes
        """
        self.write(self.get_response(result, errors, **kwargs))
        self.finish()

    def write_error(self, status_code, **kwargs):
        """
        Method gets traceback, writes it into response, finishes response.

        :param status_code: tornado parameter to format html, we don't use it.
        :type status_code: int
        :param kwargs: in debug mode must contain exc_info.
        :type kwargs: dict
        """
        exc_info = kwargs.get('exc_info')
        if self.settings.get(
                "serve_traceback") and exc_info:  # pragma: no cover
            # in debug mode, try to send a traceback
            self.set_header('Content-Type', 'text/plain')
            for line in traceback.format_exception(*exc_info):
                self.write(line)
        # exc_info[1] - HTTPError instance
        # Finish request with exception body or exception reason
        err_text = getattr(exc_info[1], 'body', self._reason)
        self.write(err_text)
        self.finish()

    async def validate(self, data, schema, **kwargs):
        """
        Method to validate parameters.
        Raises HTTPError(400) with error info for invalid data.

        :param data: bytes or dict
        :param schema: dict, valid JSON schema
          (http://json-schema.org/latest/json-schema-validation.html)
        :return: None if data is not valid. Else dict(data)
        """
        # Get and parse arguments
        if isinstance(data, dict):
            _data = data  # pragma: no cover
        else:
            try:
                _data = json.loads(data.decode())
            except ValueError as exc:
                # json.loads error
                raise HTTPError(
                    400,
                    body=self.get_response(
                        errors=[
                            {
                                'code': '',
                                'message': 'Request body is not a valid json object',
                                'detail': str(exc)
                            }
                        ]
                    )
                )
        v = validator_for(schema)(schema)
        errors = []
        for error in v.iter_errors(_data):
            # error is an instance of jsonschema.exceptions.ValidationError
            errors.append({'code': '',
                           'message': 'Validation failed',
                           'detail': error.message})
        if errors:
            # data does not pass validation
            raise HTTPError(400, body=self.get_response(errors=errors))
        return _data

    async def bad_permissions(self):
        """
        Returns answer of access denied.

        :raises: HTTPError 401
        """
        raise HTTPError(
            401,
            body=self.get_response(
                errors=[
                    {
                        'code': '',
                        'message': 'Access denied'
                    }
                ]
            )
        )

    async def is_auth(self):
        """
        Validate user authorized. Abstract. Auth logic is up to user.
        """
        return True

    async def get_roles(self):
        """
        Gets roles. Abstract. Auth logic is up to user.
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

        Schema must be a dict.
        """
        return {}

    async def serialize(self, model):
        """
        Method to serialize a model.

        By default all fields are serialized by model_to_dict.
        The model can be any model instance to pass through this method. It
        MUST be a Model instance, it won't work for basic types containing
        such instances.

        User have to handle it by their own hands.

        :param model: Model instance to serialize.
        :type model: Model instance.
        :return: serialized model.
        :rtype: dict
        """
        return model_to_dict(model,
                             recurse=self.recurse,
                             exclude=self.exclude_fields,
                             max_depth=self.max_depth)


class ApiListHandler(ApiHandler):
    """
    Base List API Handler. Supports C, L from CRUDL.
    Handles pagination,

    * default limit is defined
    * maximum limit is defined

    One can redefine that in their code.

    Other pagination parameters are:

    * limit - a positive number of items to show on a single page, int.
    * offset - a positive int to define the position in result set to start with.
    * total - A boolean to define total amount of items to be put in result set or not. 1 or 0.

    Those parameters can be sent as either GET parameters or HTTP headers.
    HTTP headers are more significant during parameters processing, but GET
    parameters are preferable to use as conservative way of pagination.
    HTTP headers are:

    * X-Limit
    * X-Offset
    * X-Total

    "exclude" filter args are for pagination, you must not redefine them ever.
    Otherwise you'd have to also redefine the prepare method.

    Some fieldnames can be added to that list. Those are fields one wishes not
    to be included to filters.
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
        JSON Schema to validate GET Url parameters.
        By default it contains pagination parameters as required fields.
        If you wish to use query filters via GET parameters, you need to
        redefine get_schema_input so that request with filter parameters
        would be valid.

        In schema you must define every possible way to filter a field,
        you wish to be filtered, in every manner it should be filtered.
        For example, if you wish to filter by a field "name" so that the query
        returns you every object with name like given string::

          {
              "type": "object",
              "additionalProperties": False,
              "properties": {
                "name__like": {"type": "string"},
                "total": {"type": "string"},
                "limit": {"type": "string"},
                "offset": {"type": "string"},
                "order_by": {"type": "string"},
              },
          }


        If you wish to filter by a field "created_dt" by given range::

          {
              "type": "object",
              "additionalProperties": False,
              "properties": {
                "created_dt__gte": {"type": "string"},
                "created_dt__lte": {"type": "string"},
                "total": {"type": "string"},
                "limit": {"type": "string"},
                "offset": {"type": "string"},
                "order_by": {"type": "string"},
              },
          }


        To cut it short, you need to add parameters like "field__operator"
        for every field you wish to be filtered and for every operator you
        wish to be used.

        Every schema must be a dict.

        :return: returns schema.
        :rtype: dict
        """
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "total": {"type": "string"},
                "limit": {"type": "string"},
                "offset": {"type": "string"},
                "order_by": {"type": "string"},
            },
        }

    @property
    def post_schema_output(self):
        """
        JSON Schema to validate POST request body. Abstract.

        Every schema must be a dict.

        :return: dict
        """
        return {}

    @property
    def post_schema_input(self):  # pragma: no cover
        """
        JSON schema of our model is generated here. Basically it is used for
        Create method - list handler, method POST.

        Hint: Modified version of this schema can be used for Update (PUT,
        detail view).

        :return: JSON schema of given model_cls Model.
        :rtype: dict
        """
        return self.model_cls.to_schema(excluded=['id'])

    @property
    def default_filter(self):
        """
        Default queryset WHERE clause. Used for list queries first.
        One must redefine it to customize filters.

        :return: dict
        """
        return {}

    @property
    def default_order_by(self):
        """
        Default queryset ORDER BY clause. Used for list queries.
        Order by must contain a string with a model field name.
        """
        return ()

    def prepare(self):
        """
        Method to get and validate offset and limit params for GET REST request.
        Total is boolean 1 or 0.

        Works for GET method only.
        """
        # Headers are more significant when taking limit and offset
        if self.request.method == 'GET':
            # No more than MAX_LIMIT records at once
            # Not less than 1 record at once
            limit = self.request.headers.get('X-Limit',
                                             self.get_query_argument('limit',
                                                                     self.default_limit))
            self.limit = validate_integer(limit, 1, self.max_limit,
                                          self.default_limit)

            # Offset should be a non negative integer
            offset = self.request.headers.get('X-Offset',
                                              self.get_query_argument('offset',
                                                                      0))
            self.offset = validate_integer(offset, 0, None, 0)

            # Force send total amount of items
            self.total = 'X-Total' in self.request.headers or \
                         self.get_query_argument(
                             'total', None) == '1'

    @classmethod
    def qs_filter(cls, qs, flt, value, process_value=True):
        """
        Private method to set WHERE part of query.
        If required, Django-style filter is available via qs.filter()
        and peewee.DQ - this method provides joins.

        Filter relational operators are:
        * NOT - '-', not operator, should be user as prefix
        * < - 'lt', less than
        * > - 'gt', greater than
        * <= - 'lte', less than or equal
        * >= - 'gte', greater than or equal
        * != - 'ne', not equal
        * LIKE - 'like', classic like operator
        * ILIKE - 'ilike', case-insensitive like operator
        * IN - 'in', classic in. Values should be separated by comma
        * ISNULL - 'isnull', operator to know if smth is equal to null. Use -<fieldname>__isnull for IS NOT NULL
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
    def qs_order_by(cls, qs, value, process_value=True):
        """
        Set ORDER BY part of response.

        Fields are passed in a string with commas to separate values.
        '-' prefix means descending order, otherwise it is ascending order.

        :return: orderbyed queryset
        :rtype: queryset
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

        By default it uses qs_filter and qs_order_by.
        All arguments for WHERE clause are passed with AND condition.
        """
        # Set limit / offset parameters
        qs = self.model_cls.select()
        if paginate:
            qs = qs.limit(self.limit).offset(self.offset)

        # Set default filter values
        for k, v in self.default_filter.items():
            qs = self.qs_filter(qs, k, v, process_value=False)

        # Set default order_by values
        for v in self.default_order_by:
            qs = self.qs_order_by(qs, v, process_value=False)

        for k, v in self.request.arguments.items():
            if k in self.exclude_filter_args:
                # Skipping special arguments (limit, offset etc)
                continue
            elif k == 'order_by':
                # Ordering
                qs = self.qs_order_by(qs, v[0])
            else:
                # Filtration. All arguments passed with AND condition (WHERE
                # <...> AND <...> etc)
                qs = self.qs_filter(qs, k, v[0])
        return qs

    async def _get_items(self, qs):
        """
        Gets queryset and paginates it.
        It executes database query. If total amount of items should be
        received (self.total = True), queries are executed in parallel.

        :param qs: peewee queryset
        :return: tuple: executed query, pagination info (dict)
        :raises: In case of bad query parameters - HTTP 400.
        """
        pagination = {'offset': self.offset}
        try:
            if self.total:
                # Execute requests to database in parallel (items + total)
                awaitables = []
                qs_total = self.get_queryset(paginate=False)
                if self.prefetch_queries:
                    # Support of prefetch queries
                    awaitables.append(self.application.objects.prefetch(qs,
                                                                        *self.prefetch_queries))
                else:
                    awaitables.append(self.application.objects.execute(qs))
                awaitables.append(self.application.objects.count(qs_total))
                items, total = await multi(awaitables)
                # Set total items number
                pagination['total'] = total
            else:
                if self.prefetch_queries:
                    items = await self.application.objects.prefetch(qs,
                                                                    *self.prefetch_queries)
                else:
                    items = await self.application.objects.execute(qs)
        except (peewee.DataError, ValueError) as e:
            # Bad parameters
            raise HTTPError(
                400,
                body=self.get_response(
                    errors=[
                        {
                            'code': '',
                            'message': 'Bad query arguments',
                            'detail': str(e)
                        }
                    ]
                )
            )
        # Set number of fetched items
        pagination['limit'] = len(items)  # TODO WTF? Why limit is set?

        return items, pagination

    async def get(self):
        """
        Handles GET request.

        1. Validates GET parameters using GET input schema and validator.
        2. Executes query using given query parameters.
        3. Paginates.
        4. Serializes result.
        5. Writes to response, not finishing it.

        :raises: In case of bad query parameters - HTTP 400.
        """
        await self.validate({k: self.get_argument(k) for k in self.request.query_arguments.keys()},
                            self.get_schema_input)
        try:
            qs = self.get_queryset()
        except AttributeError as e:
            # Wrong field name in filter or order_by
            raise HTTPError(
                400,
                body=self.get_response(
                    errors=[
                        {
                            'code': '',
                            'message': 'Bad query arguments',
                            'detail': str(e)
                        }
                    ]
                )
            )
        items, pagination = await self._get_items(qs)
        result = []
        for m in items:
            result.append(await self.serialize(m))
        self.response(result={'items': result}, pagination=pagination)

    async def head(self):
        """
        Handles HEAD request.

        1. Validates GET parameters using GET input schema and validator.
        2. Fetches total amount of items and returns it in X-Total header.
        3. Finishes response.

        :raises: In case of bad query parameters - HTTPError 400.
        """
        await self.validate({k: self.get_argument(k) for k in self.request.query_arguments.keys()},
                            self.get_schema_input)
        try:
            qs = self.get_queryset(paginate=False)
        except AttributeError as e:
            # Wrong field name in filter or order_by
            # Request.body is not available in HEAD request
            # No detail info will be provided
            raise HTTPError(400)
        try:
            total_num = await self.application.objects.count(qs)
        except (peewee.DataError, peewee.ProgrammingError, ValueError) as e:
            # Bad parameters
            # Request.body is not available in HEAD request
            # No detail info will be provided
            raise HTTPError(400)
        self.set_header('X-Total', total_num)
        self.finish()

    async def post(self):
        """
        Handles POST request.
        Validates data and creates new item.
        Returns serialized object written to response.

        HTTPError 405 is raised in case of not creatable model (there must be
        _create method implemented in model class).

        HTTPError 400 is raised in case of violated constraints, invalid
        parameters and other data and integrity errors.

        :raises: HTTPError 405, 400
        """
        data = await self.validate(self.request.body, self.post_schema_input)
        try:
            item = await self.model_cls._create(self.application, data)
        except AttributeError as e:
            # We can only create item if _create() model method implemented
            raise HTTPError(
                405,
                body=self.get_response(
                    errors=[
                        {
                            'code': '',
                            'message': 'Method not allowed',
                            'detail': str(e)
                        }
                    ]
                )
            )
        except (peewee.IntegrityError, peewee.DataError) as e:
            raise HTTPError(
                400,
                body=self.get_response(
                    errors=[
                        {
                            'code': '',
                            'message': 'Invalid parameters',
                            'detail': str(e)
                        }
                    ]
                )
            )
        self.response(result=await self.serialize(item))


class ApiItemHandler(ApiHandler):
    """
    Base Item API Handler.
    Supports R, U, D from CRUDL.
    """

    def __init__(self, *args, **kwargs):
        super(ApiItemHandler, self).__init__(*args, **kwargs)
        self._instance = None

    @property
    def get_schema_input(self):
        """
        JSON Schema to validate DELETE request body.

        :returns: GET JSON schema
        :rtype: dict
        """
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {}
        }

    @property
    def put_schema_input(self):
        """
        JSON Schema to validate PUT request body.

        :return: JSON schema of PUT
        :rtype: dict
        """
        return self.model_cls.to_schema(excluded=['id'])

    @property
    def delete_schema_input(self):
        """
        JSON Schema to validate DELETE request body.

        :returns: JSON schema for DELETE.
        :rtype: dict
        """
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {}
        }

    @property
    def put_schema_output(self):  # pragma: no cover
        """
        Returns PUT Schema, empty be default.

        :rtype: dict
        """
        return {}

    @property
    def delete_schema_output(self):  # pragma: no cover
        """
        Returns DELETE Schema, empty be default.

        :rtype: dict
        """
        return {}

    async def get_item(self, item_id):
        """
        Fetches item from database by PK.
        Result is cached in self._instance for multiple calls

        :raises: HTTP 404 if no item found.
        :returns: raw object if exists.
        :rtype: ORM model instance.
        """
        if not self._instance:
            try:
                self._instance = await self.application.objects.get(self.model_cls,
                                                                    **{self.model_cls._meta.primary_key.name: item_id})
            except (self.model_cls.DoesNotExist, ValueError) as e:
                raise HTTPError(
                    404,
                    body=self.get_response(
                        errors=[
                            {
                                'code': '',
                                'message': 'Item not found',
                                'detail': str(e)
                            }
                        ]
                    )
                )
        return self._instance

    async def get(self, item_id):
        """
        Handles GET request.

        1. Validates request.
        2. Writes serialized object of ORM model instance to response.
        """
        await self.validate({k: self.get_argument(k) for k in self.request.query_arguments.keys()},
                            self.get_schema_input, item_id=item_id)
        item = await self.get_item(item_id)

        self.response(result=await self.serialize(item))

    async def put(self, item_id):
        """
        Handles PUT request.
        Validates data and updates given item.

        Returns serialized model.

        Raises 405 in case of not updatable model (there must be
        _update method implemented in model class).

        Raises 400 in case of violated constraints, invalid parameters and other
        data and integrity errors.

        :raises: HTTP 405, HTTP 400.
        """
        item = await self.get_item(item_id)

        data = await self.validate(self.request.body, self.put_schema_input, item_id=item_id)
        try:
            item = await item._update(self.application, data)
        except AttributeError as e:
            # We can only update item if model method _update is implemented
            raise HTTPError(
                405,
                body=self.get_response(
                    errors=[
                        {
                            'code': '',
                            'message': 'Method not allowed',
                            'detail': str(e)
                        }
                    ]
                )
            )
        except (peewee.IntegrityError, peewee.DataError) as e:
            raise HTTPError(
                400,
                body=self.get_response(
                    errors=[
                        {
                            'code': '',
                            'message': 'Invalid parameters',
                            'detail': str(e)
                        }
                    ]
                )
            )

        self.response(result=await self.serialize(item))

    async def delete(self, item_id):
        """
        Handles DELETE request.

        _delete method must be defined to handle delete logic. If method
        is not defined, HTTP 405 is raised.

        If deletion is finished, writes to response HTTP code 200 and
        a message 'Item deleted'.

        :raises: HTTPError 405 if model object is not deletable.
        """
        # DELETE usually does not have body to validate.
        await self.validate(self.request.body or {}, self.delete_schema_input, item_id=item_id)
        item = await self.get_item(item_id)
        try:
            # We can only delete item if model method _delete() is implemented
            await item._delete(self.application)
        except AttributeError as e:
            raise HTTPError(
                405,
                body=self.get_response(
                    errors=[
                        {
                            'code': '',
                            'message': 'Method not allowed',
                            'detail': str(e)
                        }
                    ]
                )
            )

        self.response(result='Item deleted')
