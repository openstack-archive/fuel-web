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
                return this.remote
                    .findByCssSelector('.sticker select[name=source] > option')
                        // Check if "Source" dropdown exist
                        .end()
                    .then(function() {
                        return common.isElementDisabled('.sticker button', '"Show" button is disabled until source change');
                    })
                    .then(function() {
                        // Change the selected value for the "Source" dropdown to Rest API
                        return common.clickElement('.sticker select[name=source] option[value=api]');
                    })
                    .then(function() {
                        // Change the selected value for the "Level" dropdown to DEBUG
                        return common.clickElement('.sticker select[name=level] option[value=DEBUG]');
                    })
                    .then(function() {
                        return common.isElementEnabled('.sticker button', '"Show" button is enabled after source change');
                    })
                    .then(function() {
                        // Wait till Progress bar disappears
                        return common.waitForElementDeletion('.logs-tab div.progress');
                    })
                    .waitForCssSelector('.log-entries > tbody > tr', 5000)
                    .then(function() {
                        // "Other servers" option is present in "Logs" dropdown
                        return common.clickElement('.sticker select[name=type] > option[value=remote]');
                    })
                    .then(function() {
                        return common.elementExists('.sticker select[name=node] > option', '"Node" dropdown is present');
                    });
            }
        };
    });
});
