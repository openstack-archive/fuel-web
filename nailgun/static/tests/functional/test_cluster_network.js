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
    'intern/dojo/node!lodash',
    'intern!object',
    'intern/chai!assert',
    'tests/functional/pages/common',
    'tests/functional/pages/networks',
    'tests/functional/pages/cluster'
], function(_, registerSuite, assert, Common, NetworksPage, ClusterPage) {
    'use strict';

    registerSuite(function() {
        var common,
            networksPage,
            clusterPage,
            clusterName;

        return {
            name: 'Networks page Nova Network tests',
            setup: function() {
                common = new Common(this.remote);
                networksPage = new NetworksPage(this.remote);
                clusterPage = new ClusterPage(this.remote);
                clusterName = common.pickRandomName('Test Cluster');

                return this.remote
                    .then(function() {
                        return common.getIn();
                    })
                    .then(function() {
                        return common.createCluster(
                            clusterName,
                            {
                                Compute: function() {
                                    // select VCenter to enable Nova networking
                                    return this.remote
                                        .clickByCssSelector('input[name=vcenter]');
                                },
                                'Networking Setup': function() {
                                    return this.remote
                                        .clickByCssSelector('input[name=manager][value=nova-network]');
                                }
                            }
                        );
                    })
                    .then(function() {
                        return clusterPage.goToTab('Networks');
                    });
            },
            afterEach: function() {
                return this.remote
                    .clickByCssSelector('.btn-revert-changes');
            },
            'Network Tab is rendered correctly': function() {
                return this.remote
                    .assertElementExists('.nova-managers .radio-group', 'Nova Network manager radiogroup is present')
                    .assertElementsExist('.checkbox-group input[name=net_provider]', 2, 'Network manager options are present')
                    .assertElementSelected('input[value=FlatDHCPManager]', 'Flat DHCP manager is chosen')
                    .assertElementsExist('.network-tab h3', 4, 'All networks are present');
            },
            'Testing cluster networks: Save button interactions': function() {
                var self = this,
                    cidrInitialValue,
                    cidrElementSelector = '.storage input[name=cidr]';
                return this.remote
                    .findByCssSelector(cidrElementSelector)
                        .then(function(element) {
                            return element.getAttribute('value')
                                .then(function(value) {
                                    cidrInitialValue = value;
                                });
                        })
                        .end()
                    .setInputValue(cidrElementSelector, '240.0.1.0/25')
                    .assertElementAppears(networksPage.applyButtonSelector + ':not(:disabled)', 200,
                        'Save changes button is enabled if there are changes')
                    .then(function() {
                        return self.remote.setInputValue(cidrElementSelector, cidrInitialValue);
                    })
                    .assertElementAppears(networksPage.applyButtonSelector + ':disabled', 200,
                        'Save changes button is disabled again if there are no changes');
            },
            'Testing cluster networks: change network manager': function() {
                var amountSelector = 'input[name=fixed_networks_amount]',
                    sizeSelector = 'select[name=fixed_network_size]';
                return this.remote
                    .then(function() {
                        return networksPage.switchNetworkManager();
                    })
                    .assertElementExists(amountSelector, 'Amount field for a fixed network is present in VLAN mode')
                    .assertElementExists(sizeSelector, 'Size field for a fixed network is present in VLAN mode')
                    .assertElementEnabled(networksPage.applyButtonSelector, 'Save changes button is enabled after manager was changed')
                    .then(function() {
                        return networksPage.switchNetworkManager();
                    })
                    .assertElementNotExists(amountSelector, 'Amount field was hidden after revert to FlatDHCP')
                    .assertElementNotExists(sizeSelector, 'Size field was hidden after revert to FlatDHCP')
                    .assertElementDisabled(networksPage.applyButtonSelector, 'Save changes button is disabled again after revert to FlatDHCP');
            },
            'Testing cluster networks: VLAN range fields': function() {
                return this.remote
                    .then(function() {
                        return networksPage.switchNetworkManager();
                    })
                    .assertElementExists('input[name=range-end_fixed_networks_vlan_start]', 'VLAN range is displayed');
            },
            'Testing cluster networks: save changes': function() {
                return this.remote
                    .then(function() {
                        return networksPage.switchNetworkManager();
                    })
                    .clickByCssSelector(networksPage.applyButtonSelector)
                    .assertElementsAppear('input:not(:disabled)', 2000, 'Inputs are not disabled')
                    .assertElementNotExists('.alert-error', 'Correct settings were saved successfully')
            },
            'Testing cluster networks: verification': function() {
                return this.remote
                    .clickByCssSelector('.verify-networks-btn:not(:disabled)')
                    .assertElementAppears('.connect-3.error', 2000,
                        'At least two nodes are required to be in the environment for network verification')
                    // Testing cluster networks: verification task deletion
                    .then(function() {
                        return networksPage.switchNetworkManager();
                    })
                    .assertElementNotExists('.page-control-box .alert', 'Verification task was removed after settings has been changed');
            },
            'Check VlanID field validation': function() {
                return this.remote
                    .clickByCssSelector('.management input[type=checkbox]')
                    .clickByCssSelector('.management input[type=checkbox]')
                    .assertElementExists('.management .has-error input[name=vlan_start]',
                        'Field validation has worked properly in case of empty value');
            },
            'Testing cluster networks: data validation': function() {
                return this.remote
                    .then(function() {
                        return networksPage.switchNetworkManager();
                    })
                    .clickByCssSelector('input[name=fixed_networks_vlan_start][type=checkbox]')
                    .then(function() {
                        return networksPage.switchNetworkManager();
                    })
                    .assertElementExists('.has-error input[name=range-start_fixed_networks_vlan_start][type=text]',
                            'Field validation has worked')
                    .assertElementDisabled(networksPage.applyButtonSelector,
                        'Save changes button is disabled if there is validation error')
                    .then(function() {
                        return networksPage.switchNetworkManager();
                    })
                    .clickByCssSelector('input[name=fixed_networks_vlan_start][type=checkbox]')
                    .assertElementNotExists('.has-error input[name=range-start_fixed_networks_vlan_start][type=text]',
                            'Field validation works properly');
            }
        };
    });

    registerSuite(function() {
        var common,
            networksPage,
            clusterPage,
            clusterName;

        return {
            name: 'Networks page Neutron tests',
            setup: function() {
                common = new Common(this.remote);
                networksPage = new NetworksPage(this.remote);
                clusterPage = new ClusterPage(this.remote);
                clusterName = common.pickRandomName('Test Cluster');

                return this.remote
                    .then(function() {
                        return common.getIn();
                    })
                    .then(function() {
                        return common.createCluster(
                            clusterName,
                            {
                                'Networking Setup': function() {
                                    return this.remote
                                        .clickByCssSelector('input[name=manager][value=neutron-tun]');
                                }
                            }
                        );
                    })
                    .then(function() {
                        return clusterPage.goToTab('Networks');
                    });
            },
            afterEach: function() {
                return this.remote
                    .clickByCssSelector('.btn-revert-changes');
            },
            'Add ranges manipulations': function() {
                var rangeSelector = '.public .ip_ranges ';
                return this.remote
                    .clickByCssSelector(rangeSelector + '.ip-ranges-add')
                    .assertElementsExist(rangeSelector + '.ip-ranges-delete', 2, 'Remove ranges controls appear')
                    .clickByCssSelector(networksPage.applyButtonSelector)
                    .assertElementsExist(rangeSelector + '.range-row',
                            'Empty range row is removed after saving changes')
                    .assertElementNotExists(rangeSelector + '.ip-ranges-delete',
                            'Remove button is absent for only one range');
            },
            'DNS nameservers manipulations': function() {
                var dnsNameserversSelector = '.dns_nameservers ';
                return this.remote
                    .clickByCssSelector(dnsNameserversSelector + '.ip-ranges-add')
                    .assertElementExists(dnsNameserversSelector + '.range-row .has-error',
                            'New nameserver is added and contains validation error');
            },
            'Segmentation types differences': function() {
                return this.remote
                    // Tunneling segmentation tests
                    .assertElementExists('.private',
                            'Private Network is visible for tunneling segmentation type')
                    .assertElementTextEquals('.segmentation-type', 'Neutron with tunneling segmentation',
                            'Segmentation type is correct for tunneling segmentation')
                    // Vlan segmentation tests
                    .clickLinkByText('Environments')
                    .then(function() {
                        return common.createCluster('Test vlan segmentation');
                    })
                    .then(function() {
                        return clusterPage.goToTab('Networks');
                    })
                    .assertElementNotExists('.private', 'Private Network is not visible for vlan segmentation type')
                    .assertElementTextEquals('.segmentation-type', 'Neutron with VLAN segmentation',
                            'Segmentation type is correct for VLAN segmentation');
            }
        };
    });
});
