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
    'tests/functional/pages/cluster',
    'tests/functional/pages/modal'
], function(registerSuite, assert, Common, ClusterPage, ModalWindow) {
    'use strict';

    registerSuite(function() {
        var common,
            modal,
            clusterPage;

        return {
            name: 'Simple Pages',
            setup: function() {
                common = new Common(this.remote);
                modal = new ModalWindow(this.remote);
                clusterPage = new ClusterPage(this.remote);

                return this.remote
                    .then(function() {
                        return common.getIn();
                    })
            },
            'Notification Page': function() {
                return this.remote
                    // Check that the badge notification indicator is visible
                    .findByCssSelector('.notifications-icon .badge')
                        .then(function(badgeNotification) {
                            badgeNotification.isDisplayed().then(function(isDisplayed) {
                                assert.ok(isDisplayed, 'badge notification indicator is shown in navigation');
                            })
                        })
                        .end()
                    // Go to Notification page
                    .clickByCssSelector('.notifications-icon')
                    .clickLinkByText('View all')
                    // Notification page is rendered
                    .waitForCssSelector('.notifications-page', 2000)
                    // There are one or more notifications on the page
                    .findByCssSelector('.notifications-page .row.notification')
                        .end()
                    .findByCssSelector('.notifications-icon .badge')
                        .then(function(badgeNotification) {
                            badgeNotification.isDisplayed().then(function(isDisplayed) {
                                assert.isFalse(isDisplayed, 'badge notification indicator is shown in navigation');
                            })
                        })
                        .end();
            },
            'Notification badge behaviour': function() {
                var clusterName = common.pickRandomName('Test Cluster');
                return this.remote
                    .then(function() {
                        return common.createCluster(clusterName);
                    })
                    .then(function() {
                        return clusterPage.goToTab('Nodes');
                    })
                    .then(function() {
                        return common.addNodesToCluster(1, ['Storage - Cinder']);
                    })
                    // Just in case - reset and hide badge notification counter by clicking on it
                    .clickByCssSelector('.notifications-icon')
                    .then(function() {
                        return common.removeCluster(clusterName);
                    })
                    .findByCssSelector('.notifications-icon .badge')
                        .then(function(badgeNotification) {
                            badgeNotification.isDisplayed().then(function(isDisplayed) {
                                assert.ok(isDisplayed, 'badge notification indicator is shown in navigation');
                            })
                        })
                        .end()
                    .clickByCssSelector('.notifications-icon')
                    .waitForCssSelector('.notifications-popover .notification.clickable', 15000)
                    // Check if Node Information dialog is shown
                    .clickByCssSelector('.notifications-popover .notification.clickable p')
                    .then(function() {
                        return modal.waitToOpen();
                    })
                    .then(function() {
                        // Dialog with node information is open
                        return modal.checkTitle('Node Information');
                    })
            }
        };
    });
});
