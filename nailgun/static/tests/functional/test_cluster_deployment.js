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
                        return common.assertElementNotExists(dashboardPage.deployButtonSelector, 'No deployment should be possible without nodes added')
                    });
            },
            'Discard changes': function() {
                return this.remote
                    .then(function() {
                        // Adding three controllers
                        return common.addNodesToCluster(1, ['Controller']);
                    })
                    .then(function() {
                        return clusterPage.goToTab('Dashboard');
                    })
                    .clickByCssSelector('.discard-changes')
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
                    // All changes discarded, add nodes button gets visible
                    // in deploy readiness block
                    .waitForCssSelector('div.deploy-readiness a.btn-add-nodes', 2000);
            },
            'Start/stop deployment': function() {
                this.timeout = 60000;
                return this.remote
                    .then(function() {
                        return common.addNodesToCluster(3, ['Controller']);
                    })
                    .then(function() {
                        return clusterPage.goToTab('Dashboard');
                    })
                    .waitForCssSelector('.dashboard-tab', 200)
                    .then(function() {
                        return dashboardPage.startDeployment();
                    })
                    .waitForCssSelector('div.deploy-process div.progress', 2000)
                    .then(function() {
                        return dashboardPage.stopDeployment();
                    })
                    .waitForElementDeletion('div.deploy-process div.progress', 5000)
                    // Deployment button available
                    .waitForCssSelector(dashboardPage.deployButtonSelector, 1000)
                    .then(function() {
                        return common.assertElementContainsText('div.alert-warning strong', 'Success', 'Deployment successfully stopped alert is expected');
                    })
                    //@todo: uncomment this after bug fix https://bugs.launchpad.net/fuel/+bug/1493291
                    //.then(function() {
                    //    return common.assertElementNotExists('.go-to-healthcheck', 'Healthcheck link is not visible after stopped deploy');
                    //})
                    // Reset environment button is available
                    .then(function() {
                        return clusterPage.resetEnvironment(clusterName);
                    });
            },
            'Test tabs locking after deployment completed': function() {
                this.timeout = 100000;
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
                    // Deployment competed
                    .waitForCssSelector('div.horizon', 50000)
                    .then(function() {
                        return common.assertElementExists('.go-to-healthcheck', 'Healthcheck link is visible after deploy');
                    })
                    .findByCssSelector('div.horizon a.btn-success')
                        .getAttribute('href')
                        .then(function(value) {
                            return assert.isTrue(_.startsWith(value, 'http'), 'Link to Horizon is formed');
                        })
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
                    });
            }
        };
    });
});
