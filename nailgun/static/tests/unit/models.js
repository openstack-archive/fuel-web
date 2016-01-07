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
/*eslint object-shorthand: 0*/
define([
    'underscore',
    'models'
], function(_, models) {
    'use strict';

    suite('Test models', function() {
        suite('Test Task model', function() {
            test('Test extendStatuses method', function() {
                var task = new models.Task(),
                    filters, result;

                filters = {status: []};
                result = ['running', 'pending', 'ready', 'error'];
                assert.deepEqual(task.extendStatuses(filters), result, 'All task statuses are acceptable if "status" filter not specified');

                filters = {status: 'ready'};
                result = ['ready'];
                assert.deepEqual(task.extendStatuses(filters), result, '"status" filter can have string as a value');

                filters = {status: ['ready', 'running']};
                result = ['ready', 'running'];
                assert.deepEqual(task.extendStatuses(filters), result, '"status" filter can have list of strings as a value');

                filters = {status: ['ready'], active: true};
                result = [];
                assert.deepEqual(task.extendStatuses(filters), result, '"status" and "active" filters are not intersected');

                filters = {status: ['running'], active: true};
                result = ['running'];
                assert.deepEqual(task.extendStatuses(filters), result, '"status" and "active" filters have intersection');

                filters = {status: ['running'], active: false};
                result = [];
                assert.deepEqual(task.extendStatuses(filters), result, '"status" and "active" filters are not intersected');

                filters = {status: ['ready', 'running'], active: false};
                result = ['ready'];
                assert.deepEqual(task.extendStatuses(filters), result, '"status" and "active" filters have intersection');

                filters = {active: true};
                result = ['running', 'pending'];
                assert.deepEqual(task.extendStatuses(filters), result, 'True value of "active" filter parsed correctly');

                filters = {active: false};
                result = ['ready', 'error'];
                assert.deepEqual(task.extendStatuses(filters), result, 'False value of \'active\' filter parsed correctly');
            });

            test('Test extendGroups method', function() {
                var task = new models.Task(),
                    allTaskNames = _.flatten(_.values(task.groups)),
                    filters, result;

                filters = {name: []};
                result = allTaskNames;
                assert.deepEqual(task.extendGroups(filters), result, 'All task names are acceptable if "name" filter not specified');

                filters = {group: []};
                result = allTaskNames;
                assert.deepEqual(task.extendGroups(filters), result, 'All task names are acceptable if "group" filter not specified');

                filters = {name: 'deploy'};
                result = ['deploy'];
                assert.deepEqual(task.extendGroups(filters), result, '"name" filter can have string as a value');

                filters = {name: 'dump'};
                result = ['dump'];
                assert.deepEqual(task.extendGroups(filters), result, 'Tasks, that are not related to any task group, handled properly');

                filters = {name: ['deploy', 'check_networks']};
                result = ['deploy', 'check_networks'];
                assert.deepEqual(task.extendGroups(filters), result, '"name" filter can have list of strings as a value');

                filters = {group: 'deployment'};
                result = task.groups.deployment;
                assert.deepEqual(task.extendGroups(filters), result, '"group" filter can have string as a value');

                filters = {group: ['deployment', 'network']};
                result = allTaskNames;
                assert.deepEqual(task.extendGroups(filters), result, '"group" filter can have list of strings as a value');

                filters = {name: 'deploy', group: 'deployment'};
                result = ['deploy'];
                assert.deepEqual(task.extendGroups(filters), result, '"name" and "group" filters have intersection');

                filters = {name: 'deploy', group: 'network'};
                result = [];
                assert.deepEqual(task.extendGroups(filters), result, '"name" and "group" filters are not intersected');
            });
        });
    });
});
