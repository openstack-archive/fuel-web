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
    'tests/helpers',
    'tests/functional/pages/common',
    'tests/functional/pages/cluster'
], function(registerSuite, assert, helpers, Common, ClusterPage) {
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
                    })
                    .then(function() {
                        return clusterPage.goToTab('Logs');
                    });
            },
            teardown: function() {
                return this.remote
                    .then(function() {
                        return common.removeCluster(clusterName);
                    });
            },
            '"Show" button availability and logs displaying': function() {
                var showLogsButton;
                return this.remote
                    .setFindTimeout(5000)
                    .findByCssSelector('.sticker select[name=source] > option')
                        // Check if "Source" dropdown exist
                        .end()
                    .findByCssSelector('.sticker button')
                        .then(function(button) {
                            showLogsButton = button;
                            return showLogsButton
                                .isEnabled()
                                .then(function(isEnabled) {
                                    assert.isFalse(isEnabled, '"Show" button is disabled until source change');
                                });
                        })
                        .end()
                    .findByCssSelector('.sticker select[name=source] option[value=api]')
                        // Change the selected value for the "Source" dropdown to Rest API
                        .click()
                        .end()
                    .findByCssSelector('.sticker select[name=level] option[value=DEBUG]')
                        // Change the selected value for the "Level" dropdown to DEBUG
                        .click()
                        .end()
                    .then(function() {
                        // It is possible to click "Show" button now
                        return showLogsButton
                            .isEnabled()
                            .then(function(isEnabled) {
                                assert.isTrue(isEnabled, '"Show" button is enabled after source change');
                            });
                    })
                    .then(function() {
                        return showLogsButton.click();
                    })
                    .then(function() {
                        // Wait till Progress bar disappears
                        return common.waitForElementDeletion('.logs-tab div.progress');
                    })
                    .setFindTimeout(10000)
                    .findAllByCssSelector('.log-entries > tbody > tr')
                        .then(function(elements) {
                            assert.ok(elements.length, 'Log tab entries are present');
                        })
                        .end()
                    .findByCssSelector('.sticker select[name=type] > option[value=remote]')
                        // "Other servers" option is present in "Logs" dropdown
                        .click()
                        .end()
                    .findAllByCssSelector('.sticker select[name=node] > option')
                        .then(function(elements) {
                            assert.ok(elements.length, '"Node" dropdown is present');
                        });
            }
        };
    });
});
