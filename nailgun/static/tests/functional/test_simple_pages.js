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
            name: 'Simple Pages',
            setup: function() {
                common = new Common(this.remote);
                clusterPage = new ClusterPage(this.remote);
                clusterName = common.pickRandomName('Test Cluster');

                return this.remote
                    .then(function() {
                        return common.getIn();
                    })
            },
            'Installed Plugins Page is rendered correctly': function() {
                return this.remote
                    // Go to Support page
                    .clickLinkByText('Plugins')
                    // Plugins Page is rendered
                    .waitForCssSelector('.plugins-page', 1000)
                    // Documentation links are present
                    .findAllByCssSelector('.plugins-page li a')
                        .then(function(elements) {
                            assert.ok(elements.length, 'Documentation Links showed on the Installed Plugins Page');
                        })
                        .end();
            },
            'Releases Page is rendered correctly': function() {
                return this.remote
                    // Go to Releases page
                    .clickLinkByText('Releases')
                    // Releases Page is rendered
                    .waitForCssSelector('.releases-page', 2000)
                    .findAllByCssSelector('.releases-page table tbody td')
                        .then(function(elements) {
                            assert.ok(elements.length, 'Some Release information are loaded');
                        })
                        .end();
            },
            'Capacity Audit Page is rendered correctly': function() {
                return this.remote
                    // Go to Capacity Audit page
                    .clickLinkByText('Support')
                    .clickLinkByText('View Capacity Audit')
                    .waitForCssSelector('.capacity-page', 2000)
                    .findAllByCssSelector('.capacity-page .capacity-audit-table')
                        .then(function(elements) {
                            assert.ok(elements.length, 'Some Capacity Audit information are loaded');
                        })
                        .end()
                    .then(function() {
                        return common.assertElementExists('.capacity-page .btn', 'Download Report button is present');
                    });
            },
            'Notification Page is rendered correctly': function() {
                return this.remote
                    // Check that the bage Notification Indicator is visible
                    .findByCssSelector('.notifications-icon .badge')
                        .then(function(bageNotification) {
                            bageNotification.isDisplayed().then(function(isDisplayed) {
                                assert.ok(isDisplayed, 'Bage Notification Indicator is showed in Navigation');
                            })
                        })
                        .end()
                    // Go to Notification page
                    .clickByCssSelector('.notifications-icon')
                    .clickLinkByText('View all')
                    // Notification Page is rendered
                    .waitForCssSelector('.notifications-page', 2000)
                    // There are one or more notifications on the page
                    .findByCssSelector('.notifications-page .row.notification')
                        .end()
                    .findByCssSelector('.notifications-icon .badge')
                        .then(function(bageNotification) {
                            bageNotification.isDisplayed().then(function(isDisplayed) {
                                assert.isFalse(isDisplayed, 'Bage Notification Indicator is not showed in Navigation');
                            })
                        })
                        .end();
            },
            'Notification bage behaviour': function() {
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
                    // Just in case - reset and hide bage Notification counter
                    .clickByCssSelector('.notifications-icon')
                    .then(function() {
                        return common.removeCluster(clusterName);
                    })
                    .findByCssSelector('.notifications-icon .badge')
                        .then(function(bageNotification) {
                            bageNotification.isDisplayed().then(function(isDisplayed) {
                                assert.ok(isDisplayed, 'Bage Notification Indicator appears in Navigation');
                            })
                        })
                        .end()
            }
        };
    });
});
