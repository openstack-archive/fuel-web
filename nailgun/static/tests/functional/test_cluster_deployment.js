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
    'tests/functional/pages/dashboard',
    'tests/functional/pages/modal'
], function(_, registerSuite, assert, helpers, Common, ClusterPage, DashboardPage, ModalWindow) {
    'use strict';

    registerSuite(function() {
        var common,
            clusterPage,
            dashboardPage,
            modal,
            clusterName;

        return {
            name: 'Cluster deployment',
            setup: function() {
                common = new Common(this.remote);
                clusterPage = new ClusterPage(this.remote);
                dashboardPage = new DashboardPage(this.remote);
                modal = new ModalWindow(this.remote);
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
                    .then(function() {
                        return clusterPage.goToTab('Dashboard');
                    });
            },
            teardown: function() {
                return this.remote
                    .then(function() {
                        return common.removeCluster(clusterName);
                    });
            },
            'No deployment button when there are no nodes added': function() {
                return this.remote
                    .then(function() {
                        return common.assertElementNotExists('button.deploy-btn', 'No deployment should be possible without nodes added')
                    });
            },
            'No controller warning': function() {
                return this.remote
                    .then(function() {
                        // Adding single compute
                        return common.addNodesToCluster(1, ['Compute']);
                    })
                    .then(function() {
                        return clusterPage.goToTab('Dashboard');
                    })
                    .then(function() {
                        return common.assertElementNotExists('button.deploy-btn', 'No deployment should be possible without controller nodes added')
                    })
                    .findByCssSelector('div.instruction.invalid')
                        // Invalid configuration message is shown
                        .end()
                    .then(function() {
                        return common.assertElementContainsText(
                            'div.validation-result ul.danger li',
                            'At least 1 Controller nodes are required (0 selected currently).',
                            'No controllers added warning should be shown'
                        );
                    });
            },
            'Discard changes': function() {
                this.timeout = 120000;
                return this.remote
                    .then(function() {
                        // Adding three controllers
                        return common.addNodesToCluster(1, ['Controller']);
                    })
                    .then(function() {
                        return clusterPage.goToTab('Dashboard');
                    })
                    .clickLinkByText('Discard Changes')
                    .then(function() {
                        return modal.waitToOpen();
                    })
                    .then(function() {
                        return common.assertElementContainsText('h4.modal-title', 'Discard Changes', 'Discard Changes confirmation modal expected');
                    })
                    .then(function() {
                        return modal.clickFooterButton('Discard');
                    })
                    .then(function() {
                        return modal.waitToClose();
                    })
                    .findByCssSelector('div.deploy-readiness a.btn-add-nodes')
                        // All changes discarded, add nodes button gets visible
                        // in deploy readiness block
                        .end();
            },
            'Start/stop deployment': function() {
                this.timeout = 120000;
                return this.remote
                    .then(function() {
                        return common.addNodesToCluster(3, ['Controller']);
                    })
                    .then(function() {
                        return clusterPage.goToTab('Dashboard');
                    })
                    .waitForCssSelector('.dashboard-tab', 2000)
                    .then(function() {
                        return dashboardPage.startDeployment();
                    })
                    .setFindTimeout(2000)
                    .findAllByCssSelector('div.deploy-process div.progress')
                        .then(function(elements) {
                            assert.ok(elements.length, 'Deployment progress bar expected to appear');
                        })
                        .end()
                    .then(function() {
                        return dashboardPage.stopDeployment();
                    })
                    .waitForElementDeletion('div.deploy-process div.progress', 5000)
                    // Deployment button available
                    .waitForCssSelector('div.deploy-block button.deploy-btn', 1000)
                    .then(function() {
                        return common.assertElementContainsText('div.alert-warning strong', 'Success', 'Deployment successfully stopped alert is expected');
                    })
                    // Reset environment button is available
                    .then(function() {
                        return clusterPage.resetEnvironment(clusterName);
                    });
            },
            'Test tabs locking after deployment completed': function() {
                this.timeout = 120000;
                return this.remote
                    .then(function() {
                        // Adding single controller (enough for deployment)
                        return common.addNodesToCluster(1, ['Controller']);
                    })
                    .then(function() {
                        return clusterPage.isTabLocked('Networks');
                    })
                    .then(function(isLocked) {
                        assert.isFalse(isLocked, 'Networks tab is not locked for undeployed cluster');
                    })
                    .then(function() {
                        return clusterPage.isTabLocked('Settings');
                    })
                    .then(function(isLocked) {
                        assert.isFalse(isLocked, 'Settings tab is not locked for undeployed cluster');
                    })
                    .then(function() {
                        return clusterPage.goToTab('Dashboard');
                    })
                    .then(function() {
                        return dashboardPage.startDeployment();
                    })
                    .setFindTimeout(120000)
                    // Deployment competed
                    .findByCssSelector('div.horizon')
                        .end()
                    .then(function() {
                        return clusterPage.isTabLocked('Networks');
                    })
                    .then(function(isLocked) {
                        assert.isTrue(isLocked, 'Networks tab should turn locked after deployment');
                    })
                    .then(function() {
                        return clusterPage.isTabLocked('Settings');
                    })
                    .then(function(isLocked) {
                        assert.isTrue(isLocked, 'Settings tab should turn locked after deployment');
                    })
                    .then(function() {
                        return clusterPage.goToTab('Dashboard');
                    })
                    .then(function() {
                        return clusterPage.resetEnvironment(clusterName);
                    })
            }
        };
    });
});
