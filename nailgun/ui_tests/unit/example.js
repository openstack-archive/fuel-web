define([
    'intern!object',
    'intern/chai!assert',
    'require',
    'models'
], function (registerSuite, assert, require, models) {

    registerSuite({
        name: 'simple unit test',

        '#test models': function () {
            assert.ok(true, 'fake');
            assert.ok(new models.Cluster(), 'cluster model created');
//            var testModels = {
//                'cluster': new models.Cluster(),
//                'settings': new models.Settings()
//            };

        }
    });

});
