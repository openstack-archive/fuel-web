#!/usr/bin/env python
import setuptools


major_version = '0.1'
minor_version = '0'
name = 'nailgun-ceph-plugin'

version = "{0}.{1}".format(major_version, minor_version)

custom_roles_entry_points = [
    'custom_release_roles_metadata = nailgun_ceph.custom_role:CephRolePlugin',
    'process_cluster_attributes = nailgun_ceph.custom_role:CephRolePlugin',
    'custom_volumes = nailgun_ceph.custom_role:CephRolePlugin',
    'custom_volumes_mapping = nailgun_ceph.custom_role:CephRolePlugin',
    'custom_volumes_generators = nailgun_ceph.custom_role:CephRolePlugin',
    'custom_volumes_for_disk = nailgun_ceph.custom_role:CephRolePlugin',
    'process_volumes = nailgun_ceph.custom_role:CephRolePlugin',
    'process_volumes_metadata = nailgun_ceph.custom_role:CephRolePlugin',
    'custom_roles = nailgun_ceph.custom_role:CephRolePlugin',
    'process_custom_roles = nailgun_ceph.custom_role:CephRolePlugin',
    'custom_pending_roles = nailgun_ceph.custom_role:CephRolePlugin',
    'process_custom_pending_roles = nailgun_ceph.custom_role:CephRolePlugin',
    'get_custom_pending_roles = nailgun_ceph.custom_role:CephRolePlugin',
    'process_node_attrs = nailgun_ceph.custom_role:CephRolePlugin',
    'process_cluster_attrs = nailgun_ceph.custom_role:CephRolePlugin'
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
    packages=['nailgun_ceph'],
    package_data={'nailgun_ceph': ['config.yaml']},
    entry_points={
        'nailgun.plugin': [
            'plugin = nailgun_ceph.custom_role:CephRolePlugin'
        ],
        'nailgun.custom_roles': custom_roles_entry_points
    }
)
