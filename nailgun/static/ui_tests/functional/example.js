define([
    'intern!object',
    'intern/chai!assert',
    'require'
], function (registerSuite, assert, require) {
    registerSuite({
        name: 'simple login screen test',

        '#user login attempt': function () {
            var credentials = 'admin';
            return this.remote
                .get('http://127.0.0.1:' + (process.env.SERVER_PORT || 8000))
                .setFindTimeout(5000)
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
                .getCurrentUrl()
                .then(function (url) {
                    assert.include(url, 'clusters');
                });
        }
    });
});
