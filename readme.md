TCrudge - simple async CRUDL based on Tornado and Peewee ORM (Peewee Async)

[![Documentation Status](https://readthedocs.org/projects/tcrudge/badge/?version=latest)](http://tcrudge.readthedocs.io/en/latest/?badge=latest)
[![Build Status](https://travis-ci.org/CodeTeam/tcrudge.svg?branch=master)](https://travis-ci.org/CodeTeam/tcrudge)
[![Code Climate](https://codeclimate.com/github/CodeTeam/tcrudge/badges/gpa.svg)](https://codeclimate.com/github/CodeTeam/tcrudge)
[![Issue Count](https://codeclimate.com/github/CodeTeam/tcrudge/badges/issue_count.svg)](https://codeclimate.com/github/CodeTeam/tcrudge)
[![Coverage Status](https://coveralls.io/repos/github/CodeTeam/tcrudge/badge.svg?branch=master)](https://coveralls.io/github/CodeTeam/tcrudge?branch=master)

Full documentation (http://tcrudge.readthedocs.io/en/latest/)

# What is it?
Simple configurable framework to create CRUDL (Create, Read, Update, Delete, List) for models.
TCrudge is under heavy development - tons of bugs are expected. You can use it in production, but API can be broken at any moment.

# Why?
Tornado is fast. Peewee is great. REST is wonderful.

# Dependencies
* Tornado (https://github.com/tornadoweb/tornado)
* Peewee (https://github.com/coleifer/peewee)
* Peewee-async (https://github.com/05bit/peewee-async)

# Installation
tcrudge is distributed via pypi: https://pypi.python.org/pypi/tcrudge/
```
pip install tcrudge
```

You can manually install latest version via GitHub:
```
pip install git+https://github.com/CodeTeam/tcrudge.git
```

# How to?
Describe models using Peewee ORM. Subclass ```tcrudge.ApiListHandler``` and ```tcrudge.ApiItemHandler```. Connect handlers with models using model_cls handler attribute. Add urls to tornado.Application url dispatcher.

For detailed example see tests (also, tests are available in Docker container with py.test).

You can run tests in docker container only.
You'll need docker and docker-compose.

1. Go to project root directory
2. Run docker-compose up, it builts and runs containers.
3. Go to tcrudge container bash: docker exec -ti tcrudge_tcrudge_1 bash
4. Run: DATABASE_URL=postgresql://user:dbpass@pg/test pytest

# Features?

1. DELETE request on item is disabled by default. To enable it implement _delete method in your model.
2. Models are fat. _create, _update, _delete methods are supposed to provide different logic on CRUD operations
3. Django-style filtering in list request: ```__gt```, ```__gte```, ```__lt```, ```__lte```, ```__in```, ```__isnull```, ```__like```, ```__ilike```, ```__ne``` are supported. Use ```/?model_field__<filter_type>=<filter_condition>``` for complex or ```/?model_field=<filter_condition>``` for simple filtering.
4. Django-style order by: use ```/?order_by=<field_1>,<field_2>``` etc
5. Serialization is provided by Peewee: ```playhouse.shortcuts.model_to_dict```. ```recurse```, ```exclude``` and ```max_depth``` params are implemented in base class for better experience. If you want to serialize recurse foreign keys, do not forget to modify ```get_queryset``` method (see Peewee docs for details, use ```.join()``` and ```.select()```)
6. Validation is provided out-of-the box via jsonschema. Just set input schemas for base methods (e.g. post_schema_input, get_schema_input etc). Request query is validated for *GET* and *HEAD*. Request body is validated for *POST*, *PUT* and *DELETE*.
7. Pagination is activated by default for lists. Use ```default_limit``` and ```max_limit``` for customization. Pagination params are set through headers (X-Limit, X-Offset) or query: ```/?limit=100&offset=5```. Total amount of items is not returned by default. HEAD request should be sent or total param set to 1: ```/?total=1```
8. List handler supports default filtering and ordering. Use ```default_filter``` and ```default_order_by``` class properties.

# Example

```python
import asyncio

import peewee
import peewee_async
from playhouse.db_url import parse
from tornado import web
from tornado.ioloop import IOLoop

from tcrudge.handlers import ApiListHandler, ApiItemHandler
from tcrudge.models import BaseModel

# Configure Tornado to use asyncio
IOLoop.configure('tornado.platform.asyncio.AsyncIOMainLoop')

# Create database
DATABASE_URL = 'postgresql://user:dbpass@pg/test'

db_param = parse(DATABASE_URL)

db = peewee_async.PooledPostgresqlDatabase(**db_param)


# CRUDL Model
class Company(BaseModel):
    name = peewee.TextField()
    active = peewee.BooleanField()

    class Meta:
        database = db


# CL Handler
class CompanyDetailHandler(ApiItemHandler):
    model_cls = Company


# RUD Handler
class CompanyListHandler(ApiListHandler):
    model_cls = Company
    default_filter = {'active': True}


app_handlers = [
    ('^/api/v1/companies/', CompanyListHandler),
    ('^/api/v1/companies/([^/]+)/', CompanyDetailHandler)
]

application = web.Application(app_handlers)

# ORM
application.objects = peewee_async.Manager(db)

with application.objects.allow_sync():
    # Creates table, if not exists
    Company.create_table(True)

application.listen(8080, '0.0.0.0')
loop = asyncio.get_event_loop()
# Start application
loop.run_forever()

```

# Сontributors
* [Borisov Sergey] (https://github.com/juntatalor)
* [Shalamov Maxim] (https://github.com/mvshalamov)
* [Nikolaev Alexander] (https://github.com/wokli)
* [Krasavina Alina] (https://github.com/thaelathy)
