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
    'tests/helpers',
    'tests/functional/pages/common',
    'tests/functional/pages/networks',
    'tests/functional/pages/cluster'
], function(_, registerSuite, assert, helpers, Common, NetworksPage, ClusterPage) {
    'use strict';

    registerSuite(function() {
        var common,
            networksPage,
            clusterPage,
            clusterName;

        return {
            name: 'Networks page',
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
                    .findByCssSelector('.network-tab')
                        .then(function(networkTab) {
                            return networkTab.isDisplayed().then(function(isDisplayed) {
                                assert.ok(isDisplayed, 'Network tab is present');
                            });
                        })
                        .end()
                    .then(function() {
                        return common.assertElementExists('.nova-managers .radio-group',
                            'Nova Network manager radiogroup is present');
                    })
                    .findAllByCssSelector('.checkbox-group input[name=net_provider]')
                        .then(function(radioGroup) {
                            assert.equal(radioGroup.length, 2, 'Network manager options are present');
                        })
                        .end()
                    .findByCssSelector('input[value=FlatDHCPManager]')
                        .then(function(flatDHCPManager) {
                            flatDHCPManager.isSelected().then(function(isSelected) {
                                assert.ok(isSelected, 'Flat DHCP manager is chosen');
                            })
                        })
                        .end()
                    .findAllByCssSelector('.network-tab h3')
                        .then(function(networkSections) {
                            assert.equal(networkSections.length, 4, 'All networks are present');
                        })
                        .end();
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
                    // Save changes button is enabled if there are changes
                    .waitForCssSelector(networksPage.applyButtonSelector + ':not(:disabled)', 200)
                    .then(function() {
                        return self.remote.setInputValue(cidrElementSelector, cidrInitialValue);
                    })
                    // Save changes button is disabled again if there are no changes
                    .waitForCssSelector(networksPage.applyButtonSelector + ':disabled', 200);
            },
            'Testing cluster networks: change network manager': function() {
                var amountSelector = 'input[name=fixed_networks_amount]',
                    sizeSelector = 'select[name=fixed_network_size]';
                return this.remote
                    .then(function() {
                        return networksPage.switchNetworkManager();
                    })
                    .then(function() {
                        return common.assertElementExists(amountSelector,
                            'Amount field for a fixed network is present in VLAN mode');
                    })
                    .then(function() {
                        return common.assertElementExists(sizeSelector,
                            'Size field for a fixed network is present in VLAN mode');
                    })
                    .then(function() {
                        return common.assertElementEnabled(networksPage.applyButtonSelector,
                            'Save changes button is enabled after manager was changed');
                    })
                    .then(function() {
                        return networksPage.switchNetworkManager();
                    })
                    .then(function() {
                        return common.assertElementNotExists(amountSelector,
                            'Amount field was hidden after revert to FlatDHCP');
                    })
                    .then(function() {
                        return common.assertElementNotExists(sizeSelector,
                            'Size field was hidden after revert to FlatDHCP');
                    })
                    .then(function() {
                        return common.assertElementDisabled(networksPage.applyButtonSelector,
                            'Save changes button is disabled again after revert to FlatDHCP');
                    });
            },
            'Testing cluster networks: VLAN range fields': function() {
                return this.remote
                    .then(function() {
                        return networksPage.switchNetworkManager();
                    })
                    .then(function() {
                        return common.assertElementExists('.network-section-wrapper input[name=range-end_fixed_networks_vlan_start]',
                            'VLAN range is displayed');
                    });
            },
            'Testing cluster networks: save changes': function() {
                return this.remote
                    .then(function() {
                        return networksPage.switchNetworkManager();
                    })
                    .clickByCssSelector(networksPage.applyButtonSelector)
                    // Inputs are not disabled
                    .waitForCssSelector('input:not(:disabled)', 2000)
                    .then(function() {
                        return common.assertElementNotExists('.alert-error',
                            'Correct settings were saved successfully');
                    });
            },
            'Testing cluster networks: verification': function() {
                return this.remote
                    .clickByCssSelector('.verify-networks-btn:not(:disabled)')
                    // At least two nodes are required to be in the environment for network verification
                    .waitForCssSelector('.connect-3.error', 2000)
                    // Testing cluster networks: verification task deletion
                    .then(function() {
                        return networksPage.switchNetworkManager();
                    })
                    .then(function() {
                        return common.assertElementNotExists('.page-control-box .alert',
                            'Verification task was removed after settings has been changed');
                    });
            },
            'Check VlanID field validation': function() {
                return this.remote
                    .findByCssSelector('.management input[type=checkbox]')
                        .click()
                        .click()
                        .end()
                    .then(function() {
                        return common.assertElementExists('.management .has-error input[name=vlan_start]',
                            'Field validation has worked properly in case of empty value');
                    });
            },
            'Testing cluster networks: data validation': function() {
                return this.remote
                    .then(function() {
                        return networksPage.switchNetworkManager();
                    })
                    .clickByCssSelector('.network-section-wrapper input[name=fixed_networks_vlan_start][type=checkbox]')
                    .then(function() {
                        return networksPage.switchNetworkManager();
                    })
                    .then(function() {
                        return common.assertElementExists('.network-section-wrapper .has-error input[name=range-start_fixed_networks_vlan_start][type=text]',
                            'Field validation has worked');
                    })
                    .then(function() {
                        return common.assertElementDisabled(networksPage.applyButtonSelector, 'Save changes button is disabled if there is validation error');
                    })
                    .then(function() {
                        return networksPage.switchNetworkManager();
                    })
                    .clickByCssSelector('.network-section-wrapper input[name=fixed_networks_vlan_start][type=checkbox]')
                    .then(function() {
                        return common.assertElementNotExists('.network-section-wrapper .has-error input[name=range-start_fixed_networks_vlan_start][type=text]',
                            'Field validation works properly');
                    });
            }
        };
    });
});
