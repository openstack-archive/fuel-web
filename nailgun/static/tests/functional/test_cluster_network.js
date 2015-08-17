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
    'underscore',
    'intern!object',
    'intern/chai!assert',
    'tests/functional/pages/common',
    'tests/functional/pages/networks'
], function(_, registerSuite, assert, Common, NetworksPage) {
    'use strict';

    registerSuite(function() {
        var common,
            networksPage,
            clusterName;

        return {
            name: 'Networks page',
            setup: function() {
                common = new Common(this.remote);
                networksPage = new NetworksPage(this.remote);
                clusterName = 'Test Cluster #' + Math.round(99999 * Math.random());
            },
            beforeEach: function() {
                return this.remote
                    .then(function() {
                        return common.getIn();
                    })
                    .then(function() {
                        return common.createVCenterNovaCluster(clusterName);
                    });
            },
            afterEach: function() {
                return this.remote
                    .then(function() {
                        return common.removeCluster(clusterName, true);
                    });
            },
            'Network Tab appears': function() {
                return this.remote
                    .then(function() {
                        return common.goToTab('networks');
                    })
                    .setFindTimeout(5000)
                    .findByCssSelector('.checkbox-group input[name=net_provider]')
                    .then(function(checkbox) {
                        return applyButton.isDisplayed().then(function(isDisplayed) {
                            assert.ok(isDisplayed, 'Network manager checkbox is present');
                            return true;
                        });
                    })
                    .end()

                //this.test.assertEvalEquals(function() {return $('.checkbox-group input[name=net_provider]').length}, 2, 'Network manager options are presented');
                //this.test.assertExists('input[value=FlatDHCPManager]:checked', 'Flat DHCP manager is chosen');
                //this.test.assertEvalEquals(function() {return $('.network-tab h3').length}, 4, 'All networks are presented');
                //this.test.assertDoesntExist('.verify-networks-btn:disabled', 'Verify networks button is enabled');
                //this.test.assertExists('.apply-btn:disabled', 'Save networks button is disabled');
                //
                //
                //this.test.assertEvalEquals(function() {return $('.checkbox-group input[name=net_provider]').length}, 2, 'Network manager options are presented');
                //this.test.assertExists('input[value=FlatDHCPManager]:checked', 'Flat DHCP manager is chosen');
                //this.test.assertEvalEquals(function() {return $('.network-tab h3').length}, 4, 'All networks are presented');
                //this.test.assertDoesntExist('.verify-networks-btn:disabled', 'Verify networks button is enabled');
                //this.test.assertExists('.apply-btn:disabled', 'Save networks button is disabled');

                .then(function(result) {
                        assert.notOk(result, 'Networks tab successfully rendered');
                    });
            }
        };
    });
});
