Fuel Development Environment on Live Masternode
===============================================

If you need to deploy your own developer version of FUEL on live
masternode, you will need to use helper script from
fuel-web/fuel_development/manage.py. Helper script configures development
environment on masternode, deploys code or restores production
environment on masternode.

Help information about manage.py can be found by running it
with '-h' parameter.

Nailgun Developer Version on Live Masternode
--------------------------------------------

Configure Nailgun development environment by following the
instructions found here:
:doc:`Nailgun Dev Environment </develop/nailgun/development/env>`

In your local fuel-web repository run:
::

    workon fuel
    cd fuel_development
    python manage.py -m MASTER.NODE.ADDRESS nailgun deploy


Nailgun source code will be deployed, all required packages
will be installed, required services will be reconfigured and restarted.
After that developer version of Nailgun can be accessed.

For deploying Nailgun source code only without reconfiguring services run:
::

    python manage.py -m MASTER.NODE.ADDRESS nailgun deploy --onlysync

For restoring production version of Nailgun run:
::

    python manage.py -m MASTER.NODE.ADDRESS nailgun revert


