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
    'tests/functional/pages/common',
    'tests/functional/pages/clusters'
], function(registerSuite, assert, Common, ClustersPage) {
    'use strict';

    registerSuite(function() {
        var common,
            clustersPage,
            clusterName;

        return {
            name: 'Clusters page',
            setup: function() {
                common = new Common(this.remote);
                clustersPage = new ClustersPage(this.remote);
                clusterName = 'Test Cluster #' + Math.round(99999 * Math.random());
            },
            beforeEach: function() {
                return this.remote
                    .then(function() {
                        return common.getIn();
                    })
                    .then(function() {
                        return common.createCluster(clusterName);
                    });
            },
            afterEach: function() {
                return this.remote
                    .then(function() {
                        return common.removeCluster(clusterName, true);
                    });
            },
            'Create Cluster': function() {
                return this.remote
                    .then(function() {
                        return common.doesClusterExist(clusterName);
                    })
                    .then(function(result) {
                        assert.ok(result, 'Newly created cluster name found in the list');
                    });
            },
            'Remove Cluster': function() {
                return this.remote
                    .then(function() {
                        return common.doesClusterExist(clusterName);
                    })
                    .then(function(result) {
                        assert.ok(result, 'Cluster exists');
                    })
                    .then(function() {
                        return common.removeCluster(clusterName);
                    })
                    .then(function() {
                        return common.doesClusterExist(clusterName);
                    })
                    .then(function(result) {
                        assert.notOk(result, 'Cluster removed successfully');
                    });
            },
            'Add Cluster Nodes': function() {
                var nodesAmount = 2,
                    applyButton;
                return this.remote
                    .setTimeout('page load', 20000)
                    .then(function() {
                        return common.goToEnvironment(clusterName);
                    })
                    .setFindTimeout(5000)
                    .findByCssSelector('button.btn-add-nodes')
                        .click()
                        .end()
                    .findByCssSelector('button.btn-apply')
                        .then(function(button) {
                            applyButton = button;
                            return applyButton.isEnabled().then(function(isEnabled) {
                                assert.isFalse(isEnabled, 'Apply button is disabled until both roles and nodes chosen');
                                return true;
                            });
                        })
                        .end()
                    .findByCssSelector('div.role-panel')
                        .end()
                    .then(function() {
                        return clustersPage.checkNodeRoles(['Controller', 'Storage - Cinder']);
                    })
                    .then(function() {
                        return applyButton.isEnabled().then(function(isEnabled) {
                            assert.isFalse(isEnabled, 'Apply button is disabled until both roles and nodes chosen');
                            return true;
                        });
                    })
                    .then(function() {
                        return clustersPage.checkNodes(nodesAmount);
                    })
                    .then(function() {
                        applyButton.click();
                    })
                    .waitForDeletedByCssSelector('button.btn-apply')
                    .then(function() {
                        return common.goToEnvironment(clusterName);
                    })
                    .findAllByCssSelector('div.node')
                    .then(function(nodes) {
                        assert.equal(nodesAmount, nodes.length, 'Cluster expected to have ' + nodesAmount + ' nodes added');
                    });
            }
        };
    });
});
