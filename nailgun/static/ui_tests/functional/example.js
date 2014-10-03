define([
    'intern!object',
    'intern/chai!assert'
], function (registerSuite, assert) {
    registerSuite({
        name: 'simple login screen test',

        beforeEach: function() {
            this.remote
                .get('http://127.0.0.1:' + (process.env.SERVER_PORT || 8000) + '/#logout')
                .then(function() {
                    assert.ok(true, 'logout reached');
                });
        },

        '#user login attempt': function () {
            var username = 'admin',
                password = 'admin';
            console.log('user', username, 'password', password, 'port', process.env.SERVER_PORT);
            return this.remote
                .get('http://127.0.0.1:' + (process.env.SERVER_PORT || 8000))
                .setFindTimeout(5000)
                .findByCssSelector('.login-box input[type=text]')
                    .click()
                    .type(username)
                    .end()
                .findByCssSelector('.login-box input[type=password]')
                    .click()
                    .type(password)
                    .end()
                .findByCssSelector('.login-btn')
                    .click()
                    .end()
                .getCurrentUrl()
                .then(function (url) {
                    assert.include(url, 'clusters');
                });
        },

        '#failed user login attempt': function() {
            var username = 'admin',
                password = 'x';
            return this.remote
                .get('http://127.0.0.1:' + (process.env.SERVER_PORT || 8000))
                .setFindTimeout(5000)
                .findByCssSelector('.login-box input[type=text]')
                    .click()
                    .type(username)
                    .end()
                .findByCssSelector('.login-box input[type=password]')
                    .click()
                    .type(password)
                    .end()
                .findByCssSelector('.login-btn')
                    .click()
                    .end()
                .getCurrentUrl()
                .then(function (url) {
                    assert.include(url, 'login');
                })
                .findByCssSelector('.login-error-message .text-error')
                    .getVisibleText()
                    .then(function(text) {
                        assert.strictEqual(text, 'Unable to log in');
                    })
                    .end();
        }
    });
});
