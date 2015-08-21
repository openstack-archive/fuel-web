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
        'tests/functional/pages/modal',
        '../../helpers'], function(_, ModalWindow, Helpers) {
    'use strict';
    function ClusterPage(remote) {
        this.remote = remote;
        this.modal = new ModalWindow(remote);
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
        removeCluster: function(clusterName) {
            var that = this;
            return this.remote
                .then(function() {
                    return that.goToTab('Dashboard');
                })
                .findByCssSelector('button.delete-environment-btn')
                    .click()
                    .end()
                .then(function() {
                    return that.modal.waitToOpen();
                })
                .then(function() {
                    return that.modal.clickFooterButton('Delete');
                })
                .findByCssSelector('div.confirm-deletion-form input[type=text]')
                .then(
                    function(confirmInput) {
                        return confirmInput
                                .type(clusterName)
                            .then(function() {
                                return that.modal.clickFooterButton('Delete');
                            });
                    },
                    function(error) {
                        if (error.name && error.name == 'NoSuchElement') return true;
                        throw error;
                    })
                .then(function() {
                    return that.modal.waitToClose();
                });
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
        },
        resetEnvironment: function(clusterName) {
            var that = this;
            return this.remote
                .findByCssSelector('button.reset-environment-btn')
                    .click()
                    .end()
                .then(function() {
                    return that.modal.waitToOpen();
                })
                .then(function() {
                    return that.modal.checkTitle('Reset Environment');
                })
                .then(function() {
                    return that.modal.clickFooterButton('Reset');
                })
                .setFindTimeout(20000)
                .findByCssSelector('div.confirm-reset-form input[type=text]')
                    .then(
                        function(confirmationInput) {
                            return confirmationInput
                                    .type(clusterName)
                                .then(function() {
                                    return that.modal.clickFooterButton('Reset');
                                });
                        },
                        function(error) {
                            if (error.name && error.name == 'NoSuchElement') return true;
                            throw error;
                        })
                .then(function() {
                    return that.modal.waitToClose();
                })
                .setFindTimeout(2000)
                .waitForDeletedByCssSelector('div.progress-bar');
        },
        isTabLocked: function(tabName) {
            var that = this;
            return this.remote
                .then(function() {
                    return that.goToTab(tabName);
                })
                .findByCssSelector('div.tab-content div.row.changes-locked')
                    .then(_.constant(true), _.constant(false));
        }
    };
    return ClusterPage;
});
