define([
    'intern!object',
    'intern/chai!assert',
    'expression',
    'models',
    'views/wizard'
], function (registerSuite, assert, Expression, models, Wizard) {
    'use strict';

    registerSuite({
        name: 'simple unit test',

        '#test models': function() {
            assert.ok(Expression('1 != 0').evaluate(), '1 != 0');

            assert.ok(new models.Cluster(), 'cluster model created');

            assert.ok(new Wizard.CreateClusterWizard({collection: new models.Cluster()}));
        }
    });

});
