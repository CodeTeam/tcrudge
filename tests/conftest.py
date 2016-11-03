"""
General fixtures for Tornado application testing
"""

import os

import peewee_async
import psycopg2
import pytest
from playhouse.db_url import parse
from tornado.ioloop import IOLoop
from tornado.web import Application

IOLoop.configure('tornado.platform.asyncio.AsyncIOMainLoop')

db_param = parse(os.environ.get('DATABASE_URL'))
TEST_DB = db_param['database']
TEST_USER = db_param['user']
TEST_PWD = db_param['password']
TEST_HOST = db_param['host']

db = peewee_async.PooledPostgresqlDatabase(**db_param)
db.allow_sync = False


@pytest.fixture(scope='session')
def app(async_db):
    """
    Application fixture
    Required by pytest-tornado
    """
    application = Application()
    application.objects = peewee_async.Manager(async_db)
    return application


@pytest.fixture(scope='session', autouse=True)
def async_db(request):
    """
    Database fixture
    Creates Postgresql test database and applies yoyo migrations
    Drops database on teardown
    """
    # Create database
    with psycopg2.connect(
            'host={0} dbname=postgres user={1} password={2}'.format(TEST_HOST, TEST_USER, TEST_PWD)) as conn:
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as cur:
            cur.execute('CREATE DATABASE %s' % TEST_DB)

    def teardown():
        # Opened connections should be terminated before dropping database
        terminate_sql = "SELECT pg_terminate_backend(pg_stat_activity.pid) " \
                        "FROM pg_stat_activity " \
                        "WHERE pg_stat_activity.datname = %s " \
                        "AND pid <> pg_backend_pid();"
        with psycopg2.connect(
                'host={0} dbname=postgres user={1} password={2}'.format(TEST_HOST, TEST_USER, TEST_PWD)) as conn:
            conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
            with conn.cursor() as cur:
                cur.execute(terminate_sql, (TEST_DB,))
                cur.execute('DROP DATABASE %s' % TEST_DB)

    request.addfinalizer(teardown)

    return db


@pytest.fixture
def clean_table(request, async_db):
    """
    This fixture should be used only with
    request.param set to iterable with subclasses of peewee.Model or single peewee.Model
    It clears all data in request.param table
    Usage:
    @pytest.mark.parametrize('clean_table', [(Log, Route)], indirect=True)
    """

    def teardown():
        with async_db.allow_sync():
            for param in request.param:
                param.delete().execute()

    request.addfinalizer(teardown)
