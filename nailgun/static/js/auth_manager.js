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
define(['jquery', 'underscore'], function($, _) {
    'use strict';

    function AuthManager(options) {
        _.extend(this, {
            cacheTokenFor: 10 * 60 * 1000   // 10 minutes
        }, options);
    }

    _.extend(AuthManager.prototype, {
        login: function(options) {
            options = options || {};

            this.loginRequest = $.ajax('/api/auth/login', {
                type: 'POST',
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify(_.pick(this, ['username', 'password']))
            }).then(_.bind(function(result, state, deferred) {
                try {
                    this.token = result.auth_token;
                    //this.userId = result.access.user.id;
                    this.tokenUpdateTime = new Date();
                    return deferred;
                } catch(e) {
                    return $.Deferred().reject();
                }
            }, this)).fail(_.bind(function() {
                delete this.tokenUpdateTime;
            }, this)).always(_.bind(function() {
                delete this.loginRequest;
            }, this));

            return this.loginRequest;
        },

        logout: function(options) {
            options = options || {};

            this.logoutRequest = $.ajax('/api/auth/logout', {
                type: 'POST',
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify({auth_token: this.token})
            }).always(_.bind(function(result, state, deferred) {
                delete this.userId;
                delete this.token;
                delete this.tokenUpdateTime;
                delete this.logoutRequest;
            }, this));

            return this.logoutRequest;
        },

        changePassword: function(currentPassword, newPassword) {
        }
    });

    return AuthManager;
});
