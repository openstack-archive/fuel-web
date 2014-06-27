Fuel Development Environment on Live Master Node
================================================

If you need to deploy your own developer version of FUEL on live
Master Node, you will need to use the helper script,
fuel-web/fuel_development/manage.py. The helper script configures development
environment on masternode, deploys code or restores the production
environment.

Help information about manage.py can be found by running it
with the 'h' parameter.

Nailgun Developer Version on Live Master Node
---------------------------------------------

Configure the Nailgun development environment by following the
instructions:
:doc:`Nailgun Dev Environment </develop/nailgun/development/env>`

In your local fuel-web repository run:
::

    workon fuel
    cd fuel_development
    python manage.py -m MASTER.NODE.ADDRESS nailgun deploy


Nailgun source code will be deployed, all required packages
will be installed, required services will be reconfigured and restarted.
After that, developer version of Nailgun can be accessed.

For deploying Nailgun source code only without reconfiguring services run:
::

    python manage.py -m MASTER.NODE.ADDRESS nailgun deploy --synconly

For restoring production version of Nailgun run:
::

    python manage.py -m MASTER.NODE.ADDRESS nailgun revert


If you need to add a new python package or use another version of
the python package, make appropriate changes in the nailgun/requirements.txt
file and run:
::

    python manage.py -m MASTER.NODE.ADDRESS nailgun deploy
