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

define(['underscore',
        '../../helpers'], function(_, Helpers) {
    'use strict';
    function ClusterPage(remote) {
        this.remote = remote;
    }

    ClusterPage.prototype = {
        constructor: ClusterPage,
        goToTab: function(tabName) {
            var that = this;
            return this.remote
                .then(function() {
                    return Helpers.clickLinkByText(
                        that.remote,
                        '.tabs-box .tabs a',
                        tabName);
                });
        },
        removeCluster: function() {
            var that = this;
            return this.remote
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
                            .setFindTimeout(2000)
                            .findByCssSelector('div.modal-content')
                            .findByCssSelector('button.remove-cluster-btn')
                                .click()
                                .end()
                            .setFindTimeout(2000)
                            .waitForDeletedByCssSelector('div.modal-content');
                    }
                );
        },
        checkNodeRoles: function(assignRoles) {
            return this.remote
                .setFindTimeout(2000)
                .findAllByCssSelector('div.role-panel label')
                .then(function(roles) {
                    return roles.reduce(
                        function(result, role) {
                            return role
                                .getVisibleText()
                                .then(function(label) {
                                    var index = assignRoles.indexOf(label.substr(1));
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
            var that = this;
            return this.remote
                .setFindTimeout(2000)
                .then(function() {
                    return _.range(amount).reduce(
                        function(result, index) {
                            return that.remote
                                .setFindTimeout(1000)
                                .findAllByCssSelector('.node.discover > label')
                                .then(function(nodes) {
                                    return nodes[index].click();
                                })
                                .catch(function() {
                                    throw new Error('Failed to add ' + amount + ' nodes to the cluster');
                                });
                        },
                        true);
                });
        }
    };
    return ClusterPage;
});
