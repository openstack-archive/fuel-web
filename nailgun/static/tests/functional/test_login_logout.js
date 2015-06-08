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
    'intern/chai!assert',
    'tests/functional/pages/login',
    'tests/functional/pages/common'
], function(registerSuite, assert, LoginPage, Common) {
    'use strict';

    registerSuite(function() {
        var loginPage, common;
        return {
            name: 'Login page',
            setup: function() {
                loginPage = new LoginPage(this.remote);
                common = new Common(this.remote);
            },
            beforeEach: function() {
                this.remote
                    .then(function() {
                        return common.getOut();
                    });
            },
            'Login with incorrect credentials': function() {
                return this.remote
                    .then(function() {
                        return loginPage.login('login', '*****');
                    })
                    .findByCssSelector('div.login-error-auth.login-error-message p')
                    .isDisplayed()
                    .then(function(errorShown) {
                        assert.ok(errorShown, 'Error message is expected to be displayed');
                    });

            },
            'Login with proper credentials': function() {
                return this.remote
                    .then(function() {
                        return loginPage.login();
                    })
                    .waitForDeletedByClassName('login-btn');
            }
        };
    });
});
