define([
    'intern!object',
    'intern/chai!assert',
    'expression'
], function(registerSuite, assert, Expression) {
    'use strict';

    registerSuite({
        name: 'Expression test',
        '#test expression': function() {
            alert(1);
            assert.ok(Expression('1 != 0').evaluate(), '1 != 0');
        }
    });
});
