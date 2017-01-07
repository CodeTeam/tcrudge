.. tcrudge documentation master file, created by
   sphinx-quickstart on Fri Jan  6 22:56:23 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to tcrudge's documentation!
===================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:


TCrudge - Simple configurable framework to create CRUDL (Create, Read, Update,
Delete, List) for models based on Tornado and Peewee ORM.


Installation
============

tcrudge is not distributed by pip (https://pypi.python.org/pypi) for now. So use installation via GitHub::

    pip install git+https://github.com/CodeTeam/tcrudge.git


Module documentation
====================

.. toctree::

    tcrudge.exceptions
    tcrudge.models
    tcrudge.response
    tcrudge.handlers
    tcrudge.decorators
    tcrudge.utils