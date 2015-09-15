/*
 * Copyright 2015 Mirantis, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the 'License'); you may
 * not use this file except in compliance with the License. You may obtain
 * a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an 'AS IS' BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations
 * under the License.
 **/

define([
    '../../helpers'
], function() {
    'use strict';

    var server;

    function HealthcheckPage(remote) {
        this.remote = remote;
    }

    HealthcheckPage.prototype = {
        constructor: HealthcheckPage,
        createFakeServerForNotRunnedTests: function() {
            return this.remote
                .execute(function() {
                    return require(['sinon'], function(s) {
                        server = s.fakeServer.create();
                        server.autoRespond = true;
                        server.respondWith('GET', /\/ostf\/testsets.*/, [
                            200, {'Content-Type': 'application/json'}, JSON.stringify(
                            [
                                {
                                    id: 'general_test', name: 'General fake tests'
                                },
                                {
                                    id: 'credentials_test', name: 'Checking credentials'},
                                {
                                    id: 'ha_deployment_test', name: 'Fake tests for HA deployment'
                                },
                                {
                                    id: 'environment_variables', name: 'Test for presence of env variables inside of testrun subprocess'
                                }
                            ])
                        ]);
                        server.respondWith('GET', /\/ostf\/tests.*/, [
                            200, {'Content-Type': 'application/json'}, JSON.stringify(
                                [{
                                    status: null, taken: null, step: null, testset: 'ha_deployment_test',
                                    name: 'Check disk space outage on controller and compute nodes', duration: null, message: null,
                                    id: 'fuel_health.tests.ha_deployment_test.HATest.test_ha_depl',
                                    description: 'Target component: Nova        Scenario: 1. Check outage on controller and compute nodes   '
                                },
                                {
                                    status: null, taken: null, step: null, testset: 'general_test',
                                    name: 'Check log rotation configuration on all nodes', duration: '30s.', message: null,
                                    id: 'fuel_health.tests.general_test.Dummy_test.test_fail_with_step',
                                    description: 'Target component: Logging        Scenario:            1. Check logrotate cron job on all controller and compute nodes'
                                },
                                {
                                    status: null, taken: null, step: null, testset: 'credentials_test',
                                    name: 'Check usage of default credentials on master node', duration: '1sec', message: null,
                                    id: 'fuel_health.tests.credentials_test.dummy_tests_stopped.test_not_long_at_all',
                                    description: 'Target component: Configuration        Scenario: 1. Check user can not ssh on master node with default credentials.            '
                                },
                                {
                                    status: null, taken: null, step: null, testset: 'environment_variables',
                                    name: 'Check if default credentials for OpenStack cluster have changed', duration: '', message: null,
                                    id: 'fuel_health.tests.test_environment_variables.TestEnvVariables.test_os_credentials_env_variables',
                                    description: 'Environment Vars description'
                                }])
                        ]);
                        server.respondWith('GET', /\ostf\/testruns\/last.*/, [
                            200, {'Content-Type': 'application/json'},
                            '[]'
                        ]);
                    });
                });
        },
        restoreServer: function() {
            return this.remote
                .execute(function() {
                    server.restore();
                });
        }
    };
    return HealthcheckPage;
});
