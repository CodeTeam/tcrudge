import os
import re
import shutil
import sys
from io import open

from setuptools import setup

try:
    from pypandoc import convert


    def read_md(f):
        return convert(f, 'rst')
except ImportError:
    print("warning: pypandoc module not found, could not convert Markdown to RST")


    def read_md(f):
        return open(f, 'r', encoding='utf-8').read()

install_requires = [
    'aiopg==0.10.0',
    'peewee==2.8.3',
    'peewee-async==0.5.5',
    'psycopg2==2.6.2',
    'tornado==4.4.2',
    'jsonschema==2.5.1',
    'msgpack-python==0.4.8',
    'git+https://github.com/mvshalamov/GenSON@v0.4.5',
]

extras_require = {'tests': [
    'py==1.4.31',
    'pytest==3.0.2',
    'pytest-cov==2.3.1',
    'pytest-env==0.6.0',
    'pytest-tornado==0.4.5',
    'coverage==4.2'
], }

def get_version(package):
    """
    Return package version as listed in `__version__` in `init.py`.
    """
    init_py = open(os.path.join(package, '__init__.py')).read()
    return re.search(r"^__version__\W*=\W*'([\d.abrcdev]+)'", init_py).group(1)


def get_packages(package):
    """
    Return root package and all sub-packages.
    """
    return [dirpath
            for dirpath, dirnames, filenames in os.walk(package)
            if os.path.exists(os.path.join(dirpath, '__init__.py'))]


def get_package_data(package):
    """
    Return all files under the root package, that are not in a
    package themselves.
    """
    walk = [(dirpath.replace(package + os.sep, '', 1), filenames)
            for dirpath, dirnames, filenames in os.walk(package)
            if not os.path.exists(os.path.join(dirpath, '__init__.py'))]

    filepaths = []
    for base, filenames in walk:
        filepaths.extend([os.path.join(base, filename)
                          for filename in filenames])
    return {package: filepaths}


version = get_version('tcrudge')

if sys.argv[-1] == 'publish':
    try:
        import pypandoc
    except ImportError:
        print("pypandoc not installed.\nUse `pip install pypandoc`.\nExiting.")
    if os.system("pip freeze | grep wheel"):
        print("wheel not installed.\nUse `pip install wheel`.\nExiting.")
        sys.exit()
    if os.system("pip freeze | grep twine"):
        print("twine not installed.\nUse `pip install twine`.\nExiting.")
        sys.exit()
    os.system("python setup.py sdist bdist_wheel")
    os.system("twine upload dist/*")
    print("You probably want to also tag the version now:")
    print("  git tag -a %s -m 'version %s'" % (version, version))
    print("  git push --tags")
    shutil.rmtree('dist')
    shutil.rmtree('build')
    shutil.rmtree('tcrudge.egg-info')
    sys.exit()

setup(
    name='tcrudge',
    version=version,
    url='https://github.com/CodeTeam/tcrudge',
    license='MIT',
    description='Tornado RESTful API with Peewee',
    long_description=read_md('readme.md'),
    author='Code Team',
    author_email='saborisov@sberned.ru',
    packages=get_packages('tcrudge'),
    package_data=get_package_data('tcrudge'),
    install_requires=install_requires,
    extras_require=extras_require,
    zip_safe=False,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Framework :: Tornado',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.5',
        'Topic :: Internet :: WWW/HTTP',
    ]
)
