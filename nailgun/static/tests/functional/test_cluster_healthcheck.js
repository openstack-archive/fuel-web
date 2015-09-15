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
    'intern!object',
    'intern/chai!assert',
    'tests/helpers',
    'tests/functional/pages/common',
    'tests/functional/pages/cluster',
    'sinon'
], function(_, registerSuite, assert, helpers, Common, ClusterPage, sinon) {
    'use strict';

    registerSuite(function() {
        var common,
            clusterPage,
            clusterName,
            server;

        return {
            name: 'Healthcheck page',
            setup: function() {
                common = new Common(this.remote);
                clusterPage = new ClusterPage(this.remote);
                clusterName = common.pickRandomName('Test Cluster');

                return this.remote
                    .then(function() {
                        return common.getIn();
                    })
                    .then(function() {
                        return common.createCluster(clusterName);
                    });
            },
            beforeEach: function() {
                return this.remote
                    .execute(function() {
                        require(['sinon'], function(s) {
                            server = s.fakeServer.create();
                            server.autoRespond = true;
                            server.autoRespondAfter = 100;
                            server.respondWith(/\/ostf\/testsets.*/, function(request) {
                                request.respond(
                                    200, {"Content-Type": "application/json"},
                                    '[{"id": "general_test", "name": "General fake tests"},' +
                                    ' {"id": "stopped_test", "name": "Long running 25 secs fake tests"}, ' +
                                    '{"id": "ha_deployment_test", "name": "Fake tests for HA deployment"},' +
                                    ' {"id": "environment_variables", "name": "Test for presence of env variables inside of testrun subprocess"}]'
                                );
                            });
                            server.respondWith(/\/ostf\/tests.*/, function(request) {
                                request.respond(
                                    200, {"Content-Type": "application/json"},
                                    '[{"status": null, "taken": null, "step": null, "testset": "ha_deployment_test", "name": "fake empty test", "duration": null, "message": null, "id": "fuel_plugin.testing.fixture.dummy_tests.deployment_types_tests.ha_deployment_test.HATest.test_ha_depl", "description": "        This is empty test for any\n        ha deployment\n        "}, {"status": null, "taken": null, "step": null, "testset": "ha_deployment_test", "name": "fake empty test", "duration": null, "message": null, "id": "fuel_plugin.testing.fixture.dummy_tests.deployment_types_tests.ha_deployment_test.HATest.test_ha_ubuntu_depl", "description": "        This is fake test for ha\n        ubuntu deployment\n        "}, {"status": null, "taken": null, "step": null, "testset": "general_test", "name": "Fast fail with step", "duration": null, "message": null, "id": "fuel_plugin.testing.fixture.dummy_tests.general_test.Dummy_test.test_fail_with_step", "description": "        "}, {"status": null, "taken": null, "step": null, "testset": "general_test", "name": "And fast error", "duration": null, "message": null, "id": "fuel_plugin.testing.fixture.dummy_tests.general_test.Dummy_test.test_fast_error", "description": "        "}, {"status": null, "taken": null, "step": null, "testset": "general_test", "name": "Fast fail", "duration": null, "message": null, "id": "fuel_plugin.testing.fixture.dummy_tests.general_test.Dummy_test.test_fast_fail", "description": "        "}, {"status": null, "taken": null, "step": null, "testset": "general_test", "name": "fast pass test", "duration": "1sec", "message": null, "id": "fuel_plugin.testing.fixture.dummy_tests.general_test.Dummy_test.test_fast_pass", "description": "        This is a simple always pass test\n        "}, {"status": null, "taken": null, "step": null, "testset": "general_test", "name": "Will sleep 5 sec", "duration": "5sec", "message": null, "id": "fuel_plugin.testing.fixture.dummy_tests.general_test.Dummy_test.test_long_pass", "description": "        This is a simple test\n        it will run for 5 sec\n        "}, {"status": null, "taken": null, "step": null, "testset": "general_test", "name": "Skip", "duration": null, "message": null, "id": "fuel_plugin.testing.fixture.dummy_tests.general_test.Dummy_test.test_skip", "description": "        "}, {"status": null, "taken": null, "step": null, "testset": "general_test", "name": "Skip with exception", "duration": null, "message": null, "id": "fuel_plugin.testing.fixture.dummy_tests.general_test.Dummy_test.test_skip_directly", "description": "        "}, {"status": null, "taken": null, "step": null, "testset": "stopped_test", "name": "You know.. for testing", "duration": "1sec", "message": null, "id": "fuel_plugin.testing.fixture.dummy_tests.stopped_test.dummy_tests_stopped.test_not_long_at_all", "description": "            "}, {"status": null, "taken": null, "step": null, "testset": "stopped_test", "name": "What i am doing here? You ask me????", "duration": null, "message": null, "id": "fuel_plugin.testing.fixture.dummy_tests.stopped_test.dummy_tests_stopped.test_one_no_so_long", "description": "        "}, {"status": null, "taken": null, "step": null, "testset": "stopped_test", "name": "This is long running tests", "duration": "25sec", "message": null, "id": "fuel_plugin.testing.fixture.dummy_tests.stopped_test.dummy_tests_stopped.test_really_long", "description": "           "}, {"status": null, "taken": null, "step": null, "testset": "environment_variables", "name": "", "duration": "", "message": null, "id": "fuel_plugin.testing.fixture.dummy_tests.test_environment_variables.TestEnvVariables.test_os_credentials_env_variables", "description": ""}]'
                                )
                            });
                            server.respondWith(/\ostf\/testruns\/last.*/, function(request) {
                                request.respond(
                                    200, {"Content-Type": "application/json"},
                                    '[]'
                                );
                            });
                        });
                    });
            },
            teardown: function() {
                return this.remote
                    .execute(function() {
                        server.restore();
                    })
                    .then(function() {
                        return common.removeCluster(clusterName);
                    });
            },
            'Health Check tests are rendered if response received': function() {
                return this.remote
                    .then(function() {
                        return clusterPage.goToTab('Dashboard');
                    })
                    .then(function() {
                        return clusterPage.goToTab('Health Check');
                    })
                    .then(function() {
                        return clusterPage.goToTab('Dashboard');
                    })
                    .then(function() {
                        return clusterPage.goToTab('Health Check');
                    })
                    .then(function() {
                        return clusterPage.goToTab('Dashboard');
                    })
                    .then(function() {
                        return clusterPage.goToTab('Health Check');
                    })
                    .waitForCssSelector('.healthcheck-table', 80000)
                    .then(function() {
                        return common.assertElementExists('.healthcheck-table', 'Healthcheck table is rendered');
                    });
            }
        }
    });
});
