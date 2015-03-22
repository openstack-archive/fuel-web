define([
    'intern!object',
    'intern/chai!assert',
    'expression'
], function(registerSuite, assert, Expression) {
    'use strict';

    registerSuite({
        name: 'Expression test',
        '#test expression': function() {
            assert.ok(Expression('0 != 0').evaluate(), '1 != 0');
        }
    });
});
