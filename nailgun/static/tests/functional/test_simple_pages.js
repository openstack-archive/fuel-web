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
    'tests/functional/pages/common'
], function(registerSuite, assert, Common) {
    'use strict';

    registerSuite(function() {
        var common;

        return {
            name: 'Simple Pages',
            setup: function() {
                common = new Common(this.remote);

                return this.remote
                    .then(function() {
                        return common.getIn();
                    })
            },
            'Installed Plugins Page is rendered correctly': function() {
                return this.remote
                    // Go to Support page
                    .clickLinkByText('Plugins')
                    .then(function() {
                        return common.assertElementExists('.plugins-page', 'Installed Plugins Page is present');
                    })
                    .findAllByCssSelector('.plugins-page a')
                        .then(function(elements) {
                            assert.ok(elements.length, 'Links showed on the Installed Plugins Page');
                        })
                        .end();
            },
            'Releases Page is rendered correctly': function() {
                return this.remote
                    // Go to Releases page
                    .clickLinkByText('Releases')
                    .then(function() {
                        return common.assertElementExists('.releases-page', 'Releases Page is present');
                    })
                    .findAllByCssSelector('.releases-page table tbody td')
                        .then(function(elements) {
                            assert.ok(elements.length, 'Some Release information are loaded');
                        })
                        .end();
            },
            'Notification Page is rendered correctly': function() {
                return this.remote
                    // Check that the Bage Notification Indicator is present
                    .findByCssSelector('.notifications-icon .badge')
                        .then(function(bageNotification) {
                            bageNotification.isEnabled().then(function(isEnabled) {
                                assert.ok(isEnabled, 'Bage Notification Indicator is showed in Navigation');
                            })
                        })
                        .end()
                    // Go to Notification page
                    .clickByCssSelector('.notifications-icon')
                    .clickLinkByText('View all')
                    .then(function() {
                        return common.assertElementExists('.notifications-page', 'Notification Page is present');
                    })
                    .findAllByCssSelector('.notifications-page .row.notification')
                        .then(function(elements) {
                            assert.ok(elements.length, 'There are one or more a notifications on the page');
                        })
                        .end()
                    .findByCssSelector('.notifications-icon .badge')
                        .then(function(bageNotification) {
                            bageNotification.isEnabled().then(function(isEnabled) {
                                assert.isFalse(isEnabled, 'Bage Notification Indicator is not showed in Navigation');
                            })
                        })
                        .end();
            },
            'Capacity Audit Page is rendered correctly': function() {
                return this.remote
                    // Go to Capacity Audit page
                    .clickLinkByText('Support')
                    .clickLinkByText('View Capacity Audit')
                    .waitForCssSelector('.capacity-page', 1000)
                    .findAllByCssSelector('.capacity-page .capacity-audit-table')
                        .then(function(elements) {
                            assert.ok(elements.length, 'Some Capacity Audit information are loaded');
                        })
                        .end()
                    .then(function() {
                        return common.assertElementExists('.capacity-page .btn', 'Download Report button is present');
                    });
            }
        };
    });
});
