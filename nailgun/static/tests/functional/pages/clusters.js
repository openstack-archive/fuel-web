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

define(['../../helpers'], function(Helpers) {
    'use strict';
    function ClustersPage(remote) {
        this.remote = remote;
    }

    ClustersPage.prototype = {
        constructor: ClustersPage,
        createCluster: function(clusterName) {
            return this.remote
                .setFindTimeout(1000)
                .findByClassName('create-cluster')
                    .click()
                    .end()
                .sleep(2000) // Modal dialog opens
                .findByName('name')
                    .clearValue()
                    .type(clusterName)
                    .pressKeys('\uE007')
                    .pressKeys('\uE007')
                    .pressKeys('\uE007')
                    .pressKeys('\uE007')
                    .pressKeys('\uE007')
                    .pressKeys('\uE007')
                    .pressKeys('\uE007')
                    .end()
                .sleep(2000); // Modal dialog closes
        },
        goToTab: function(tabName) {
            var that = this;
            return this.remote
                .then(function() {
                    return Helpers.clickLinkByText(
                        that.remote,
                        'ul.cluster-tabs li a',
                        tabName);
                });
        },
        removeCluster: function(clusterName, suppressErrors) {
            var that = this;
            return this.remote
                .then(function() {
                    return that.goToEnvironment(clusterName, suppressErrors);
                })
                .then(
                    function() {
                        return this.parent
                            .setFindTimeout(2000)
                            .then(function() {
                                return that.goToTab('Actions');
                            })
                            .findByCssSelector('button.delete-environment-btn')
                                .click()
                                .end()
                            .sleep(1000) // Modal opens
                            .findByCssSelector('button.remove-cluster-btn')
                                .click()
                                .end()
                            .sleep(1000); // Modal closes
                    },
                    function() {
                        if (!suppressErrors) {
                            throw new Error('Unable to delete cluster ' + clusterName);
                        }
                        return true;
                    }
                );
        },
        goToEnvironment: function(clusterName) {
            return this.remote
                .setFindTimeout(5000)
                .findAllByCssSelector('div.cluster-name')
                .then(function(divs) {
                    return divs.reduce(
                        function(matchFound, element) {
                            return element.getVisibleText().then(
                                function(name) {
                                    if (name === clusterName) {
                                        element.click();
                                        return true;
                                    }
                                    return matchFound;
                                }
                            )},
                            false
                        );
                })
                .then(function(result) {
                    if (!result) {
                        throw new Error('Cluster ' + clusterName + ' not found');
                    }
                    return true;
                });
        },
        checkNodeRoles: function(assignRoles) {
            return this.remote
                .setFindTimeout(2000)
                .findAllByCssSelector('.role-label .label-wrapper')
                .then(function(roles) {
                    return roles.reduce(
                        function(result, role) {
                            return role
                                .getVisibleText()
                                .then(function(label) {
                                    var index = assignRoles.indexOf(label);
                                    if (index >= 0) {
                                        role.click();
                                        assignRoles.splice(index, 1);
                                        return assignRoles.length == 0;
                                    }
                                });
                            },
                            false
                        );
                });
        },
        checkNodes: function(amount) {
            return this.remote
                .setFindTimeout(2000)
                .findAllByCssSelector('label.node-box.discover')
                .then(function(nodes) {
                    return nodes.reduce(
                        function(nodesLeft, node) {
                            if (!nodesLeft) {
                                return 0;
                            }
                            node.click();
                            return nodesLeft - 1;
                        },
                        amount);
                })
                .then(function(nodesLeft) {
                    if (nodesLeft) {
                        throw new Error('Unable to add ' + amount + ' nodes to the cluster');
                    }
                });
        }
    };
    return ClustersPage;
});
