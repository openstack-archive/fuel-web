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
define(['jquery', 'underscore', 'js-cookie'], ($, _, Cookies) => {
    'use strict';

    class KeystoneClient {
        constructor(url, options) {
            this.DEFAULT_PASSWORD = 'admin';
            _.extend(this, {
                url: url,
                cacheTokenFor: 10 * 60 * 1000
            }, options);
        }

        authenticate(username, password, options = {}) {
            if (this.tokenUpdateRequest) return this.tokenUpdateRequest;

            if (!options.force && this.tokenUpdateTime && (this.cacheTokenFor > (new Date() - this.tokenUpdateTime))) {
                return $.Deferred().resolve();
            }
            let data = {auth: {}};
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
            }).then((result, state, deferred) => {
                try {
                    this.userId = result.access.user.id;
                    this.token = result.access.token.id;
                    this.tokenUpdateTime = new Date();

                    Cookies.set('token', result.access.token.id);

                    return deferred;
                } catch (e) {
                    return $.Deferred().reject();
                }
            })
            .fail(() => delete this.tokenUpdateTime)
            .always(() => delete this.tokenUpdateRequest);

            return this.tokenUpdateRequest;
        }

        changePassword(currentPassword, newPassword) {
            let data = {
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
            }).then((result, state, deferred) => {
                try {
                    this.token = result.access.token.id;
                    this.tokenUpdateTime = new Date();

                    Cookies.set('token', result.access.token.id);

                    return deferred;
                } catch (e) {
                    return $.Deferred().reject();
                }
            });
        }

        deauthenticate() {
            let token = this.token;

            if (this.tokenUpdateRequest) return this.tokenUpdateRequest;
            if (!token) return $.Deferred().reject();

            delete this.userId;
            delete this.token;
            delete this.tokenUpdateTime;

            Cookies.remove('token');

            this.tokenRemoveRequest = $.ajax(this.url + '/v2.0/tokens/' + token, {
                type: 'DELETE',
                dataType: 'json',
                contentType: 'application/json',
                headers: {'X-Auth-Token': token}
            })
            .always(() => delete this.tokenRemoveRequest);

            return this.tokenRemoveRequest;
        }
    }

    return KeystoneClient;
});
