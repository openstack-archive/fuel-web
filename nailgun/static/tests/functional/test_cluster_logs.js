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
                var showLogsButtonSelector = '.sticker button';
                return this.remote
                    .findByCssSelector('.sticker select[name=source] > option')
                        // Check if "Source" dropdown exist
                        .end()
                    .then(function() {
                        return common.assertElementDisabled(showLogsButtonSelector, '"Show" button is disabled until source change');
                    })
                    // Change the selected value for the "Source" dropdown to Rest API
                    .clickByCssSelector('.sticker select[name=source] option[value=api]')
                    // Change the selected value for the "Level" dropdown to DEBUG
                    .clickByCssSelector('.sticker select[name=level] option[value=DEBUG]')
                    .then(function() {
                        return common.assertElementEnabled(showLogsButtonSelector, '"Show" button is enabled after source change');
                    })
                    .clickByCssSelector(showLogsButtonSelector)
                    // Wait till Progress bar disappears
                    .waitForElementDeletion('.logs-tab div.progress', 5000)
                    .waitForCssSelector('.log-entries > tbody > tr', 5000)
                    // "Other servers" option is present in "Logs" dropdown
                    .clickByCssSelector('.sticker select[name=type] > option[value=remote]')
                    .then(function() {
                        return common.assertElementExists('.sticker select[name=node] > option', '"Node" dropdown is present');
                    });
            }
        };
    });
});
