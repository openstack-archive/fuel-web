define([
    'intern!object',
    'intern/chai!assert',
    'expression'
], function (registerSuite, assert, Expression) {
    'use strict';

    registerSuite({
        name: 'simple unit test',

        '#test models': function() {
            assert.ok(Expression('1 != 0').evaluate(), '1 != 0');
        }
    });

});
