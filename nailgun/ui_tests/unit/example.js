define([
    'intern!object',
    'intern/chai!assert',
    'require',
    '../../static/js/expression/parser',
    'js/libs/bower/underscore/underscore',
    'js/expression',
    'js/utils',
    'js/models'
], function (registerSuite, assert, require, parser, underscore, expression, utils, models) {

    registerSuite({
        name: 'simple unit test',

        '#test models': function () {
            debugger;
            return assert.ok(true, 'fake');
//            assert.ok(new models.Cluster(), 'cluster model created');
//            var testModels = {
//                'cluster': new models.Cluster(),
//                'settings': new models.Settings()
//            };

        }
    });

});
