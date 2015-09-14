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
    'tests/functional/pages/interfaces',
    'tests/functional/pages/cluster',
    'tests/functional/pages/common'
], function(registerSuite, assert, helpers, InterfacesPage, ClusterPage, Common) {
    'use strict';

    registerSuite(function() {
        var common,
            clusterPage,
            interfacesPage,
            clusterName;

        return {
            name: 'Node Interfaces',
            setup: function() {
                common = new Common(this.remote);
                clusterPage = new ClusterPage(this.remote);
                interfacesPage = new InterfacesPage(this.remote);
                clusterName = common.pickRandomName('Test Cluster');

                return this.remote
                    .then(function() {
                        return common.getIn();
                    })
                    .then(function() {
                        return common.createCluster(clusterName);
                    });
            },
            beforeEach: function() {
                return this.remote
                    .then(function() {
                        return common.addNodesToCluster(1, 'Controller', 'Supermicro X9SCD')
                    })
                    .findByCssSelector('.node.pending_addition input[type=checkbox]:not(:checked)')
                        .click()
                        .end()
                    .findByCssSelector('button.btn-configure-interfaces')
                        .click()
                        .end()
                    .findByCssSelector('div.ifc-list')
                        .end()

            },
            afterEach: function() {
                return this.remote
                    .clickOnElement('.btn-defaults');
            },
            teardown: function() {
                return this.remote
                    .then(function() {
                        return common.removeCluster(clusterName, true);
                    });
            },
//            'Untagged networks error': function() {
//                return this.remote
//                    .then(function() {
//                        return interfacesPage.assignNetworkToInterface('Public', 'eth0');
//                    })
//                    .then(function() {
//                        return common.elementExists('div.ifc-error', 'Untagged networks can not be assigned to the same interface message should appear');
//                    });
//            },
//            'Bond interfaces with different speeds': function() {
//                return this.remote
//                    .then(function() {
//                        return interfacesPage.selectInterface('eth2');
//                    })
//                    .then(function() {
//                        return interfacesPage.selectInterface('eth3');
//                    })
//                    .then(function() {
//                        return common.elementExists('div.alert.alert-warning', 'Interfaces with different speeds bonding not recommended message should appear');
//                    })
//                    .then(function() {
//                        return common.isElementEnabled('.btn-bond', 'Bonding button should still be enabled')
//                    });
//            },
            'Interfaces bonding': function() {
                return this.remote
                    .then(function() {
                        return interfacesPage.bondInterfaces('eth1', 'eth2');
                    })
                    .then(function() {
                        return interfacesPage.checkBondInterfaces('bond0', ['eth1', 'eth2']);
                    })
                    .then(function() {
                        return interfacesPage.bondInterfaces('bond0', 'eth5');
                    })
                    .then(function() {
                        return interfacesPage.checkBondInterfaces('bond0', ['eth1', 'eth2', 'eth5']);
                    });
            }
    }});
});
