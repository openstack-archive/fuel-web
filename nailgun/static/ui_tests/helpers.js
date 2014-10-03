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
], function(
) {
    'use strict';

    var serverHost = '127.0.0.1',
        serverPort = process.env.SERVER_PORT || 5544,
        serverUrl = 'http://' + serverHost + ':' + serverPort;

    var authenticate = function(username, password) {

        username = username || 'admin';
        password = password || 'admin';

        console.log('user', username, 'password', password, 'port', process.env.SERVER_PORT);

        return function() {
            var findTimeout;

            //debugger;

            this.getFindTimeout()
                .then(function(timeout) {
                    findTimeout = timeout;
                })
                .setFindTimeout(10000)
                .then(waitForWindowApp)
                .get(serverUrl + '/#login')
                .findByCssSelector('.login-box input[name=username]')
                    .then(function() {
                        console.log('LOGGING IN');

                        this.findByCssSelector('.login-box input[name=username]')
                                .click()
                                .type(username)
                                .end()
                            .findByCssSelector('.login-box input[name=password]')
                                .click()
                                .type(password)
                                .end()
                            .then(function() {
                                debugger;
                            })
                            .findByCssSelector('.login-btn')
                                .click()
                                .end()
                            .then(function() {
                                console.log('BUTTON CLICKED');
                            })
                            .waitForDeletedByClassName('login-box');
                    },
                    function() {
                        // logged in already
                        return;
                    })
                    .end()
                .setFindTimeout(findTimeout);
        };  // return function
    };  // authenticate

    var skipWelcomeScreen = function() {
        this.get(serverUrl)
            .then(waitForWindowApp)
            .execute(function() {
                window.app.settings.set('user_choice_saved', {type: 'hidden', value: true});
            })
            .then(function() {});
    };   // skipWelcomeScreen

    var waitForWindowApp = function() {
        var findTimeout,
            executeAsyncTimeout;

        this.getFindTimeout()
            .then(function(timeout) {
                findTimeout = timeout;
            })
            .setFindTimeout(10000)
            .getExecuteAsyncTimeout()
            .then(function(timeout) {
                executeAsyncTimeout = timeout;
            })
            .setExecuteAsyncTimeout(10000)

            .get(serverUrl)
            .executeAsync(function(callback) {
                var isAppPresent = function() {
                    if (!window.app || !window.app.keystoneClient) {
                        setTimeout(isAppPresent, 100);
                    } else {
                        callback();
                    }
                };

                isAppPresent();
            }).then(function() {})

            //.setExecuteAsyncTimeout(executeAsyncTimeout)
            //.setFindTimeout(findTimeout);
    };  // waitForWindowApp

    return {
        authenticate: authenticate,
        serverUrl: serverUrl,
        skipWelcomeScreen: skipWelcomeScreen,
        waitForWindowApp: waitForWindowApp
    };
});
