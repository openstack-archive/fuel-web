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
    'tests/functional/pages/dashboard',
    'tests/functional/pages/modal'
], function(_, registerSuite, assert, Common, ClusterPage, DashboardPage, ModalWindow) {
    'use strict';

    registerSuite(function() {
        var common,
            clusterPage,
            dashboardPage,
            modal,
            clusterName;

        return {
            name: 'Dashboard tests',
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

            'Add nodes button is present and works on freshly created cluster': function() {
                return this.remote
                    .then(function() {
                        return dashboardPage.isAddNodesButtonVisible();
                    })
                    .then(function(isVisible) {
                        assert.isTrue(isVisible, 'Add nodes button is visible on new cluster');
                    })
                        .end()
                    .findByCssSelector('.btn-add-nodes')
                        .click()
                        .end()
                    .getCurrentUrl()
                    .then(function(url) {
                        assert.isTrue(_.contains(url, 'nodes/add'), 'Add nodes button navigates from Dashboard to Add nodes screen');
                    })
            },

            'Renaming cluster works': function() {
                var initialName = clusterName,
                    newName = clusterName + '!!!';
                return this.remote
                    .then(function() {
                        return dashboardPage.startClusterRenaming();
                    })
                    .then(function() {
                        return dashboardPage.isRenameControlVisible()
                            .then(function(isVisible) {
                                assert.ok(isVisible, 'Rename control appears');
                            })
                            // Escape
                            .type('')
                            .end()
                    })
                    .then(function() {
                        return dashboardPage.isRenameControlVisible()
                            .then(function(isVisible) {
                                assert.notOk(isVisible, 'Rename control disappears');
                            })
                            .end()
                    })
                    .setFindTimeout(1000)
                    .then(function() {
                        return dashboardPage.getClusterName()
                            .then(function(text) {
                                assert.isTrue(text == initialName, 'Switching rename control does not change cluster name');
                            })
                            .end()
                    })
                    .then(function() {
                        return dashboardPage.setClusterName(newName)
                            .end()
                    })
                    .setFindTimeout(1000)
                    .then(function() {
                        return dashboardPage.getClusterName()
                            .then(function(text) {
                                assert.isFalse(text == initialName, 'New cluster name is not equal to the initial');
                                assert.isTrue(text == newName, 'New name is applied');
                            })
                    })
                    .then(function() {
                        return dashboardPage.setClusterName(initialName);
                    });
            },

            'Adding node manipulations': function() {
                return this.remote
                    .findByCssSelector('.btn-add-nodes')
                        .click()
                        .end()
                    .then(function() {
                        return common.addNodesToCluster(1, ['Controller']);
                    })
                    .then(function() {
                        return clusterPage.goToTab('Dashboard');
                    })
                    .then(function() {
                        return dashboardPage.isDeploymentButtonVisible()
                            .then(function(isVisible) {
                                assert.isTrue(isVisible, 'Deploy button is visible after adding Controller node');
                            })
                    })
                    .setFindTimeout(1000)
                    .findByCssSelector('a.discard-changes')
                        .click()
                        .end()
                    .then(function() {
                        return modal.waitToOpen();
                    })
                    .then(function() {
                        return modal.clickFooterButton('Discard');
                    })
                    .then(function() {
                        return modal.waitToClose();
                    })
                    .setFindTimeout(1000)
                    .then(function() {
                        return dashboardPage.isDeploymentButtonVisible()
                            .then(function(isVisible) {
                                assert.isFalse(isVisible, 'Deploy button is not visible after adding Controller node');
                            })
                    })
            }
        };
    });
});
