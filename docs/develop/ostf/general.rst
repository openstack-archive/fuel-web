.. _ostf-general:

General Information
===================

Health Check or OSTF?
^^^^^^^^^^^^^^^^^^^^^

The Fuel web UI has a tab called `Health Check`.
In development team though,there is an established acronym OSTF,
which stands for OpenStack Testing Framework.
This is all about the same. For simplicity, this document will use widely
accepted term OSTF.


Main goal of OSTF
^^^^^^^^^^^^^^^^^

After OpenStack installation via Fuel, it is very important to understand whether
it was successful and if it is ready for work.
OSTF provides a set of health checks - sanity, smoke, HA and additional components tests
that check the proper operation of all system components in typical conditions.
There are tests for OpenStack scenarios validation and other specific tests useful in validating an OpenStack deployment.


General OSTF architecture
^^^^^^^^^^^^^^^^^^^^^^^^^

Tests are included into Fuel, so they will be accessible as soon as you install
Fuel on your lab. OSTF architecture is quite simple, it consists of two main packages:
- `fuel_health` - contains the test set itself and related modules
- `fuel_plugin` - contains OSTF-adapter that forms necessary test list in context of cluster deployment options and transfers them to the Fuel web UI using REST_API

On the other hand, there is some information necessary for test execution itself.
There are several modules that gather information and parse them into objects which will be used in the tests themselves. All information is gathered from Nailgun component.

.. _appendix1:

Appendix 1
^^^^^^^^^^

::

    IdentityGroup = [
        cfg.StrOpt('catalog_type',
            default='identity', may be changes on keystone
            help="Catalog type of the Identity service."),
        cfg.BoolOpt('disable_ssl_certificate_validation',
            default=False,
            help="Set to True if using self-signed SSL certificates."),
        cfg.StrOpt('uri',
            default='http://localhost/' (If you are using FileConfig set  here appropriate address)
            help="Full URI of the OpenStack Identity API (Keystone), v2"),
        cfg.StrOpt('url',
            default='http://localhost:5000/v2.0/', (If you are using FileConfig set  here appropriate address to horizon)
            help="Dashboard Openstack url, v2"),
        cfg.StrOpt('uri_v3',
            help='Full URI of the OpenStack Identity API (Keystone), v3'),
        cfg.StrOpt('strategy',
            default='keystone',
            help="Which auth method does the environment use? "
                 "(basic|keystone)"),
        cfg.StrOpt('region',
            default='RegionOne',
            help="The identity region name to use."),
        cfg.StrOpt('admin_username',
            default='nova' , (If you are using FileConfig set appropriate value here)
            help="Administrative Username to use for"
                 "Keystone API requests."),
        cfg.StrOpt('admin_tenant_name', (If you are using FileConfig set appropriate value here)
            default='service',
            help="Administrative Tenant name to use for Keystone API "
                 "requests."),
        cfg.StrOpt('admin_password', (If you are using FileConfig set appropriate value here)
            default='nova',
            help="API key to use when authenticating as admin.",
            secret=True),
        ]

    ComputeGroup = [
        cfg.BoolOpt('allow_tenant_isolation',
            default=False,
            help="Allows test cases to create/destroy tenants and "
                 "users. This option enables isolated test cases and "
                 "better parallel execution, but also requires that "
                 "OpenStack Identity API admin credentials are known."),
        cfg.BoolOpt('allow_tenant_reuse',
            default=True,
            help="If allow_tenant_isolation is True and a tenant that "
                 "would be created for a given test already exists (such "
                 "as from a previously-failed run), re-use that tenant "
                 "instead of failing because of the conflict. Note that "
                 "this would result in the tenant being deleted at the "
                 "end of a subsequent successful run."),
        cfg.StrOpt('image_ssh_user',
            default="root", (If you are using FileConfig set appropriate value here)
            help="User name used to authenticate to an instance."),
        cfg.StrOpt('image_alt_ssh_user',
            default="root", (If you are using FileConfig set appropriate value here)
            help="User name used to authenticate to an instance using "
                 "the alternate image."),
        cfg.BoolOpt('create_image_enabled',
            default=True,
            help="Does the test environment support snapshots?"),
        cfg.IntOpt('build_interval',
            default=10,
            help="Time in seconds between build status checks."),
        cfg.IntOpt('build_timeout',
            default=160,
            help="Timeout in seconds to wait for an instance to build."),
        cfg.BoolOpt('run_ssh',
            default=False,
            help="Does the test environment support snapshots?"),
        cfg.StrOpt('ssh_user',
            default='root', (If you are using FileConfig set appropriate value here)
            help="User name used to authenticate to an instance."),
        cfg.IntOpt('ssh_timeout',
            default=50,
            help="Timeout in seconds to wait for authentication to "
                 "succeed."),
        cfg.IntOpt('ssh_channel_timeout',
            default=20,
            help="Timeout in seconds to wait for output from ssh "
                 "channel."),
        cfg.IntOpt('ip_version_for_ssh',
            default=4,
            help="IP version used for SSH connections."),
        cfg.StrOpt('catalog_type',
            default='compute',
            help="Catalog type of the Compute service."),
        cfg.StrOpt('path_to_private_key',
            default='/root/.ssh/id_rsa', (If you are using FileConfig set appropriate value here)
            help="Path to a private key file for SSH access to remote "
                 "hosts"),
        cfg.ListOpt('controller_nodes',
            default=[], (If you are using FileConfig set appropriate value here)
            help="IP addresses of controller nodes"),
        cfg.ListOpt('compute_nodes',
            default=[], (If you are using FileConfig set appropriate value here)
            help="IP addresses of compute nodes"),
        cfg.StrOpt('controller_node_ssh_user',
            default='root', (If you are using FileConfig set appropriate value here)
            help="ssh user of one of the controller nodes"),
        cfg.StrOpt('controller_node_ssh_password',
            default='r00tme', (If you are using FileConfig set appropriate value here)
            help="ssh user pass of one of the controller nodes"),
        cfg.StrOpt('image_name',
            default="TestVM", (If you are using FileConfig set appropriate value here)
            help="Valid secondary image reference to be used in tests."),
        cfg.StrOpt('deployment_mode',
            default="ha", (If you are using FileConfig set appropriate value here)
            help="Deployments mode"),
        cfg.StrOpt('deployment_os',
            default="RHEL", (If you are using FileConfig set appropriate value here)
            help="Deployments os"),
        cfg.IntOpt('flavor_ref',
            default=42,
            help="Valid primary flavor to use in tests."),
    ]


    ImageGroup = [
        cfg.StrOpt('api_version',
            default='1',
            help="Version of the API"),
        cfg.StrOpt('catalog_type',
            default='image',
            help='Catalog type of the Image service.'),
        cfg.StrOpt('http_image',
            default='http://download.cirros-cloud.net/0.3.1/'
                    'cirros-0.3.1-x86_64-uec.tar.gz',
            help='http accessable image')
    ]

    NetworkGroup = [
        cfg.StrOpt('catalog_type',
            default='network',
            help='Catalog type of the Network service.'),
        cfg.StrOpt('tenant_network_cidr',
            default="10.100.0.0/16",
            help="The cidr block to allocate tenant networks from"),
        cfg.IntOpt('tenant_network_mask_bits',
            default=29,
            help="The mask bits for tenant networks"),
        cfg.BoolOpt('tenant_networks_reachable',
            default=True,
            help="Whether tenant network connectivity should be "
                 "evaluated directly"),
        cfg.BoolOpt('neutron_available',
            default=False,
            help="Whether or not neutron is expected to be available"),
    ]

    VolumeGroup = [
        cfg.IntOpt('build_interval',
            default=10,
            help='Time in seconds between volume availability checks.'),
        cfg.IntOpt('build_timeout',
            default=180,
            help='Timeout in seconds to wait for a volume to become'
                 'available.'),
        cfg.StrOpt('catalog_type',
            default='volume',
            help="Catalog type of the Volume Service"),
        cfg.BoolOpt('cinder_node_exist',
            default=True,
            help="Allow to run tests if cinder exist"),
        cfg.BoolOpt('multi_backend_enabled',
            default=False,
            help="Runs Cinder multi-backend test (requires 2 backends)"),
        cfg.StrOpt('backend1_name',
            default='BACKEND_1',
            help="Name of the backend1 (must be declared in cinder.conf)"),
        cfg.StrOpt('backend2_name',
            default='BACKEND_2',
            help="Name of the backend2 (must be declared in cinder.conf)"),
    ]

    ObjectStoreConfig = [
        cfg.StrOpt('catalog_type',
            default='object-store',
            help="Catalog type of the Object-Storage service."),
        cfg.StrOpt('container_sync_timeout',
            default=120,
            help="Number of seconds to time on waiting for a container"
                 "to container synchronization complete."),
        cfg.StrOpt('container_sync_interval',
            default=5,
            help="Number of seconds to wait while looping to check the"
                 "status of a container to container synchronization"),
    ]


