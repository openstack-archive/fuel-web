Managing UI Dependencies
========================

The dependencies of Fuel UI are managed by NPM_.

Used NPM packages are listed in *dependencies* and *devDependencies* sections
of a package.json file. To install all required packages, run::

    npm install

To use gulp_ you also need to install the gulp package globally::

    sudo npm install -g gulp

To add a new package, it is not enough just to add a new entry to a
package.json file because npm-shrinkwrap_ is used to lock down package
versions. First you need to install the clingwrap package globally:

    sudo npm install -g clingwrap

Then install required package::

    npm install --save some-package

Then run::

    clingwrap some-package

to update npm-shrinkwrap.json.

Alternatively, you can completely regenerate npm-shrinkwrap.json by running::

    rm npm-shrinkwrap.json
    rm -rf node_modules
    npm install
    npm shrinkwrap --dev
    clingwrap npmbegone

.. _npm: https://www.npmjs.org/
.. _gulp: http://gulpjs.com/
.. _npm-shrinkwrap: https://www.npmjs.org/doc/cli/npm-shrinkwrap.html
