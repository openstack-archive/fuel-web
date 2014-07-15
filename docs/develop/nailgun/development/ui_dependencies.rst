Managing UI Dependencies
========================

The UI has 2 types of dependencies: managed by NPM (run on node.js) and managed
by Bower (run in browser).

Managing NPM Packages
---------------------

NPM packages such as grunt_, bower_ and others are used in a development
environment only. Used NPM packages are listed in *devDependencies* section of
a package.json file. To install all required packages, run::

    npm install

To use grunt_ you also need to install grunt-cli package globally::

    sudo npm install -g grunt-cli

To add a new package, it is not enough just to add a new entry to a
package.json file because npm-shrinkwrap_ is used to lock down package
versions. First you need to install clingwrap package globally:

    sudo npm install -g clingwrap

Then you need to remove existing npm-shrinkwrap.json file::

    rm npm-shrinkwrap.json

Then make required changes to a package.json file and run::

    rm -rf node_modules
    npm install

to remove old packages and install new ones. Then regenerate
npm-shrinkwrap.json by running::

    npm shrinkwrap
    clingwrap npmbegone


Managing Bower Packages
-----------------------

Bower_ is used to download libraries that run in browser. To add a new package
just add an entry to dependencies section of a bower.json file and run::

    grunt bower

to download it. The new package will be placed to nailgun/static/js/libs/bower/
directory. If the package contains more than one JS file, to avoid their
appearance in the final UI build you need to add a new entry to exportsOverride
section with a path to the needed file.

If a library does not exist in the bower repository, it should be placed to
nailgun/static/js/libs/custom/ directory.

.. _grunt: http://gruntjs.com/
.. _bower: http://bower.io/
.. _npm-shrinkwrap: https://www.npmjs.org/doc/cli/npm-shrinkwrap.html