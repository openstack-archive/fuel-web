Fuel Development Examples
=========================

This section provides examples of the Fuel development
process. It builds on the information in the `How to
contribute
<https://wiki.openstack.org/wiki/Fuel/How_to_contribute>`_
document, and the :doc:`Fuel Development Quick-Start Guide
</develop/quick_start>` which illustrate the development
process for a single Fuel component. These examples show how
to manage development and integration of a more complicated
example.

Any new feature effort should start with the creation of a
blueprint where implementation decisions and related commits
are tracked.  More information on launchpad blueprints can
be found here: `https://wiki.openstack.org/wiki/Blueprints
<https://wiki.openstack.org/wiki/Blueprints>`_.

Understanding the Fuel architecture helps you understand
which components any particular addition will impact. The
following documents provide valuable information about the
Fuel architecture, and the provisioning and deployment
process:

* `Fuel architecture on the OpenStack wiki <https://wiki.openstack.org/wiki/Fuel#Fuel_architecture>`_
* :doc:`Architecture section of Fuel documentation </develop/architecture>`
* :doc:`Visual of provisioning tasks </develop/sequence>`

Adding Zabbix Role
------------------

This section outlines the steps followed to add a new role
to Fuel. In this case, monitoring service functionality was
added by enabling the deployment of a Zabbix server
configured to monitor an OpenStack environment deployed by
Fuel.

The monitoring server role was initially planned in `this
blueprint
<https://blueprints.launchpad.net/fuel/+spec/monitoring-system>`_.
Core Fuel developers provided feedback to small
commits via Gerrit and IRC while the work was coming
together.  Ultimately the work was rolled up into two
commits including over 23k lines of code, and these two
commits were merged into `fuel-web <https://github.com/stackforge/fuel-web>`_
and `fuel-library
<https://github.com/stackforge/fuel-library>`_.

Additions to Fuel-Web for Zabbix role
-------------------------------------

In fuel-web, the `Support for Zabbix
<https://review.openstack.org/#/c/84408/>`_ commit added the
additional role to :doc:`Nailgun </develop/nailgun>`. The
reader is urged to review this commit closely as a good
example of where specific additions fit.  In order to
include this as an option in the Fuel deployment process,
the following files were included in the commit for
fuel-web:

UI components::

    nailgun/static/i18n/translation.json
    nailgun/static/js/views/cluster_page_tabs/nodes_tab_screens/node_list_screen.js

Testing additions::

    nailgun/nailgun/test/integration/test_cluster_changes_handler.py
    nailgun/nailgun/test/integration/test_orchestrator_serializer.py

General Nailgun additions::

    nailgun/nailgun/errors/__init__.py
    nailgun/nailgun/fixtures/openstack.yaml
    nailgun/nailgun/network/manager.py
    nailgun/nailgun/orchestrator/deployment_serializers.py
    nailgun/nailgun/rpc/receiver.py
    nailgun/nailgun/settings.yaml
    nailgun/nailgun/task/task.py
    nailgun/nailgun/utils/zabbix.py

Additions to Fuel-Library for Zabbix role
-----------------------------------------

In addition to the Nailgun additions, the related Puppet
modules were added to the `fuel-library repository
<https://github.com/stackforge/fuel-library>`_.  This
`Zabbix fuel-library integration
<https://review.openstack.org/#/c/101844/>`_ commit included
all the puppet files, many of which are brand new modules
specifically for Zabbix, in addition to adjustments to the
following files::

    deployment/puppet/openstack/manifests/logging.pp
    deployment/puppet/osnailyfacter/manifests/cluster_ha.pp
    deployment/puppet/osnailyfacter/manifests/cluster_simple.pp

Once all these commits passed CI and had been reviewed by
both community members and the Fuel PTLs, they were merged
into master.

Adding Hardware Support
-----------------------

This section outlines the steps followed to add support for
a Mellanox network card, which requires a kernel driver that
is available in most Linux distributions but was not loaded
by default. Adding support for other hardware would touch
similar Fuel components, so this outline should provide a
reasonable guide for contributors wishing to add support for
new hardware to Fuel.

It is important to keep in mind that the Fuel node discovery
process works by providing a bootstrap image via PXE. Once
the node boots with this image, a basic inventory of
hardware information is gathered and sent back to the Fuel
controller. If a node contains hardware requiring a unique
kernel module, the bootstrap image must contain that module
in order to detect the hardware during discovery.

In this example, loading the module in the bootstrap image
was enabled by adjusting the ISO makefile and specifying the
appropriate requirements.

Adding a hardware driver to bootstrap
-------------------------------------

The `Added bootstrap support to Mellanox
<https://review.openstack.org/#/c/101126>`_ commit shows how
this is achieved by adding the modprobe call to load the
driver specified in the requirements-rpm.txt file, requiring
modification of only two files in the fuel-main repository::

    bootstrap/module.mk
    requirements-rpm.txt

The `Adding OFED drivers installation
<https://review.openstack.org/#/c/103427>`_ commit shows the
changes made to the preseed (for Ubuntu) and kickstart (for
CentOS) files in the fuel-library repository::

    deployment/puppet/cobbler/manifests/snippets.pp
    deployment/puppet/cobbler/templates/kickstart/centos.ks.erb
    deployment/puppet/cobbler/templates/preseed/ubuntu-1204.preseed.erb
    deployment/puppet/cobbler/templates/snippets/centos_ofed_prereq_pkgs_if_enabled.erb
    deployment/puppet/cobbler/templates/snippets/ofed_install_with_sriov.erb
    deployment/puppet/cobbler/templates/snippets/ubuntu_packages.erb

Though this example did not require it, if the hardware
driver is required during the operating system installation,
the installer images (debian-installer and anaconda) would
also need to be repacked. For most installations though,
ensuring the driver package is available during installation
should be sufficient.

Adding to Fuel package repositories
-----------------------------------

If the addition will be committed back to the public Fuel
codebase to benefit others, you will need to submit a bug in
the Fuel project to request the package be added to the
repositories. This `Add neutron-lbaas-agent package
<https://bugs.launchpad.net/bugs/1330610>`_ bug is a good
example. The package must also include a license that
complies with the Fedora project license requirements for
binary firmware. See the `Fedora Project licensing page
<https://fedoraproject.org/wiki/Licensing:Main#Binary_Firmware>`_
for more information.
