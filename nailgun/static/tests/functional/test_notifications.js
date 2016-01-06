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
/*eslint prefer-arrow-callback: 0*/
define([
    'intern!object',
    'tests/functional/pages/common',
    'tests/functional/pages/modal'
], function(registerSuite, Common, ModalWindow) {
    'use strict';

    registerSuite(function() {
        var common,
            modal;

        return {
            name: 'Notifications',
            setup: function() {
                common = new Common(this.remote);
                modal = new ModalWindow(this.remote);

                return this.remote
                    .then(function() {
                        return common.getIn();
                    });
            },
            'Notification Page': function() {
                return this.remote
                    .assertElementDisplayed('.notifications-icon .badge', 'Badge notification indicator is shown in navigation')
                    // Go to Notification page
                    .clickByCssSelector('.notifications-icon')
                    .clickLinkByText('View all')
                    .assertElementAppears('.notifications-page', 2000, 'Notification page is rendered')
                    .assertElementsExist('.notifications-page .notification', 'There are one or more notifications on the page')
                    .assertElementNotDisplayed('.notifications-icon .badge', 'Badge notification indicator is hidden');
            },
            'Notification badge behaviour': function() {
                var clusterName = common.pickRandomName('Test Cluster');
                return this.remote
                    .then(function() {
                        return common.createCluster(clusterName);
                    })
                    .then(function() {
                        return common.addNodesToCluster(1, ['Storage - Cinder']);
                    })
                    // Just in case - reset and hide badge notification counter by clicking on it
                    .clickByCssSelector('.notifications-icon')
                    .then(function() {
                        return common.removeCluster(clusterName);
                    })
                    .assertElementAppears('.notifications-icon .badge.visible', 3000, 'New notification appear after the cluster removal')
                    .clickByCssSelector('.notifications-icon')
                    .assertElementAppears('.notifications-popover .notification.clickable', 20000, 'Discovered node notification uploaded')
                    // Check if Node Information dialog is shown
                    .clickByCssSelector('.notifications-popover .notification.clickable p')
                    .then(function() {
                        return modal.waitToOpen();
                    })
                    .then(function() {
                        // Dialog with node information is open
                        return modal.checkTitle('Node Information');
                    });
            }
        };
    });
});
