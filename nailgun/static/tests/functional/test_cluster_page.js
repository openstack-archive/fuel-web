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
    'tests/functional/pages/cluster'
], function(_, registerSuite, assert, helpers, Common, ClusterPage) {
    'use strict';

    registerSuite(function() {
        var common,
            clusterPage,
            clusterName,
            nodesAmount = 3,
            applyButtonSelector = 'button.btn-apply';

        return {
            name: 'Cluster page',
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
                    })
                    .then(function() {
                        return clusterPage.goToTab('Nodes');
                    });
            },
            'Add Cluster Nodes': function() {
                return this.remote
                    .then(function() {
                        return common.assertElementExists('.node-list .alert-warning', 'Node list shows warning if there are no nodes in environment');
                    })
                    .clickByCssSelector('.btn-add-nodes')
                    // wait for unallocated nodes loaded
                    .waitForCssSelector('.node', 2000)
                    .then(function() {
                        return common.assertElementDisabled(applyButtonSelector, 'Apply button is disabled until both roles and nodes chosen');
                    })
                    .then(function() {
                        return common.assertElementDisabled('.role-panel [type=checkbox][name=mongo]', 'Unavailable role has locked checkbox');
                    })
                    .then(function() {
                        return common.assertElementExists('.role-panel .mongo i.tooltip-icon', 'Unavailable role has warning tooltip');
                    })
                    .then(function() {
                        return clusterPage.checkNodeRoles(['Controller', 'Storage - Cinder']);
                    })
                    .then(function() {
                        return common.assertElementDisabled('.role-panel [type=checkbox][name=compute]', 'Compute role can not be added together with selected roles');
                    })
                    .then(function() {
                        return common.assertElementDisabled(applyButtonSelector, 'Apply button is disabled until both roles and nodes chosen');
                    })
                    .then(function() {
                        return clusterPage.checkNodes(nodesAmount);
                    })
                    .clickByCssSelector(applyButtonSelector)
                    .waitForElementDeletion(applyButtonSelector, 2000)
                    // wait for cluster node list loaded
                    .waitForCssSelector('.nodes-group', 2000)
                    .findAllByCssSelector('.node-list')
                        .findAllByCssSelector('.node')
                            .then(function(elements) {
                                return assert.equal(elements.length, nodesAmount, nodesAmount + ' nodes were successfully added to the cluster');
                            })
                            .end()
                        .findAllByCssSelector('.nodes-group')
                            .then(function(elements) {
                                return assert.equal(elements.length, 1, 'One node group is present');
                            })
                            .end()
                        .end();
            },
            'Edit cluster node roles': function() {
                return this.remote
                    .then(function() {
                        return common.addNodesToCluster(1, ['Storage - Cinder']);
                    })
                    .findAllByCssSelector('.node-list .nodes-group')
                        .then(function(elements) {
                            return assert.equal(elements.length, 2, 'Two node groups are present');
                        })
                        .end()
                    // select all nodes
                    .clickByCssSelector('.select-all label')
                    .clickByCssSelector('.btn-edit-roles')
                    // wait for cluster nodes screen unmounted
                    .waitForElementDeletion('.btn-edit-roles', 2000)
                    .then(function() {
                        return common.assertElementNotExists('.node-box [type=checkbox]:not(:disabled)', 'Node selection is locked on Edit Roles screen');
                    })
                    .then(function() {
                        return common.assertElementNotExists('[name=select-all]:not(:disabled)', 'Select All checkboxes are locked on Edit Roles screen');
                    })
                    .then(function() {
                        return common.assertElementExists('.role-panel [type=checkbox][name=controller]:indeterminate', 'Controller role checkbox has indeterminate state');
                    })
                    .then(function() {
                        // uncheck Cinder role
                        return clusterPage.checkNodeRoles(['Storage - Cinder', 'Storage - Cinder']);
                    })
                    .clickByCssSelector(applyButtonSelector)
                    // wait for role editing screen unmounted
                    .waitForElementDeletion('.btn-apply', 2000)
                    .findAllByCssSelector('.node-list .node-box')
                        .then(function(elements) {
                            return assert.equal(elements.length, nodesAmount, 'One node was removed from cluster after editing roles');
                        })
                        .end();
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
            }
        };
    });
});
