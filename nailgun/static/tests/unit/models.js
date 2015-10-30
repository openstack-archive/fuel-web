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
    'models'
], function(registerSuite, assert, models) {
    'use strict';

    registerSuite({
        name: 'Test models',
        'Test Task model': function() {
            var task = new models.Task();

            // test extendStatuses method
            var filters, result;

            filters = {status: []};
            result = ['ready', 'error', 'running', 'pending'];
            assert.equal(task.extendStatuses(filters), result, 'All task statuses are acceptable if "status" filter not specified');

            filters = {status: 'ready'};
            result = ['ready'];
            assert.equal(task.extendStatuses(filters), result, '"status" filter can have string as a value');

            filters = {status: ['ready', 'running']};
            result = ['ready', 'running'];
            assert.equal(task.extendStatuses(filters), result, '"status" filter can have list of strings as a value');

            filters = {status: ['ready'], active: true};
            result = [];
            assert.equal(task.extendStatuses(filters), result, '"status" and "active" filters are not intersected');

            filters = {status: ['running'], active: true};
            result = ['running'];
            assert.equal(task.extendStatuses(filters), result, '"status" and "active" filters have intersection');

            filters = {status: ['running'], active: false};
            result = [];
            assert.equal(task.extendStatuses(filters), result, '"status" and "active" filters are not intersected');

            filters = {status: ['ready', 'running'], active: false};
            result = ['ready'];
            assert.equal(task.extendStatuses(filters), result, '"status" and "active" filters have intersection');

            filters = {active: true};
            result = ['running', 'pending'];
            assert.equal(task.extendStatuses(filters), result, 'True value of "active" filter parsed correctly');

            filters = {active: false};
            result = ['ready', 'error'];
            assert.equal(task.extendStatuses(filters), result, 'False value of \'active\' filter parsed correctly');

            //TODO(jkirnosova): test extendGroups method
        }
    });
});
