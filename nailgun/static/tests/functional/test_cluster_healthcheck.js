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
    'tests/functional/pages/common',
    'tests/functional/pages/cluster',
    'tests/functional/pages/healthcheck'
], function(_, registerSuite, assert, Common, ClusterPage, HealthcheckPage) {
    'use strict';

    registerSuite(function() {
        var common,
            clusterPage,
            clusterName,
            healthCheckPage;

        return {
            name: 'Healthcheck page',
            setup: function() {
                common = new Common(this.remote);
                clusterPage = new ClusterPage(this.remote);
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
            teardown: function() {
                return this.remote
                    .then(function() {
                        return common.removeCluster(clusterName);
                    });
            },
            'Health Check tests are rendered if response received': function() {
                return this.remote
                    .findAllByCssSelector('.healthcheck-table')
                        .then(function(elements) {
                            return assert.isTrue(elements.length > 0, 'Healthcheck table is rendered');
                        })
                    .then(function() {
                        return common.assertElementDisabled('.custom-tumbler input[type=checkbox]', 'Test checkbox is disabled');
                    })
                    .then(function() {
                        return common.assertElementContainsText('.alert-warning', 'You must deploy your OpenStack environment before running tests against it.',
                            'Warning to deploy cluster is shown');
                    })
                    .then(function() {
                        return healthCheckPage.restoreServer();
                    });
            }
            // @TODO(@morale): deal with this
            //'After deploy tests': function() {
            //    this.timeout = 60000;
            //    return this.remote
            //        .execute(function() {
            //            server.restore();
            //        })
            //        .then(function() {
            //            return common.addNodesToCluster(1, ['Controller']);
            //        })
            //        .then(function() {
            //            return clusterPage.goToTab('Dashboard');
            //        })
            //        .then(function() {
            //            return dashboardPage.startDeployment();
            //        })
            //        // Deployment competed
            //        .waitForCssSelector('div.horizon', 50000)
            //        .then(function() {
            //            return clusterPage.goToTab('Health Check');
            //        })
            //        // common render tests
            //        .then(function() {
            //            return common.assertElementEnabled('.custom-tumbler input[type=checkbox]', 'Test checkbox is enabled after deply');
            //        })
            //
            //        .then(function() {
            //            return common.assertElementDisabled('.run-tests-btn', 'Run tests button is disabled if no tests checked');
            //        })
            //        .then(function() {
            //            return common.assertElementExists('.toggle-credentials', 'Toggle credentials button is visible');
            //        })
            //        // provide credentials tests
            //        .clickByCssSelector('.toggle-credentials')
            //        .waitForCssSelector('.credentials', 500)
            //        .findAllByCssSelector('.credentials input[type=text]')
            //            .then(function(elements) {
            //                return assert.isTrue(elements.length > 0, 'Text inputs appear');
            //            })
            //            .end()
            //        .clickByCssSelector('.toggle-credentials')
            //        .waitForElementDeletion('.credentials', 2000)
            //        .then(function() {
            //            return common.assertElementNotExists('.alert-warning', 'No warning is shown after deploy');
            //        })
            //        .then(function() {
            //            return healthCheckPage.createFakeServerForRunningAndFinishedTests();
            //        })
            //        .then(function() {
            //            return clusterPage.goToTab('Dashboard');
            //        })
            //        .then(function() {
            //            return clusterPage.goToTab('Health Check');
            //        })
            //        .clickByCssSelector('.healthcheck-controls .select-all input[type=checkbox]')
            //        .waitForCssSelector('.run-tests-btn:enabled', 1000)
            //        .clickByCssSelector('.run-tests-btn')
            //        .sleep(50000)
            //}
        }
    });
});
