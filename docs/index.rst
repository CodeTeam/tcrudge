.. tcrudge documentation master file, created by
   sphinx-quickstart on Fri Jan  6 22:56:23 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to tcrudge's documentation!
===================================

.. toctree::
   :maxdepth: 2


TCrudge - Simple configurable framework to create CRUDL (Create, Read, Update, Delete, List) for models based on Tornado and Peewee ORM.
TCrudge is under heavy development - tons of bugs are expected. You can use it in production, but API can be broken at any moment.

Installation
============

Tcrudge is distributed via pypi (https://pypi.python.org/pypi/tcrudge/) ::

   pip install tcrudge

You can manually install latest version via GitHub::

   pip install git+https://github.com/CodeTeam/tcrudge.git

Example
=======
One-file sample application::

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

Module documentation
====================

.. toctree::

    tcrudge.exceptions
    tcrudge.models
    tcrudge.response
    tcrudge.handlers
    tcrudge.decorators
    tcrudge.utils