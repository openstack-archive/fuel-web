Devops Guide
============


Clean installation
------------------

Fuel-Devops is a sublayer between application and target environment (currently
only supported under libvirt).


This application is used for testing purposes like grouping virtual machines to
environments, booting KVM VMs locally from the ISO image and over the network
via PXE, creating, snapshotting and resuming back the whole environment in
single action, create virtual machines with multiple NICs, multiple hard drives
and many other customizations with a few lines of code in system tests.

For sources please refer to [fuel-devops@github](https://github.com/stackforge/fuel-devops)

Dependencies ::

    sudo apt-get install postgresql \
    python-psycopg2 \
    python-ipaddr \
    python-libvirt \
    python-paramiko \
    python-django \
    git \
    python-xmlbuilder \
    python-libvirt \
    python-django-south

**NOTE** Depending from your distro some of these packages could not exists in your distro upstream repositories. In this case please refer to *Devops installation in virtualenv* chapter.

Devops Installation from packages
---------------------------------

Here is nothing strange just do:

    sudo apt-get install postgresql \
    python-psycopg2 \
    python-ipaddr \
    python-libvirt \
    python-paramiko \
    python-django \
    git \
    python-xmlbuilder \
    python-libvirt \
    python-django-south
    
then clone fuel-devops repo and run setup.py:

	git clone git://github.com/stackforge/fuel-devops.git
	cd fuel-devops
	python ./setup.py

Devops installation in virtualenv
---------------------------------

First let's install packages required for that way:
	apt-get install postgresql-server-dev-all python-libvirt python-dev python-django

Then create virtualenv:

	virtualenv --system-site-packages devops-venv

And install devops inside it:

	. devops-venv/bin/activate
	pip install git+https://github.com/stackforge/fuel-devops.git --upgrade

setup.py in fuel-devops repository does everything required.

System wide settings required for devops
----------------------------------------

Basicly devops requires the following:

 * Existent libvirt's pool(called 'default' by default)
 * Permissions to run KVM VMs with libvirt
 * Alive Postgresql database with grants and devops schema
 * Optionally, Nested Paging enabled

libvirt pool
~~~~~~~~~~~~

    sudo virsh pool-define-as --type=dir --name=default --target=/var/lib/libvirt/images
    sudo virsh pool-autostart default
    sudo virsh pool-start default

Permissions to run KVM VMs with libvirt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    sudo usermod $(whoami) -a -G libvirtd,sudo

Alive Postgresql database with grants and devops schema
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    sudo sed -ir 's/peer/trust/' /etc/postgresql/9.1/main/pg_hba.conf
    sudo service postgresql restart
    django-admin.py syncdb --settings=devops.settings
    django-admin.py migrate devops --settings=devops.settings

**NOTE** Depending from your distro django-admin.py may refer to system-wide django installed from package.
In this case you could get an exception means devops.settings module is not resolvable. To fix this run django-admin.py (or django-admin) with full path:

    ./bin/django-admin syncdb --settings=devops.settings
    ./bin/django-admin migrate devops --settings=devops.settings

Optionally, Nested Paging enabled
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This option enables in BIOS and turns on by kvm kernel module by default.
To load kernel module run

    kvm-ok

it will show something like

    INFO: /dev/kvm exists
    KVM acceleration can be used

Then run

    cat /sys/module/kvm_intel/parameters/nested

There will be Y letter.

Environment creation via Devops + Fuel_main
-------------------------------------------

Clone fuel-main:

    git clone https://github.com/stackforge/fuel-main
    cd fuel-main/

Install requirements:

    pip install -r ./fuelweb_test/requirements.txt --upgrade

If you don't have a Fuel ISO and wanna build it please refer to
[building-fuel-iso](http://docs.mirantis.com/fuel-dev/develop/env.html#building-the-fuel-iso) section.

Next, you need to define several variables for the future environment:

    export ISO_PATH=<path_to_iso>
    export NODES_COUNT=<number_nodes>
    export ENV_NAME=<name_of_env>

Alternatively, you can edit this file to set them as a default values:

    fuelweb_test/settings.py

Start tests by running this command:

    export PYTHONPATH=$(pwd)
    ./utils/jenkins/system_tests.sh -t test -w $(pwd) -j fuelweb_test -i $ISO_PATH -o --group=setup

For more information about how tests work, read the usage information ::

    "./utils/jenkins/system_tests.sh" -h
