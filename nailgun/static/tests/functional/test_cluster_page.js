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
            nodesAmount = 3;

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
                var self = this;

                return this.remote
                    .then(function() {
                        return common.elementExists('.node-list .alert-warning', 'Node list shows warning if there are no nodes in environment');
                    })
                    // go to Add Nodes screen
                    .findByCssSelector('button.btn-add-nodes')
                        .click()
                        .end()
                    // wait for Add Nodes screen opened
                    .waitForCssSelector('.role-panel', 2000)
                    .then(function() {
                        return common.isElementDisabled('button.btn-apply', 'Apply button is disabled until both roles and nodes chosen');
                    })
                    .then(function() {
                        return common.isElementDisabled('.role-panel [type=checkbox][name=mongo]', 'Unavailable role has locked checkbox');
                    })
                    .then(function() {
                        return common.elementExists('.role-panel .mongo i.tooltip-icon', 'Unavailable role has warning tooltip');
                    })
                    .then(function() {
                        return clusterPage.checkNodeRoles(['Controller', 'Storage - Cinder']);
                    })
                    .then(function() {
                        return common.isElementDisabled('.role-panel [type=checkbox][name=compute]', 'Compute role can not be added together with selected roles');
                    })
                    .then(function() {
                        return common.isElementDisabled('button.btn-apply', 'Apply button is disabled until both roles and nodes chosen');
                    })
                    .then(function() {
                        return clusterPage.checkNodes(nodesAmount);
                    })
                    // save changes
                    .findByCssSelector('button.btn-apply')
                        .click()
                        .end()
                    // check cluster node list is rendered
                    .waitForCssSelector('button.btn-add-nodes', 2000)
                    // check node allocation
                    .then(function() {
                        return _.range(1, 1 + nodesAmount).reduce(
                            function(nodesFound, index) {
                                return self.remote
                                    .findByCssSelector('div.node:nth-child(' + index + ')')
                                        .catch(function() {
                                            throw new Error('Unable to find ' + index + ' node in cluster');
                                        });
                            },
                            0
                        );
                    })
                    .findAllByCssSelector('.node-list .nodes-group')
                        .then(function(elements) {
                            return assert.equal(elements.length, 1, 'One node group is present');
                        })
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
                    .findByCssSelector('.select-all label')
                        .click()
                        .end()
                    // go to Edit Roles screen
                    .findByCssSelector('button.btn-edit-roles')
                        .click()
                        .end()
                    // wait for Edit Roles screen opened
                    .waitForCssSelector('.role-panel', 2000)
                    .then(function() {
                        return common.elementNotExists('.node-box [type=checkbox]:not(:disabled)', 'Node selection is locked on Edit Roles screen');
                    })
                    .then(function() {
                        return common.elementNotExists('[name=select-all]:not(:disabled)', 'Select All checkboxes are locked on Edit Roles screen');
                    })
                    .then(function() {
                        return common.elementExists('.role-panel [type=checkbox][name=controller]:indeterminate', 'Controller role checkbox has indeterminate state');
                    })
                    .then(function() {
                        // uncheck Cinder role
                        return clusterPage.checkNodeRoles(['Storage - Cinder', 'Storage - Cinder']);
                    })
                    // save changes
                    .findByCssSelector('button.btn-apply')
                        .click()
                        .end()
                    // check cluster node list is rendered
                    // nodes remain selected, so Edit Roles button is checked
                    .waitForCssSelector('button.btn-edit-roles', 4000)
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
