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
name = 'nova-network-plugin'

version = "{0}.{1}".format(major_version, minor_version)

custom_roles_entry_points = [
    'process_node_attrs = '
    'nova_network.nova_network_plugin:NovaNetworkPlugin',
    'process_cluster_attrs = '
    'nova_network.nova_network_plugin:NovaNetworkPlugin',
    'process_cluster_ha_attrs = '
    'nova_network.nova_network_plugin:NovaNetworkPlugin'
]

setuptools.setup(
    name=name,
    version=version,
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
    packages=['nova_network'],
    package_data={'nova_network': ['config.yaml']},
    entry_points={
        'nailgun.plugin': [
            'plugin = nova_network.nova_network_plugin:NovaNetworkPlugin'
        ],
        'nailgun.rest_api': [
            'plugin = nova_network.nova_network_plugin:NovaNetworkPlugin'
        ],
        'nailgun.custom_roles': custom_roles_entry_points
    }
)
