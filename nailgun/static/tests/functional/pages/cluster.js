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
            var self = this;
            return this.remote
                .then(function() {
                    return Helpers.clickLinkByText(
                        self.remote,
                        '.tabs-box .tabs a',
                        tabName);
                });
        },
        removeCluster: function(clusterName) {
            var self = this;
            return this.remote
                .then(function() {
                    return self.goToTab('Dashboard');
                })
                .findByCssSelector('button.delete-environment-btn')
                    .click()
                    .end()
                .then(function() {
                    return self.modal.waitToOpen();
                })
                .then(function() {
                    return self.modal.clickFooterButton('Delete');
                })
                .findAllByCssSelector('div.confirm-deletion-form input[type=text]')
                    .then(function(confirmInputs) {
                        if (confirmInputs.length)
                            return confirmInputs[0]
                                .type(clusterName)
                                .then(function() {
                                    return self.modal.clickFooterButton('Delete');
                                });
                        })
                        .end()
                .then(function() {
                    return self.modal.waitToClose();
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
            var self = this;
            return this.remote
                .setFindTimeout(2000)
                .then(function() {
                    return _.range(amount).reduce(
                        function(result, index) {
                            return self.remote
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
            var self = this;
            return this.remote
                .findByCssSelector('button.reset-environment-btn')
                    .click()
                    .end()
                .then(function() {
                    return self.modal.waitToOpen();
                })
                .then(function() {
                    return self.modal.checkTitle('Reset Environment');
                })
                .then(function() {
                    return self.modal.clickFooterButton('Reset');
                })
                .setFindTimeout(20000)
                .findAllByCssSelector('div.confirm-reset-form input[type=text]')
                    .then(function(confirmationInputs) {
                        if (confirmationInputs.length)
                            return confirmationInputs[0]
                                .type(clusterName)
                                .then(function() {
                                    return self.modal.clickFooterButton('Reset');
                                });
                    })
                    .end()
                .then(function() {
                    return self.modal.waitToClose();
                })
                .setFindTimeout(10000)
                .waitForDeletedByCssSelector('div.progress-bar');
        },
        isTabLocked: function(tabName) {
            var self = this;
            return this.remote
                .then(function() {
                    return self.goToTab(tabName);
                })
                .findByCssSelector('div.tab-content div.row.changes-locked')
                    .then(_.constant(true), _.constant(false));
        }
    };
    return ClusterPage;
});
