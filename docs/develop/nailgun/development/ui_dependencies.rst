Managing UI Dependencies
========================

The UI has 2 types of dependencies: managed by NPM_ (run on node.js) and
managed by Bower_ (run in browser).

Managing NPM Packages
---------------------

NPM packages such as grunt_, bower_ and others are used in a development
environment only. Used NPM packages are listed in the *devDependencies* section
of a package.json file. To install all required packages, run::

    npm install

To use grunt_ you also need to install the grunt-cli package globally::

    sudo npm install -g grunt-cli

To add a new package, it is not enough just to add a new entry to a
package.json file because npm-shrinkwrap_ is used to lock down package
versions. First you need to install the clingwrap package globally:

    sudo npm install -g clingwrap

Then you need to remove the existing npm-shrinkwrap.json file::

    rm npm-shrinkwrap.json

Then make required changes to a package.json file and run::

    npm install

to remove old packages and install new ones. Then regenerate
npm-shrinkwrap.json by running::

    npm shrinkwrap --dev
    clingwrap npmbegone


Managing Bower Packages
-----------------------

Bower_ is used to download libraries that run in browser. To add a new package,
just add an entry to dependencies section of a bower.json file and run::

    grunt bower

to download it. The new package will be placed in the
nailgun/static/js/libs/bower/ directory. If the package contains more than one
JS file, you must add a new entry to the exportsOverride section with a path to
the appropriate file, in order to prevent unwanted JS files from appearing in
the final UI build.

If a library does not exist in the bower repository, it should be placed in the
nailgun/static/js/libs/custom/ directory.

.. _npm: https://www.npmjs.org/
.. _bower: http://bower.io/
.. _grunt: http://gruntjs.com/
.. _npm-shrinkwrap: https://www.npmjs.org/doc/cli/npm-shrinkwrap.html