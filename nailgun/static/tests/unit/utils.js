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
    'underscore',
    'utils',
    'i18n',
    'backbone'
], (_, utils, i18n, Backbone) => {
    'use strict';

    suite('Test utils', () => {
        test('Test getResponseText', () => {
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
        });

        test('Test comparison', () => {
            var compare = utils.compare;
            var model1 = new Backbone.Model({
                    string: 'bond2',
                    number: 1,
                    boolean: true,
                    booleanFlagWithNull: null
                });
            var model2 = new Backbone.Model({
                    string: 'bond10',
                    number: 10,
                    boolean: false,
                    booleanFlagWithNull: false
                });

            assert.equal(compare(model1, model2, {attr: 'string'}), -1, 'String comparison a<b');

            assert.equal(compare(model2, model1, {attr: 'string'}), 1, 'String comparison a>b');

            assert.equal(compare(model1, model1, {attr: 'string'}), 0, 'String comparison a=b');

            assert.ok(compare(model1, model2, {attr: 'number'}) < 0, 'Number comparison a<b');

            assert.ok(compare(model2, model1, {attr: 'number'}) > 0, 'Number comparison a>b');

            assert.equal(compare(model1, model1, {attr: 'number'}), 0, 'Number comparison a=b');

            assert.equal(compare(model1, model2, {attr: 'boolean'}), -1, 'Boolean comparison true and false');

            assert.equal(compare(model2, model1, {attr: 'boolean'}), 1, 'Boolean comparison false and true');

            assert.equal(compare(model1, model1, {attr: 'boolean'}), 0, 'Boolean comparison true and true');

            assert.equal(compare(model2, model2, {attr: 'boolean'}), 0, 'Boolean comparison false and false');

            assert.equal(compare(model1, model2, {attr: 'booleanFlagWithNull'}), 0, 'Comparison null and false');
        });

        test('Test highlightTestStep', () => {
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
        });

        test('Test getDefaultGatewayForCidr', () => {
            var getGateway = utils.getDefaultGatewayForCidr;

            assert.equal(getGateway('172.16.0.0/24'), '172.16.0.1', 'Getting default gateway for CIDR');
            assert.equal(getGateway('192.168.0.0/10'), '192.128.0.1', 'Getting default gateway for CIDR');
            assert.equal(getGateway('172.16.0.0/31'), '', 'No gateway returned for inappropriate CIDR (network is too small)');
            assert.equal(getGateway('172.16.0.0/'), '', 'No gateway returned for invalid CIDR');
        });

        test('Test getDefaultIPRangeForCidr', () => {
            var getRange = utils.getDefaultIPRangeForCidr;

            assert.deepEqual(getRange('172.16.0.0/24'), [['172.16.0.1', '172.16.0.254']], 'Getting default IP range for CIDR');
            assert.deepEqual(getRange('192.168.0.0/10', true), [['192.128.0.2', '192.191.255.254']], 'Gateway address excluded from default IP range');
            assert.deepEqual(getRange('172.16.0.0/31'), [['', '']], 'No IP range returned for inappropriate CIDR (network is too small)');
            assert.deepEqual(getRange('172.16.0.0/', true), [['', '']], 'No IP range returned for invalid CIDR');
        });

        test('Test validateIpCorrespondsToCIDR', () => {
            var validate = utils.validateIpCorrespondsToCIDR;

            assert.ok(validate('172.16.0.0/20', '172.16.0.2'), 'Check IP, that corresponds to CIDR');
            assert.ok(validate('172.16.0.5/24', '172.16.0.2'), 'Check IP, that corresponds to CIDR');
            assert.notOk(validate('172.16.0.0/20', '172.16.15.255'), 'Check broadcast address');
            assert.notOk(validate('172.16.0.0/20', '172.16.0.0'), 'Check network address');
            assert.notOk(validate('192.168.0.0/10', '192.231.255.254'), 'Check IP, that does not correspond to CIDR');
        });
    });
});
