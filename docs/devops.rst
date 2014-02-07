For Ubuntu server 12.10
=======================
Clean installation
------------------ 

Fuel-Devops is a sublayer between application and target environment (currently
only supported under libvirt).


This application is used for testing purposes like grouping virtual machines to 
environments, booting KVM VMs locally from the ISO image and over the network 
via PXE, creating, snapshotting and resuming back the whole environment in 
single action, create virtual machines with multiple NICs, multiple hard drives 
and many other customizations with a few lines of code in system tests.

Dependencies ::

    sudo apt-get install postgresql python-psycopg2 python-ipaddr python-libvirt
    sudo apt-get install python-paramiko python-django git python-xmlbuilder 
    sudo apt-get install python-libvirt python-django-south
    git clone https://github.com/stackforge/fuel-devops.git
    cd fuel-devops/
    export PYTHONPATH=$PYTHONPATH:$(pwd)
    sudo sed -ir 's/peer/trust/' /etc/postgresql/9.1/main/pg_hba.conf
    sudo service postgresql restart
    django-admin syncdb --settings=devops.settings
    django-admin migrate devops --settings=devops.settings


Environment creation via Devops + Fuel_main
-------------------------------------------  
If you want to install a Fuel node + bootstrap for slave nodes, you will 
need to run the following commands::

    sudo apt-get install python-pip  postgresql-server-dev-all python-dev git
    sudo apt-get install python-libvirt libvirt-bin virt-manager postgresql
    sudo apt-get install qemu-utils qemu-kvm pm-utils python-virtualenv

Clone fuel-main ::

    git clone https://github.com/stackforge/fuel-main
    cd fuel-main/

Create pool 'default' ::

    sudo virsh pool-define-as --type=dir --name=default --target=
    /var/lib/libvirt/images
    sudo virsh pool-autostart default
    sudo virsh pool-start default
    sudo usermod $USER -a -G libvirtd,sudo
    sudo reboot

Check for KVM support (the output should be 'KVM acceleration can be used') ::

    kvm-ok

Should be 'Y'    ::

    cat /sys/module/kvm_intel/parameters/nested  
    cd fuel-main/
    virtualenv venv/fuelweb_test --system-site-packages
    . venv/fuelweb_test/bin/activate
    pip install -r fuelweb_test/requirements.txt
    sudo sed -ir 's/peer/trust/' /etc/postgresql/9.1/main/pg_hba.conf
    sudo service postgresql restart
    django-admin.py syncdb --settings devops.settings

Download fuel iso. Accessible here: http://software.mirantis.com/ 
(registration required)
Next, you need to define several variables for the future environment ::

    export ISO_PATH=<path_to_iso>
    export NODES_COUNT=<number_nodes>
    export ENV_NAME=<name_of_env>

Alternatively, you can edit this file ::

    fuelweb_test/settings.py

Start tests by running this command::

    sh "utils/jenkins/system_tests.sh" -t test -w $(pwd) -j "fuelweb_test" -i 
    "$ISO_PATH" -V $(pwd)/venv/fuelweb_test -o --group=setup

About how tests work, read the usage information ::

    sh "utils/jenkins/system_tests.sh" -h
