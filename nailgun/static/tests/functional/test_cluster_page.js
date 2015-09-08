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
            clusterName;

        return {
            name: 'Cluster page',
            setup: function() {
                common = new Common(this.remote);
                clusterPage = new ClusterPage(this.remote);
                clusterName = common.pickRandomName('Test Cluster');

                return this.remote
                    .then(function() {
                        return common.getIn();
                    });
            },
            beforeEach: function() {
                return this.remote
                    .then(function() {
                        return common.createCluster(clusterName);
                    });
            },
            teardown: function() {
                return this.remote
                    .then(function() {
                        return common.removeCluster(clusterName, true);
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
                var nodesAmount = 3,
                    self = this,
                    applyButtonSelector = 'button.btn-apply';
                return this.remote
                    .setFindTimeout(5000)
                    .clickByCssSelector('a.btn-add-nodes')
                    .then(function() {
                        return common.assertElementDisabled(applyButtonSelector, 'Apply button is disabled until both roles and nodes chosen');
                    })
                    .findByCssSelector('div.role-panel')
                        .end()
                    .then(function() {
                        return clusterPage.checkNodeRoles(['Controller', 'Storage - Cinder']);
                    })
                    .then(function() {
                        return common.assertElementDisabled(applyButtonSelector, 'Apply button is disabled until both roles and nodes chosen');
                    })
                    .then(function() {
                        return clusterPage.checkNodes(nodesAmount);
                    })
                    .clickByCssSelector(applyButtonSelector)
                    .setFindTimeout(2000)
                    .findByCssSelector('button.btn-add-nodes')
                        .end()

                    .then(function() {
                        return _.range(1, 1 + nodesAmount).reduce(
                            function(nodesFound, index) {
                                return self.remote
                                    .setFindTimeout(1000)
                                    .findByCssSelector('div.node:nth-child(' + index + ')')
                                    .catch(function() {
                                        throw new Error('Unable to find ' + index + ' node in cluster');
                                    });
                            },
                            0
                        );
                    });
            }
        };
    });
});
