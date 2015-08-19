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
    'tests/functional/pages/cluster'
], function(registerSuite, assert, Common, ClusterPage) {
    'use strict';

    registerSuite(function() {
        var common,
            clusterPage,
            clusterName;

        return {
            name: 'Logs Tab',
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
                        return common.addNodesToCluster(1, ['Controller']);
                    });
            },
            beforeEach: function() {
                return this.remote
                    .then(function() {
                        return clusterPage.goToTab('Logs');
                    });
            },
            afterEach: function() {
            },
            teardown: function() {
                return this.remote
                    .then(function() {
                        return common.removeCluster(clusterName);
                    });
            },
            'Test Logs Tab': function() {
                var showLogsButton;
                return this.remote
                    .setFindTimeout(5000)
                    .findByCssSelector('.sticker select[name=source] > option')
                        // Check if "Source" dropdown exist
                        .end()
                    .findByCssSelector('.sticker button')
                        .then(function(button) {
                            showLogsButton = button;
                            return showLogsButton.isEnabled().then(function(isEnabled) {
                                return assert.isFalse(isEnabled, '"Show" button should be disabled until source change');
                            });
                        })
                        .end()
                    .findByCssSelector('.sticker select[name=source] option[value=receiverd]')
                        // Change the selected value for the "Source" dropdown
                        .click()
                        .end()
                    .then(function() {
                        // It is possible to click "Show" button now
                        return showLogsButton.isEnabled()
                            .then(function(isEnabled) {
                                return assert.isTrue(isEnabled, '"Show" button should be enabled after source change');
                            });
                    })
                    .then(function() {
                        showLogsButton.click()
                    })
                    .findAllByCssSelector('.log-entries tr:first-child td:last-child')
                        .then(function(elements) {
                            return assert.isTrue(elements.length > 0, 'Log tab entries are not present');
                        })
                        .end()
                    .findByCssSelector('.sticker select[name=type] > option[value=remote]')
                        // "Other servers" option is presented in "Logs" dropdown
                        .click()
                        .end()
                    .findAllByCssSelector('.sticker select[name=node] > option')
                        .then(function(elements) {
                            return assert.isTrue(elements.length > 0, '"Node" dropdown is not present');
                        })
                        .end()
            }
        };
    });
});
