define([
    'intern!object',
    'intern/chai!assert',
    'require',
    'models',
    'views/wizard'
], function (registerSuite, assert, require, models, wizard) {

    registerSuite({
        name: 'simple unit test',

        '#test models': function () {
            assert.ok(new wizard.CreateClusterWizard({collection: new models.Cluster()}));
        }
    });

});
