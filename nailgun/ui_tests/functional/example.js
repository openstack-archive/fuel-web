define([
    'intern!object',
    'intern/chai!assert',
    'require'
], function (registerSuite, assert, require) {
    registerSuite({
        name: 'index',
        test: function () {
            this.remote
                .get('http://127.0.0.1:5544/')
                .setFindTimeout(5000)
                .findByCssSelector('.login-box input[type=text]')
                    .click()
                    .type('admin')
                    .end()
                .then(function() {
                    assert.strictEqual(1, 2);
                });
        }
    });
});
