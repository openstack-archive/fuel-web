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
    'intern/dojo/node!lodash',
    'intern!object',
    'intern/chai!assert',
    'tests/functional/pages/common',
    'tests/functional/pages/cluster',
    'tests/functional/pages/dashboard',
    'tests/functional/pages/healthcheck'
], function(_, registerSuite, assert, Common, ClusterPage, DashboardPage, HealthcheckPage) {
    'use strict';

    registerSuite(function() {
        var common,
            clusterPage,
            clusterName,
            dashboardPage,
            healthCheckPage;

        return {
            name: 'Healthcheck page',
            setup: function() {
                common = new Common(this.remote);
                clusterPage = new ClusterPage(this.remote);
                dashboardPage = new DashboardPage(this.remote);
                clusterName = common.pickRandomName('Healthcheck test');
                healthCheckPage = new HealthcheckPage(this.remote);

                return this.remote
                    .then(function() {
                        return common.getIn();
                    })
                    .then(function() {
                        return common.createCluster(clusterName);
                    })
                    .sleep(400)
                    .then(function() {
                        return clusterPage.goToTab('Dashboard');
                    });
            },
            beforeEach: function() {
                return this.remote
                    .then(function() {
                        return healthCheckPage.createFakeServerForNotRunnedTests();
                    })
                    .then(function() {
                        return clusterPage.goToTab('Health Check');
                    });
            },
            afterEach: function() {
                return this.remote
                    .then(function() {
                        return healthCheckPage.restoreServer();
                    });
            },
            teardown: function() {
                return this.remote
                    .then(function() {
                        return common.removeCluster(clusterName);
                    });
            },
            'Health Check tests are rendered if response received': function() {
                return this.remote
                    .assertElementsAppear('.healthcheck-table', 5000, 'Healthcheck tables are rendered')
                    .assertElementDisabled('.custom-tumbler input[type=checkbox]', 'Test checkbox is disabled')
                    .assertElementContainsText('.alert-warning', 'Before you can test an OpenStack environment, you must deploy the OpenStack environment',
                    'Warning to deploy cluster is shown');
            },
            'After deploy tests': function() {
                this.timeout = 60000;
                return this.remote
                    .then(function() {
                        healthCheckPage.restoreServer();
                    })
                    .then(function() {
                        return common.addNodesToCluster(1, ['Controller']);
                    })
                    .then(function() {
                        return clusterPage.goToTab('Dashboard');
                    })
                    .then(function() {
                        return dashboardPage.startDeployment();
                    })
                    .assertElementDisappears('.dashboard-block .progress', 60000, 'Progress bar disappears after deployment')
                    .assertElementAppears('.links-block', 5000, 'Deployment completed')
                    .then(function() {
                        return healthCheckPage.createFakeServerForRunningAndFinishedTests();
                    })
                    .then(function() {
                        return clusterPage.goToTab('Health Check');
                    })
                    // common render tests
                    .assertElementEnabled('.custom-tumbler input[type=checkbox]', 'Test checkbox is enabled after deploy')
                    //
                    .assertElementDisabled('.run-tests-btn', 'Run tests button is disabled if no tests checked')
                    .assertElementExists('.toggle-credentials', 'Toggle credentials button is visible')
                    // provide credentials tests
                    .clickByCssSelector('.toggle-credentials')
                    .waitForCssSelector('.credentials', 500)
                    .assertElementsAppear('.credentials input[type=text]', 'Text inputs appear')
                    .clickByCssSelector('.toggle-credentials')
                    .waitForElementDeletion('.credentials', 2000)
                    .clickByCssSelector('.healthcheck-controls .select-all input[type=checkbox]')
                    .waitForCssSelector('.run-tests-btn:enabled', 1000);
            }
        };
    });
});
