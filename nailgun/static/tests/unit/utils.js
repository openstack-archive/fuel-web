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
        },
        'Test highlightTestStep': function() {
            var text;
            var highlight = utils.highlightTestStep;

            text = '1. Step 1\n2. Step 2\n3. Step 3';
            assert.equal(
                highlight(text, 1),
                '<b>1. Step 1</b>\n2. Step 2\n3. Step 3',
                'Highlighting first step in simple text works'
            );
            assert.equal(
                highlight(text, 2),
                '1. Step 1\n<b>2. Step 2</b>\n3. Step 3',
                'Highlighting middle step in simple text works'
            );
            assert.equal(
                highlight(text, 3),
                '1. Step 1\n2. Step 2\n<b>3. Step 3</b>',
                'Highlighting last step in simple text works'
            );

            text = '1. Step 1\n1-1\n1-2\n2. Step 2\n2-1\n2-2\n3. Step 3\n3-1\n3-2';
            assert.equal(
                highlight(text, 1),
                '<b>1. Step 1\n1-1\n1-2</b>\n2. Step 2\n2-1\n2-2\n3. Step 3\n3-1\n3-2',
                'Highlighting first step in multiline text works'
            );
            assert.equal(
                highlight(text, 2),
                '1. Step 1\n1-1\n1-2\n<b>2. Step 2\n2-1\n2-2</b>\n3. Step 3\n3-1\n3-2',
                'Highlighting middle step in multiline text works'
            );
            assert.equal(
                highlight(text, 3),
                '1. Step 1\n1-1\n1-2\n2. Step 2\n2-1\n2-2\n<b>3. Step 3\n3-1\n3-2</b>',
                'Highlighting last step in multiline text works'
            );

            text = ' \n \n 1. Step 1 \n \n';
            assert.equal(
                highlight(text, 1),
                ' \n \n <b>1. Step 1 \n \n</b>',
                'Highlighting steps in padded text works'
            );

            text = '1. Step 1\n3. Step 3';
            assert.equal(
                highlight(text, 2),
                text,
                'Attempting to highlight non-existent step keeps text as it is'
            );
        }
    });
});
