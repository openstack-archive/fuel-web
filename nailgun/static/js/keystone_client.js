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
define(['jquery', 'underscore', 'jquery-cookie'], function($, _) {
    'use strict';

    function KeystoneClient(url, options) {
        _.extend(this, {
            url: url,
            cacheTokenFor: 10 * 60 * 1000
        }, options);
    }

    _.extend(KeystoneClient.prototype, {
        authenticate: function(username, password, options) {
            options = options || {};
            if (this.tokenUpdateRequest) {
                return this.tokenUpdateRequest;
            }
            if (!options.force && this.tokenUpdateTime && (this.cacheTokenFor > (new Date() - this.tokenUpdateTime))) {
                return $.Deferred().resolve();
            }
            var data = {auth: {}};
            if (username && password) {
                data.auth.passwordCredentials = {
                    username: username,
                    password: password
                };
            } else if (this.token) {
                data.auth.token = {id: this.token};
            } else {
                return $.Deferred().reject();
            }
            if (this.tenant) {
                data.auth.tenantName = this.tenant;
            }
            this.tokenUpdateRequest = $.ajax(this.url + '/v2.0/tokens', {
                type: 'POST',
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify(data)
            }).then(_.bind(function(result, state, deferred) {
                try {
                    this.userId = result.access.user.id;
                    this.token = result.access.token.id;
                    this.tokenUpdateTime = new Date();

                    $.cookie('token', result.access.token.id);

                    return deferred;
                } catch(e) {
                    return $.Deferred().reject();
                }
            }, this)).fail(_.bind(function() {
                delete this.tokenUpdateTime;
            }, this)).always(_.bind(function() {
                delete this.tokenUpdateRequest;
            }, this));
            return this.tokenUpdateRequest;
        },
        changePassword: function(currentPassword, newPassword) {
            var data = {
                user: {
                    password: newPassword,
                    original_password: currentPassword
                }
            };
            return $.ajax(this.url + '/v2.0/OS-KSCRUD/users/' + this.userId, {
                type: 'PATCH',
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify(data),
                headers: {'X-Auth-Token': this.token}
            }).then(_.bind(function(result, state, deferred) {
                try {
                    this.token = result.access.token.id;
                    this.tokenUpdateTime = new Date();

                    $.cookie('token', result.access.token.id);

                    return deferred;
                } catch(e) {
                    return $.Deferred().reject();
                }
            }, this));
        },
        deauthenticate: function() {
            var token = this.token;

            if (this.tokenRemoveRequest) {
                return this.tokenRemoveRequest;
            }
            if (!this.token) {
                return $.Deferred().reject();
            }

            delete this.userId;
            delete this.token;
            delete this.tokenUpdateTime;

            $.removeCookie('token');

            this.tokenRemoveRequest = $.ajax(this.url + '/v2.0/tokens/' + token, {
                type: 'DELETE',
                dataType: 'json',
                contentType: 'application/json',
                headers: {'X-Auth-Token': token}
            }).always(_.bind(function() {
                delete this.tokenRemoveRequest;
            }, this));

            return this.tokenRemoveRequest;
        }
    });

    return KeystoneClient;
});
