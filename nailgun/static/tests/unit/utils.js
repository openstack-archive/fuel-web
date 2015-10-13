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
    'intern!object',
    'intern/chai!assert',
    'underscore',
    'utils',
    'i18n'
], function(registerSuite, assert, _, utils, i18n) {
    'use strict';

    registerSuite({
        name: 'Test utils',
        'Test getResponseText': function() {
            var response;
            var getResponseText = utils.getResponseText;
            var serverErrorMessage = i18n('dialog.error_dialog.server_error');
            var serverUnavailableMessage = i18n('dialog.error_dialog.server_unavailable');

            response = {status: 500, responseText: 'Server error occured'};
            assert.equal(getResponseText(response), serverErrorMessage, 'HTTP 500 is treated as a server error');

            response = {status: 502, responseText: 'Bad gateway'};
            assert.equal(getResponseText(response), serverUnavailableMessage, 'HTTP 502 is treated as server unavailability');

            response = {status: 0, responseText: 'error'};
            assert.equal(getResponseText(response), serverUnavailableMessage, 'XHR object with no status is treated as server unavailability');

            response = {status: 400, responseText: 'Bad request'};
            assert.equal(getResponseText(response), serverErrorMessage, 'HTTP 400 with plain text response is treated as a server error');

            response = {status: 400, responseText: JSON.stringify({message: '123'})};
            assert.equal(getResponseText(response), '123', 'HTTP 400 with JSON response is treated correctly');
        }
    });
});
