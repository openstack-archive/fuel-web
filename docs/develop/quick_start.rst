Fuel Development Quick-Start
============================

If you are interested in contributing to Fuel or modifying Fuel
for your own purposes, this short guide should get you pointed
to all the information you need to get started.

If you are new to contributing to OpenStack, read
through the “How To Contribute” page on the OpenStack wiki.
See: `How to contribute
<https://wiki.openstack.org/wiki/How_To_Contribute>`_.

For this walk-through, let’s use the example of modifying an
option to the “new environment wizard” in Fuel (example here:
`https://review.openstack.org/#/c/90687/1
<https://review.openstack.org/#/c/90687/1>`_).  This
enhancement required modification to three files in the fuel-web
repository::

    fuel-web/nailgun/static/i18n/translation.json
    fuel-web/nailgun/static/js/views/dialogs.js
    fuel-web/nailgun/static/templates/dialogs/create_cluster_wizard/storage.html

In order to add, test and commit the code necessary to
implement this feature, these steps were followed:

#. Create a Fuel development environment by following the
   instructions found here:
   :doc:`Fuel Development Environment </develop/env>`.

#. In your development environment, prepare your environment
   for Nailgun unit tests and Web UI tests by following
   the instructions found here:
   :doc:`Nailgun Dev Environment </develop/nailgun/development/env>`.
   Be sure to run the tests noted in each section to ensure
   your environment confirms to a known good baseline.

#. Branch your fuel-web checkout (see `Gerrit Workflow
   <https://wiki.openstack.org/wiki/GerritWorkflow>`_ for
   more information on the gerrit workflow)::

    cd fuel-web
    git fetch --all;git checkout -b vcenter-wizard-fix origin/master

#. Modify the necessary files (refer to :doc:`Fuel Architecture
   </develop/architecture>` to understand how the components
   of Fuel work together).

#. Test your Nailgun changes::

    cd fuel-web
    ./run_tests.sh --no-lint-ui --no-webui
    ./run_tests.sh --flake8
    ./run_tests.sh --lint-ui
    ./run_tests.sh --webui

#. You should also test Nailgun in fake UI mode by following
   the steps found here: :ref:`running-nailgun-in-fake-mode`

#. When all tests pass you should commit your code, which
   will subject it to further testing via Jenkins and Fuel CI.
   Be sure to include a good commit message, guidelines can be
   found here: `Git Commit Messages <https://wiki.openstack.org/wiki/GitCommitMessages>`_.::

    git commit -a
    git review

#. Frequently, the review process will suggest changes be
   made before your code can be merged.  In that case, make
   your changes locally, test the changes, and then re-submit
   for review by following these steps::

    git commit -a --amend
    git review

#. Now that your code has been committed, you should change
   your Fuel ISO makefile to point to your specific commit.
   As noted in the :doc:`Fuel Development documentation </develop/env>`,
   when you build a Fuel ISO it pulls down the additional
   repositories rather than using your local repos.  Even
   though you have a local clone of fuel-web holding the branch
   you just worked on, the build script will be pulling code
   from git for the sub-components (Nailgun, Astute, OSTF)
   based on the repository and commit specified in environment
   variables when calling “make iso”, or as found in config.mk.
   You will need to know the gerrit commit ID and patch number.
   For this example we are looking at
   https://review.openstack.org/#/c/90687/1
   with the gerrit ID 90687, patch 1. In this instance, you
   would build the ISO with::

    cd fuel-main
    NAILGUN_GERRIT_COMMIT=refs/changes/32/90687/1 make iso

#. Once your ISO build is complete, you can test it.  If
   you have access to hardware that can run the KVM
   hypervisor, you can follow the instructions found in the
   :doc:`Devops Guide </devops>` to create a robust testing
   environment.  Otherwise you can test the ISO with
   Virtualbox (the download link can be found at
   `https://software.mirantis.com/ <https://software.mirantis.com/>`_)

#. Once your code has been merged, you can return your local
   repo to the master branch so you can start fresh on your
   next commit by following these steps::

    cd fuel-web
    git remote update
    git checkout master
    git pull

