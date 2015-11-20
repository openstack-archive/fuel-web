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
    'tests/functional/pages/cluster',
    'tests/functional/pages/modal'
], function(_, registerSuite, assert, Common, NetworksPage, ClusterPage, ModalWindow) {
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
                    .assertElementsExist('.network-tab h3', 3, 'All networks are present');
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
                    .clickByCssSelector('.subtab-link-nova_configuration')
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
            'Testing cluster networks: network notation change': function() {
                return this.remote
                    .clickByCssSelector('.subtab-link-default')
                    .assertElementAppears('.storage', 2000, 'Storage network is shown')
                    .assertElementSelected('.storage .cidr input[type=checkbox]', 'Storage network has "cidr" notation by default')
                    .assertElementNotExists('.storage .ip_ranges input[type=text]:not(:disabled)', 'It is impossible to configure IP ranges for network with "cidr" notation')
                    .clickByCssSelector('.storage .cidr input[type=checkbox]')
                    .assertElementNotExists('.storage .ip_ranges input[type=text]:disabled', 'Network notation was changed to "ip_ranges"');
            },
            'Testing cluster networks: VLAN range fields': function() {
                return this.remote
                    .then(function() {
                        return networksPage.switchNetworkManager();
                    })
                    .clickByCssSelector('.subtab-link-nova_configuration')
                    .assertElementAppears('input[name=range-end_fixed_networks_vlan_start]', 2000, 'VLAN range is displayed');
            },
            'Testing cluster networks: save network changes': function() {
                return this.remote
                    .then(function() {
                        return networksPage.switchNetworkManager();
                    })
                    .clickByCssSelector(networksPage.applyButtonSelector)
                    .assertElementsAppear('input:not(:disabled)', 2000, 'Inputs are not disabled')
                    .assertElementNotExists('.alert-error', 'Correct settings were saved successfully')
            },
            'Testing cluster networks: save settings with group: network': function() {
                return this.remote
                    .clickByCssSelector('.subtab-link-network_settings')
                    .clickByCssSelector('input[name=auto_assign_floating_ip][type=checkbox]')
                    .clickByCssSelector(networksPage.applyButtonSelector)
                    .assertElementsAppear('input:not(:disabled)', 2000, 'Inputs are not disabled')
                    .assertElementDisabled(networksPage.applyButtonSelector, 'Save changes button is disabled again after successfull settings saving');
            },
            'Testing cluster networks: verification': function() {
                return this.remote
                    .clickByCssSelector('.subtab-link-network_verification')
                    .clickByCssSelector('.verify-networks-btn:not(:disabled)')
                    .assertElementAppears('.connect-3.error', 2000,
                        'At least two nodes are required to be in the environment for network verification')
                    // Testing cluster networks: verification task deletion
                    .then(function() {
                        return networksPage.switchNetworkManager();
                    })
                    .clickByCssSelector('.subtab-link-network_verification')
                    .assertElementNotExists('.page-control-box .alert', 'Verification task was removed after settings has been changed');
            },
            'Check VlanID field validation': function() {
                return this.remote
                    .clickByCssSelector('.subtab-link-default')
                    .assertElementAppears('.management', 2000, 'Management network appears')
                    .clickByCssSelector('.management .vlan-tagging input[type=checkbox]')
                    .clickByCssSelector('.management .vlan-tagging input[type=checkbox]')
                    .assertElementExists('.management .has-error input[name=vlan_start]',
                        'Field validation has worked properly in case of empty value');
            },
            'Testing cluster networks: data validation': function() {
                return this.remote
                    .then(function() {
                        return networksPage.switchNetworkManager();
                    })
                    .clickByCssSelector('.subtab-link-nova_configuration')
                    .assertElementAppears('input[name=fixed_networks_vlan_start][type=checkbox]', 2000, 'Vlan range appearsse')
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
                    .clickByCssSelector('.subtab-link-neutron_l3')
                    .clickByCssSelector(dnsNameserversSelector + '.ip-ranges-add')
                    .assertElementExists(dnsNameserversSelector + '.range-row .has-error',
                            'New nameserver is added and contains validation error');
            },
            'Segmentation types differences': function() {
                return this.remote
                    .clickByCssSelector('.subtab-link-default')
                    // Tunneling segmentation tests
                    .assertElementExists('.private',
                            'Private Network is visible for tunneling segmentation type')
                    .assertElementTextEquals('.segmentation-type', '(Neutron with tunneling segmentation)',
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
                    .assertElementTextEquals('.segmentation-type', '(Neutron with VLAN segmentation)',
                            'Segmentation type is correct for VLAN segmentation');
            }
        };
    });

    registerSuite(function() {
        var common,
            clusterPage,
            clusterName,
            modal;

        return {
            name: 'Networks page Node network group tests',
            setup: function() {
                common = new Common(this.remote);
                clusterPage = new ClusterPage(this.remote);
                clusterName = common.pickRandomName('Test Cluster');
                modal = new ModalWindow(this.remote);

                return this.remote
                    .then(function() {
                        return common.getIn();
                    })
                    .then(function() {
                        return common.createCluster(clusterName);
                    })
                    .then(function() {
                        return clusterPage.goToTab('Networks');
                    });
            },
            'Node network group creation': function() {
                return this.remote
                    .clickByCssSelector('.add-nodegroup-btn')
                    .then(function() {
                        return modal.waitToOpen();
                    })
                    .assertElementContainsText('h4.modal-title', 'Add New Node Network Group', 'Add New Node Network Group modal expected')
                    .setInputValue('[name=node_network_group_name]', 'Node_Network_Group_1')
                    .then(function() {
                        return modal.clickFooterButton('Add Group');
                    })
                    .then(function() {
                        return modal.waitToClose();
                    })
                    .assertElementAppears('.node-network-groups-list', 2000, 'Node network groups title appears')
                    .assertElementDisplayed('.subtab-link-Node_Network_Group_1', 'New subtab is shown')
                    .assertElementTextEquals('.network-group-name .btn-link', 'Node_Network_Group_1', 'New Node Network group title is shown');
            },
            'Verification is disabled for multirack': function() {
                return this.remote
                    .clickByCssSelector('.subtab-link-network_verification')
                    .assertElementExists('.alert-warning', 'Warning is shown')
                    .assertElementDisabled('.verify-networks-btn', 'Verify networks button is disabled');
            },
            'Node network group renaming': function() {
                return this.remote
                    .clickByCssSelector('.subtab-link-Node_Network_Group_1')
                    .clickByCssSelector('.glyphicon-pencil')
                    .assertElementAppears('.network-group-name input[type=text]', 2000, 'Node network group renaming control is rendered')
                    .findByCssSelector('.node-group-renaming input[type=text]')
                        .clearValue()
                        .type('default')
                        // Enter
                        .type('\uE007')
                        .end()
                    .assertElementAppears('.has-error.node-group-renaming', 1000, 'Error is displayed in case of dublicate name')
                    .findByCssSelector('.node-group-renaming input[type=text]')
                        .clearValue()
                        .type('Node_Network_Group_2')
                        // Enter
                        .type('\uE007')
                        .end()
                    .assertElementDisplayed('.subtab-link-Node_Network_Group_2', 'New subtab title is shown');
            },
            'Node network group deletion': function() {
                return this.remote
                    .clickByCssSelector('.subtab-link-default')
                    .assertElementNotExists('.glyphicon-remove', 'It is not possible to delete default node network group')
                    .clickByCssSelector('.subtab-link-Node_Network_Group_2')
                    .assertElementAppears('.glyphicon-remove', 1000, 'Remove icon is shown')
                    .clickByCssSelector('.glyphicon-remove')
                    .then(function() {
                        return modal.waitToOpen();
                    })
                    .assertElementContainsText('h4.modal-title', 'Remove Node Network Group', 'Remove Node Network Group modal expected')
                    .then(function() {
                        return modal.clickFooterButton('Delete');
                    })
                    .then(function() {
                        return modal.waitToClose();
                    })
                    .assertElementDisappears('.subtab-link-Node_Network_Group_2', 2000, 'Node network groups title disappears')
                    .assertElementDisappears('.network-group-name .btn-link', 1000, 'Default Node Network group title disappers');
            }
        };
    });
});
