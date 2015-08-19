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
            clusterName
        return {
            name: 'Logs Tab',
            setup: function() {
                common = new Common(this.remote);
                clusterPage = new ClusterPage(this.remote);
                clusterName = 'Test Cluster #' + Math.round(99999 * Math.random());
            },
            beforeEach: function() {
                return this.remote
                    .then(function() {
                        return common.getIn();
                    })
                    .then(function() {
                        return common.createCluster(clusterName);
                    })
                    .then(function() {
                        return clusterPage.addClusterNode();
                    });
            },
            afterEach: function() {
                return this.remote
                    .then(function() {
                        return common.removeCluster(clusterName, true);
                    });
            },
            'Test Logs Tab': function() {
                var showLogsButton;
                return this.remote
                    .then(function() {
                        return clusterPage.goToTab('Logs');
                    })
                    .setFindTimeout(5000)
                    .findByCssSelector('.sticker select[name=source] > option')
                        .end() // "Source" dropdown exist
                    .findByCssSelector('.sticker button')
                        .then(function(button) {
                            showLogsButton = button;
                            return showLogsButton.isEnabled().then(function(isEnabled) {
                                assert.isFalse(isEnabled, '"Show" button is disabled until source shange');
                                return true;
                            });
                        })
                        .end() // "Show" button is disabled till "Source" dropdown changed
                    .findByCssSelector('.sticker select[name=source] option[value=receiverd]')
                        .click()
                        .end() // Change the selected value for the "Source" dropdown
                    .then(function() {
                        showLogsButton.click(); // It is possible to click "Show" button now
                    })
                    .setFindTimeout(5000)
                    .findByCssSelector('.log-entries tr:first-child td:last-child')
                        .end() // Log tab entries are presented
                    .findByCssSelector('.sticker select[name=type] > option[value=remote]')
                        .click()
                        .end() // "Other servers" option is presented in "Logs" dropdown
                    .findByCssSelector('.sticker select[name=node] > option')
                        .end(); // "Node" dropdown is presented
            }
        };
    });
});
