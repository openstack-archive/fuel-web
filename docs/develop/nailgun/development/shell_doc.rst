Interacting with Nailgun using Shell
====================================

.. contents:: :local:


Launching shell
---------------

Development shell for Nailgun can only be accessed inside its virtualenv,
which can be activated by launching the following command::

	source /opt/nailgun/bin/activate

After that, the shell is accessible through this command::

	python /opt/nailgun/bin/manage.py shell

Its appearance depends on availability of ipython on current system. This
package is not available by default on the master node but you can use the
command above to run a default Python shell inside the Nailgun environment::

	Python 2.7.3 (default, Feb 27 2014, 19:58:35)
	[GCC 4.6.3] on linux2
	Type "help", "copyright", "credits" or "license" for more information.
	(InteractiveConsole)
	>>>


Interaction
-----------

There are two ways user may interact with Nailgun object instances
through shell:

	* Using Nailgun objects abstraction
	* Using raw SQLAlchemy queries

**IMPORTANT NOTE:** Second way (which is equal to straightforward modifying
objects in DB) should only be used if nothing else works.

.. _shell-objects:

Objects approach
****************

Importing objects may look like this::

	>>> from nailgun import objects
	>>> objects.Release
	<class 'nailgun.objects.release.Release'>
	>>> objects.Cluster
	<class 'nailgun.objects.cluster.Cluster'>
	>>> objects.Node
	<class 'nailgun.objects.node.Node'>

These are common abstractions around basic items Nailgun is dealing with.
The reference on how to work with them can be found here:
:ref:`objects-reference`.

These objects allow user to interact with items in DB on higher level, which
includes all necessary business logic which is not executed then values in DB
are changed by hands. For working examples continue to :ref:`shell-faq`.

SQLAlchemy approach
*******************

Using raw SQLAlchemy models and queries allows user to modify objects through
ORM, almost the same way it can be done through SQL CLI.

First, you need to get a DB session and import models::

	>>> from nailgun.db import db
	>>> from nailgun.db.sqlalchemy import models
	>>> models.Release
	<class 'nailgun.db.sqlalchemy.models.release.Release'>
	>>> models.Cluster
	<class 'nailgun.db.sqlalchemy.models.cluster.Cluster'>
	>>> models.Node
	<class 'nailgun.db.sqlalchemy.models.node.Node'>

and then get necessary instances from DB, modify them and commit current
transaction::

	>>> node = db().query(models.Node).get(1)  # getting object by ID
	>>> node
	<nailgun.db.sqlalchemy.models.node.Node object at 0x3451790>
	>>> node.status = 'error'
	>>> db().commit()

You may refer to `SQLAlchemy documentation <http://docs.sqlalchemy.org/en/rel_0_7/orm/query.html>`_
to find some more info on how to do queries.

.. _shell-faq:

Frequently Asked Questions
--------------------------

As a first step in any case objects should be imported as is
described here: :ref:`shell-objects`.

**Q:** How can I change status for particular node?

**A:** Just retrieve node by its ID and update it::

	>>> node = objects.Node.get_by_uid(1)
	>>> objects.Node.update(node, {"status": "ready"})
	>>> objects.Node.save(node)


**Q:** How can I remove node from cluster by hands?

**A:** Get node by ID and call its method::

	>>> node = objects.Node.get_by_uid(1)
	>>> objects.Node.remove_from_cluster(node)
	>>> objects.Node.save(node)

