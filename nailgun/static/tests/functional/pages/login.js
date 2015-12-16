/*
 * Copyright 2015 Mirantis, Inc.
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
    '../../helpers'
], function(Helpers) {
    'use strict';

    function LoginPage(remote) {
        this.remote = remote;
    }

    LoginPage.prototype = {
        constructor: LoginPage,
        login: function(username, password) {
            username = username || Helpers.username;
            password = password || Helpers.password;
            var self = this;

            return this.remote
                .setFindTimeout(500)
                .setWindowSize(1280, 1024)
                .getCurrentUrl()
                .then(function(url) {
                    if (url !== Helpers.serverUrl + '/#login') {
                        return self.logout();
                    }
                })
                .setInputValue('[name=username]', username)
                .setInputValue('[name=password]', password)
                .clickByCssSelector('.login-btn');
        },
        logout: function() {
            return this.remote
                .getCurrentUrl()
                .then(function(url) {
                    if (url.indexOf(Helpers.serverUrl) !== 0) {
                        return this.parent
                            .get(Helpers.serverUrl + '/#logout')
                            .findByClassName('login-btn')
                            .then(function() {
                                return true;
                            });
                    }
                })
                .clickByCssSelector('li.user-icon')
                .clickByCssSelector('.user-popover button.btn-logout')
                .findByCssSelector('.login-btn')
                .then(
                    function() {return true;},
                    function() {return true;}
                );
        }
    };
    return LoginPage;
});
