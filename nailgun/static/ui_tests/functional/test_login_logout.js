/*
 * Copyright 2014 Mirantis, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may
 * not use this file except in compliance with the License. You may obtain
 * a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations
 * under the License.
 **/

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
                .findByCssSelector('.login-box input[name=username]')
                    .click()
                    .type(username)
                    .end()
                .findByCssSelector('.login-box input[name=password]')
                    .click()
                    .type(password)
                    .end()
                .execute(function() {
                    return window.app.keystoneClient.token;
                })
                .then(function(token) {
                    assert(!token, 'User token not set initially');
                })
                .findByCssSelector('.login-btn')
                    .click()
                    .end()
                .waitForDeletedByClassName('login-box')
                .getCurrentUrl()
                    .then(function (url) {
                        assert.include(url, 'welcome', 'Redirected to welcome screen after login');
                    })
                .findByCssSelector('.welcome-button-box button')
                    .click()
                    .end()
                .waitForDeletedByClassName('welcome-page')
                .getCurrentUrl()
                .then(function (url) {
                    assert.include(url, 'clusters', 'Redirected to clusters view after welcome screen');
                })
                .findByCssSelector('a[href="#logout"]')
                    .end()
                .findByCssSelector('span.username')
                    .getVisibleText()
                    .then(function(text) {
                        assert.equal(text, username, 'Username present');
                    })
                    .end()
                .execute(function() {
                    return window.app.keystoneClient.token;
                })
                    .then(function(token) {
                        assert(!!token, 'Token is set after login');
                    });
        },

        '#failed user login attempt': function() {
            var username = 'admin',
                password = 'x';
            return this.remote
                .get('http://127.0.0.1:' + (process.env.SERVER_PORT || 8000))
                .setFindTimeout(5000)
                .findByCssSelector('.login-box input[name=username]')
                    .click()
                    .type(username)
                    .end()
                .findByCssSelector('.login-box input[name=password]')
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
