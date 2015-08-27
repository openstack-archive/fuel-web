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

define(['underscore', 'tests/functional/pages/modal'], function(_, ModalWindow) {
    'use strict';
    function DashboardPage(remote) {
        this.remote = remote;
        this.modal = new ModalWindow(remote);
    }

    DashboardPage.prototype = {
        constructor: DashboardPage,
        isDeploymentButtonVisible: function() {
            return this.remote
                .setFindTimeout(100)
                .findAllByCssSelector('button.deploy-btn')
                .then(function(buttons) {
                    return buttons.length > 0;
                });
        },
        startDeployment: function() {
            var self = this;
            return this.remote
                .setFindTimeout(2000)
                .findByCssSelector('div.deploy-block button.deploy-btn')
                    .click()
                    .end()
                .then(function() {
                    return self.modal.waitToOpen();
                })
                .then(function() {
                    return self.modal.checkTitle('Deploy Changes');
                })
                .then(function() {
                    return self.modal.clickFooterButton('Deploy');
                })
                .then(function() {
                    return self.modal.waitToClose();
                });
        },
        stopDeployment: function() {
            var self = this;
            return this.remote
                .findByCssSelector('button.stop-deployment-btn')
                    .click()
                    .end()
                .then(function() {
                    return self.modal.waitToOpen();
                })
                .then(function() {
                    return self.modal.checkTitle('Stop Deployment');
                })
                .then(function() {
                    return self.modal.clickFooterButton('Stop');
                })
                .then(function() {
                    return self.modal.waitToClose();
                });
        },
        isAddNodesButtonVisible: function() {
            return this.remote
                .setFindTimeout(100)
                .findAllByCssSelector('.btn-add-nodes')
                .then(function(buttons) {
                    return buttons.length > 0;
                });
        },
        startClusterRenaming: function() {
            return this.remote
                .setFindTimeout(100)
                .findByCssSelector('.cluster-info-value.name .glyphicon-pencil')
                    .click()
                    .end();
        },
        isRenameControlVisible: function() {
            return this.remote
                .findAllByCssSelector('.rename-block input[type=text]')
                    .then(function(elements) {
                        return elements.length;
                    });
        },
        getClusterName: function() {
            return this.remote
                .setFindTimeout(100)
                .findByCssSelector('.cluster-info-value.name a')
                .getVisibleText()
                    .then(function(value) {
                        return value;
                    });
        },
        setClusterName: function(name) {
            var self = this;
            return this.remote
                .then(function() {
                    return self.startClusterRenaming();
                })
                .setFindTimeout(100)
                .findByCssSelector('.rename-block input[type=text]')
                    .clearValue()
                    .type(name)
                    .type('')
                    .end();
        }
    };
    return DashboardPage;
});
