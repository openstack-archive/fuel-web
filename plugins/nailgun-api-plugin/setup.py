#!/usr/bin/env python
import setuptools

# In python < 2.7.4, a lazy loading of package `pbr` will break
# setuptools if some other modules registered functions in `atexit`.
# solution from: http://bugs.python.org/issue15881#msg170215
try:
    import multiprocessing  # flake8: noqa
except ImportError:
    pass


major_version = '0.1'
minor_version = '0'
name = 'nailgun-api-plugin'

version = "{0}.{1}".format(major_version, minor_version)


setuptools.setup(
    name=name,
    #setup_requires=['pbr>=0.5.21,<1.0'],
    author='Mirantis Inc.',
    author_email='product@mirantis.com',
    url='http://mirantis.com',
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: Apache Software License"
        "Programming Language :: Python"
        "Programming Language :: Python :: 2"
        "Programming Language :: Python :: 2.6"
        "Language :: Python :: 2.7"
    ],
    entry_points={
        'nailgun.rest_api': [
            'application = api_plugin.plugin:SampleAPIPlugin'
        ]
    },
    #pbr=True
)
