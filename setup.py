# -*- coding: utf-8 -*-
"""Packaging logic for beem."""
import codecs
import io
import os
import sys

from setuptools import setup

# Work around mbcs bug in distutils.
# http://bugs.python.org/issue10945

try:
    codecs.lookup('mbcs')
except LookupError:
    ascii = codecs.lookup('ascii')
    codecs.register(lambda name, enc=ascii: {True: enc}.get(name == 'mbcs'))

VERSION = '0.1.0'

tests_require = ['mock >= 2.0.0', 'pytest', 'pytest-mock', 'parameterized']

requires = [
    "beem",
    "steemengine"
]


def write_version_py(filename):
    """Write version."""
    cnt = """\"""THIS FILE IS GENERATED FROM beem SETUP.PY.\"""
version = '%(version)s'
"""
    with open(filename, 'w') as a:
        a.write(cnt % {'version': VERSION})


def get_long_description():
    """Generate a long description from the README file."""
    descr = []
    for fname in ('README.md',):
        with io.open(fname, encoding='utf-8') as f:
            descr.append(f.read())
    return '\n\n'.join(descr)


if __name__ == '__main__':

    # Rewrite the version file everytime
    write_version_py('distribubot/version.py')

    setup(
        name='distribubot',
        version=VERSION,
        description='Distribution of steem-engine Token through comments',
        url='http://github.com/steem-engine-exchange/distribubot',
        long_description=get_long_description(),
        author='Holger Nahrstaedt',
        author_email='holgernahrstaedt@gmx.de',
        maintainer='Holger Nahrstaedt',
        maintainer_email='holgernahrstaedt@gmx.de',
        keywords=['steem', 'token', 'steem-engine'],
        packages=[
            "distribubot",
        ],
        classifiers=[
            'License :: OSI Approved :: MIT License',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3.4',
            'Programming Language :: Python :: 3.5',
            'Programming Language :: Python :: 3.6',
            'Development Status :: 4 - Beta',
            'Intended Audience :: Developers',
        ],
        install_requires=requires,
        entry_points={
            'console_scripts': [
                'distribubot=distribubot.distribubot:main',
            ],
        },
        include_package_data=True,
    )

