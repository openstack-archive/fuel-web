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
    'tests/functional/pages/common'
], function(registerSuite, Common) {
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
            'Installed Plugins Page': function() {
                return this.remote
                    // Go to installed Plugins page
                    .clickLinkByText('Plugins')
                    // Plugins page is rendered
                    .waitForCssSelector('.plugins-page', 1000)
                    .then(function() {
                        return common.assertElementExists('.plugins-page li a', 'Documentation links are present')
                    });
            },
            'Releases Page': function() {
                return this.remote
                    // Go to Releases page
                    .clickLinkByText('Releases')
                    // Releases page is rendered
                    .waitForCssSelector('.releases-page table', 2000);
            },
            'Capacity Audit Page': function() {
                return this.remote
                    // Go to Capacity Audit page
                    .clickLinkByText('Support')
                    .clickLinkByText('View Capacity Audit')
                    .waitForCssSelector('.capacity-page .capacity-audit-table', 2000)
                    .then(function() {
                        return common.assertElementExists('.capacity-page .btn', 'Download Report button is present');
                    });
            }
        };
    });
});
