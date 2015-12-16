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
            name: 'GUI support for Ironic',
            setup: function() {
                // Login to Fuel UI
                common = new Common(this.remote);
                clusterPage = new ClusterPage(this.remote);

                return this.remote
                    .then(function() {
                        return common.getIn();
                    });
            },
            beforeEach: function() {
                // Create cluster with additional service "Ironic"
                clusterName = common.pickRandomName('Ironic Cluster');
                return this.remote
                    .then(function() {
                        return common.createCluster(
                            clusterName,
                            {
                                'Additional Services': function() {
                                    return this.remote
                                        .clickByCssSelector('input[value=additional_service\\:ironic]');
                                }
                            }
                        );
                    });
            },
            afterEach: function() {
                // Remove tested "Ironic" cluster
                return this.remote
                    .then(function() {
                        return common.removeCluster(clusterName);
                    });
            },
            'T2199263: Check Ironic item on Settings tab': function() {
                return this.remote
                    // Go to "Settings" tab
                    .then(function() {
                        return clusterPage.goToTab('Settings');
                    })
                    // Go to "OpenStack Services" subtab
                    .clickLinkByText('OpenStack Services')
                    // Check "Ironic" item is selected
                    .assertElementExists('input[name=ironic]', 'Ironic item is not existed')
                    .assertElementEnabled('input[name=ironic]', 'Ironic item is not enabled')
                    .assertElementAttributeEquals('input[name=ironic]', 'value', 'true', 'Ironic item is not selected');
            }
        };
    });
});
