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
    'tests/functional/pages/networks',
    'tests/functional/pages/cluster',
    'tests/functional/pages/modal'
], function(_, registerSuite, assert, Common, NetworksPage, ClusterPage, ModalWindow) {
    'use strict';

    registerSuite(function() {
        var common,
            networksPage,
            clusterPage,
            clusterName,
            initialValue,
            cidrElement,
            modal;

        return {
            name: 'Networks page',
            setup: function() {
                common = new Common(this.remote);
                networksPage = new NetworksPage(this.remote);
                clusterPage = new ClusterPage(this.remote);
                modal = new ModalWindow(this.remote);

                return this.remote
                    .then(function() {
                        return common.getIn();
                    });
            },
            beforeEach: function() {
                clusterName = common.pickRandomName('Test Cluster');
                return this.remote
                    .setFindTimeout(2000)
                    .then(function() {
                        return common.createCluster(
                            clusterName,
                            {
                                Compute: function() {
                                    // Selecting VCenter
                                    return this.remote
                                        .setFindTimeout(2000)
                                        .findByCssSelector('.custom-tumbler input[name=vcenter]')
                                            .click()
                                            .end();
                                }
                            }
                        );
                    })
                    .then(function() {
                        return clusterPage.goToTab('Networks');
                    })
                    .then(function() {
                        cidrElement = networksPage.getCidrElement();
                        return cidrElement;
                    })
                    .then(function() {
                        return cidrElement.getAttribute('value')
                            .then(function(initValue) {
                                initialValue = initValue;
                                return initialValue;
                            })
                            .end();
                    });
            },
            afterEach: function() {
                return this.remote
                    .then(function() {
                        return clusterPage.goToTab('Dashboard');
                    })
                    .then(function() {
                        return modal.clickFooterButton('Discard Changes');
                    })
                    .then(function() {
                        return common.removeCluster(clusterName, true);
                    });
            },

            'Network Tab is rendered correctly': function() {
                return this.remote
                    .setFindTimeout(5000)
                    //tab is rendered
                    .findByCssSelector('.network-tab')
                        .then(function(networkTab) {
                            return networkTab.isDisplayed().then(function(isDisplayed) {
                                assert.ok(isDisplayed, 'Network tab is present');
                            });
                        })
                        .end()
                    //Network manager options are presented
                    .findByCssSelector('.nova-managers .radio-group')
                        .then(function(radioGroupWrapper) {
                            return radioGroupWrapper.isDisplayed().then(function(isDisplayed) {
                                assert.ok(isDisplayed, 'Nova Network manager radiogroup is present');
                            });
                        })
                        .end()
                    .findAllByCssSelector('.checkbox-group input[name=net_provider]')
                        .then(function(radioGroup) {
                            assert.equal(radioGroup.length, 2, 'Network manager options are presented');
                        })
                        .end()
                    //Flat DHCP manager is chosen
                    .findByCssSelector('input[value=FlatDHCPManager]')
                        .then(function(flatDHCPManager) {
                            flatDHCPManager.isSelected().then(function(isSelected) {
                                assert.ok(isSelected, 'Flat DHCP manager is chosen');
                            })
                        })
                        .end()
                    //All networks are presented
                    .findAllByCssSelector('.network-tab h3')
                        .then(function(networkSections) {
                            assert.equal(networkSections.length, 4, 'All networks are presented');
                        })
                        .end();
            },

            'Testing cluster networks: Save button interactions': function() {
                return this.remote
                    .then(function() {
                        return common.setInputValue('.storage input[name=cidr]', '240.0.1.0/25');
                    })
                    // apply btn
                    .then(function() {
                        return networksPage.isApplyButtonEnabled()
                            .then(function(isEnabled) {
                                assert.ok(isEnabled, 'Save networks button is enabled if there are changes');
                            })
                            .end();
                    })
                    .then(function() {
                        return common.setInputValue('.storage input[name=cidr]', initialValue);
                    })
                    .then(function() {
                        return networksPage.isApplyButtonEnabled()
                            .then(function(isEnabled) {
                                assert.isFalse(isEnabled, 'Save networks button is disabled again if there are no changes');
                            })
                    })
            },

            'Testing cluster networks: change network manager': function() {
                return this.remote
                    .setFindTimeout(5000)
                    .findByCssSelector('input[name=net_provider]:not(:checked)')
                        .click()
                        .end()
                    .findAllByCssSelector('input[name=fixed_networks_amount]')
                        .then(function(elements) {
                            assert.equal(elements.length, 1, 'Amount field for a fixed network is presented in VLAN mode');
                        })
                        .end()
                    .findAllByCssSelector('select[name=fixed_network_size]')
                        .then(function(elements) {
                            assert.equal(elements.length, 1, 'Size field for a fixed network is presented in VLAN mode');
                        })
                        .end()
                    .then(function() {
                        return networksPage.isApplyButtonEnabled()
                            .then(function(isEnabled) {
                                assert.ok(isEnabled, 'Save networks button is enabled after manager was changed');
                            })
                            .end()
                    })
                        .findByCssSelector('input[name=net_provider]:not(:checked)')
                        .click()
                        .end()
                    .findAllByCssSelector('input[name=fixed_networks_amount]')
                        .then(function(elements) {
                            assert.notOk(elements.length, 'Amount field was hidden after revert to FlatDHCP');
                        })
                        .end()
                    .findAllByCssSelector('select[name=fixed_network_size]')
                        .then(function(elements) {
                            assert.notOk(elements.length, 'Size field was hidden after revert to FlatDHCP');
                        })
                        .end()
                    .then(function() {
                        return networksPage.isApplyButtonEnabled()
                            .then(function(isEnabled) {
                                assert.isFalse(isEnabled, 'Save networks button is disabled again after revert to FlatDHCP');
                            })
                    });
            },

            'Testing cluster networks: VLAN range fields': function() {
                return this.remote
                    .setFindTimeout(5000)
                    .findByCssSelector('input[name=net_provider]:not(:checked)')
                        .click()
                        .end()
                    .findAllByCssSelector('.network-section-wrapper input[name=range-end_fixed_networks_vlan_start]')
                        .then(function(elements) {
                            assert.equal(elements.length, 1, 'VLAN range is displayed')
                        })
                        .end()
                    .findByCssSelector('input[name=net_provider]:not(:checked)')
                        .click()
                        .end();
            },

            'Testing cluster networks: save changes': function() {
                return this.remote
                    .setFindTimeout(5000)
                    .findByCssSelector('input[name=net_provider]:not(:checked)')
                        .click()
                        .end()
                    .then(function() {
                        return networksPage.getApplyButton()
                            .click()
                            .end()
                    })
                    .findAllByCssSelector('input:not(:disabled)')
                        .then(function(elements) {
                            assert.ok(elements.length, 'Input is not disabled');
                        })
                        .end()
                    .findAllByCssSelector('.alert-error')
                        .then(function(elements) {
                            assert.notOk(elements.length, 'Correct settings were saved successfully');
                        })
                        .end();
            },

            'Testing cluster networks: verification': function() {
                return this.remote
                    .findByCssSelector('.verify-networks-btn:not(:disabled)')
                        .click()
                        .end()
                    .setFindTimeout(2000)
                    .findAllByCssSelector('.connect-3.error')
                        .then(function(elements) {
                            assert.equal(elements.length, 1, 'At least two nodes are required to be in the environment for network verification.')
                        })
                        .end()
                    // Testing cluster networks: verification task deletion
                    .findByCssSelector('input[name=net_provider]:not(:checked)')
                        .click()
                        .end()
                    .findAllByCssSelector('.page-control-box .alert')
                        .then(function(elements) {
                            assert.notOk(elements.length, 'Verification task was removed after settings has been changed');
                        })
                        .end()
                    .findByCssSelector('input[name=net_provider]:not(:checked)')
                        .click()
                        .end();
            },

            'Check VlanID field validation': function() {
                return this.remote
                    .findByCssSelector('.management input[type=checkbox]')
                        .click()
                        .end()
                    .findByCssSelector('.management input[type=checkbox]')
                        .click()
                        .end()
                    .findAllByCssSelector('.management .has-error input[name=vlan_start]')
                    .then(function(elements) {
                        assert.equal(elements.length, 1, 'Field validation has worked properly in case of empty value');
                    })
                    .end();
            },

            'Testing cluster networks: data validation': function() {
                return this.remote
                    .findByCssSelector('.network-section-wrapper input[name=fixed_networks_vlan_start]')
                        .click()
                        .end()
                    .findByCssSelector('input[name=net_provider]:not(:checked)')
                        .click()
                        .end()
                    .findAllByCssSelector('.network-section-wrapper .has-error input[name=range-start_fixed_networks_vlan_start]')
                        .then(function(elements) {
                            assert.equal(elements.length, 1, 'Field validation has worked');
                        })
                        .end()
                    .then(function() {
                        return networksPage.isApplyButtonEnabled()
                            .then(function(isEnabled) {
                                assert.isFalse(isEnabled, 'Save networks button is disabled if there is validation error');
                            })
                            .end()
                    })
                    .findByCssSelector('input[name=net_provider]:not(:checked)')
                        .click()
                        .end()
                    .findByCssSelector('.network-section-wrapper input[name=fixed_networks_vlan_start]')
                        .click()
                        .end()
                    .findAllByCssSelector('.network-section-wrapper .has-error input[name=range-start_fixed_networks_vlan_start]')
                        .then(function(elements) {
                            assert.equal(elements.length, 0, 'Field validation works properly');
                        })
                        .end();
            }

        };
    });
});
