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
    'intern/dojo/node!lodash',
    'tests/functional/pages/modal',
    'intern/dojo/node!leadfoot/helpers/pollUntil',
    '../../helpers'
], function(_, ModalWindow, pollUntil) {
    'use strict';
    function ClusterPage(remote) {
        this.remote = remote;
        this.modal = new ModalWindow(remote);
    }

    ClusterPage.prototype = {
        constructor: ClusterPage,
        goToTab: function(tabName) {
            return this.remote
                .findByCssSelector('.cluster-page .tabs')
                    .clickLinkByText(tabName)
                    .end()
                .then(pollUntil(function(textToFind) {
                    return window.$('.cluster-tab.active').text() == textToFind || null;
                }, [tabName], 3000));
        },
        removeCluster: function(clusterName) {
            var self = this;
            return this.remote
                .clickLinkByText('Dashboard')
                .clickByCssSelector('button.delete-environment-btn')
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
                })
                .waitForCssSelector('.clusters-page', 2000)
                .waitForDeletedByCssSelector('.clusterbox', 20000);
        },
        searchForNode: function(nodeName) {
            return this.remote
                .clickByCssSelector('button.btn-search')
                .setInputValue('input[name=search]', nodeName);
        },
        checkNodeRoles: function(assignRoles) {
            return this.remote
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
        checkNodes: function(amount, status) {
            var self = this;
            status = status || 'discover';
            return this.remote
                .then(function() {
                    return _.range(amount).reduce(
                        function(result, index) {
                            return self.remote
                                .findAllByCssSelector('.node' + '.' + status + ' > label')
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
                .clickByCssSelector('button.reset-environment-btn')
                .then(function() {
                    return self.modal.waitToOpen();
                })
                .then(function() {
                    return self.modal.checkTitle('Reset Environment');
                })
                .then(function() {
                    return self.modal.clickFooterButton('Reset');
                })
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
                .waitForElementDeletion('div.progress-bar', 10000);
        },
        isTabLocked: function(tabName) {
            var self = this;
            return this.remote
                .then(function() {
                    return self.goToTab(tabName);
                })
                .waitForCssSelector('div.tab-content div.row.changes-locked', 2000)
                    .then(_.constant(true), _.constant(false));
        }
    };
    return ClusterPage;
});
