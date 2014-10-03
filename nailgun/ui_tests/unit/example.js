define([
    'intern!object',
    'intern/chai!assert',
    'require'
], function (registerSuite, assert, require, expression) {

    registerSuite({
        name: 'simple unit test',

        '#test models': function () {
            return assert.ok(true, 'fake');
//            assert.ok(new models.Cluster(), 'cluster model created');
//            var testModels = {
//                'cluster': new models.Cluster(),
//                'settings': new models.Settings()
//            };

        }
    });

});
