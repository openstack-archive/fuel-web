define([
    'intern!object',
    'intern/chai!assert',
    'models',
    'views/wizard'
], function (registerSuite, assert, models, wizard) {
    'use strict';

    registerSuite({
        name: 'simple unit test',

        '#test models': function() {
            assert.ok(true, 'fake');
            assert.ok(new models.Cluster(), 'cluster model created');
//            var testModels = {
//                'cluster': new models.Cluster(),
//                'settings': new models.Settings()
//            };

            assert.ok(new wizard.CreateClusterWizard({collection: new models.Cluster()}));
        }
    });

});
