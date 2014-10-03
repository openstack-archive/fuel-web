define([
    'intern!object',
    'intern/chai!assert',
    'require',
    'intern/dojo/node!leadfoot/helpers/pollUntil'
], function (registerSuite, assert, require, pollUntil) {
    registerSuite({
        name: 'simple login screen test',

        '#user login attempt': function () {
            var credentials = 'admin';
            return this.remote
                .get('http://127.0.0.1:8000/')
                .setFindTimeout(10000)
                .findByCssSelector('.login-box input[type=text]')
                    .click()
                    .type(credentials)
                    .end()
                .findByCssSelector('.login-box input[type=password]')
                    .click()
                    .type(credentials)
                    .end()
                .findByCssSelector('.login-btn')
                    .click()
                    .end()
                .setFindTimeout(10000)
                .getCurrentUrl()
                .then(function (url) {
                    assert.include(url, 'clusters');
                });
        }
    });
});
