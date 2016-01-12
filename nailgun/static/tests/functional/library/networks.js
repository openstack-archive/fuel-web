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
    'tests/functional/pages/modal',
    '../../helpers'
], function(ModalWindow) {
    'use strict';

    function NetworksLib(remote) {
        this.remote = remote;
        this.modal = new ModalWindow(remote);
    }

    NetworksLib.prototype = {
        constructor: NetworksLib,

        checkBaremetalInitialState: function() {
            return this.remote
                // CIDR
                .assertElementEnabled('div.baremetal div.cidr input[type="text"]',
                    'Baremetal "CIDR" textfield is enabled')
                .assertElementPropertyEquals('div.baremetal div.cidr input[type="text"]', 'value', '192.168.3.0/24',
                    'Baremetal "CIDR" textfield has default value')
                .assertElementEnabled('div.baremetal div.cidr input[type="checkbox"]',
                    'Baremetal "Use the whole CIDR" checkbox is enabled')
                .assertElementNotSelected('div.baremetal div.cidr input[type="checkbox"]',
                    'Baremetal "Use the whole CIDR" checkbox is not selected')
                // IP Ranges
                .assertElementEnabled('div.baremetal div.ip_ranges input[name*="range-start"]',
                    'Baremetal "Start IP Range" textfield is enabled')
                .assertElementEnabled('div.baremetal div.ip_ranges input[name*="range-end"]',
                    'Baremetal "End IP Range" textfield is enabled')
                .assertElementEnabled('div.baremetal div.ip_ranges button.ip-ranges-add',
                    'Add new IP range button is enabled')
                .assertElementNotExists('div.baremetal div.ip_ranges div.range-row[data-reactid$="$1"]',
                    'Only default IP range is observed')
                .assertElementPropertyEquals('div.baremetal div.ip_ranges input[name*="range-start"]', 'value',
                    '192.168.3.1', 'Baremetal "Start IP Range" textfield  has default value')
                .assertElementPropertyEquals('div.baremetal div.ip_ranges input[name*="range-end"]', 'value',
                    '192.168.3.50', 'Baremetal "End IP Range" textfield has default value')
                // VLAN
                .assertElementEnabled('div.baremetal div.vlan_start input[type="checkbox"]',
                    'Baremetal "Use VLAN tagging" checkbox is enabled')
                .assertElementSelected('div.baremetal div.vlan_start input[type="checkbox"]',
                    'Baremetal "Use VLAN tagging" checkbox is selected')
                .assertElementEnabled('div.baremetal div.vlan_start input[type="text"]',
                    'Baremetal "Use VLAN tagging" textfield is enabled')
                .assertElementPropertyEquals('div.baremetal div.vlan_start input[type="text"]', 'value', '104',
                    'Baremetal "Use VLAN tagging" textfield has default value')
                // Generic
                .assertElementDisabled('button.apply-btn', '"Save Settings" button is disabled')
                .assertElementDisabled('button.btn-revert-changes', '"Cancel Changes" button is disabled')
                .assertElementNotExists('div.baremetal div.has-error', 'No Baremetal errors are observed');
        },
        checkIncorrectValueInput: function() {
            return this.remote
                .assertElementDisabled('button.apply-btn', '"Save Settings" button is disabled')
                .assertElementExists('a[class$="network_verification"]', '"Connectivity Check" link is existed')
                .clickByCssSelector('a[class$="network_verification"]')
                .assertElementDisabled('button.verify-networks-btn', '"Verify Networks" button is disabled')
                .assertElementExists('a[class$="default"]', '"Default" link is existed')
                .clickByCssSelector('a[class$="default"]');
        },
        saveSettings: function() {
            return this.remote
                .assertElementEnabled('button.apply-btn', '"Save Settings" button is enabled')
                .clickByCssSelector('button.apply-btn')
                .assertElementDisabled('button.apply-btn', '"Save Settings" button is disabled')
                .assertElementNotExists('div.has-error', 'Settings saved successfully');
        },
        cancelChanges: function() {
            return this.remote
                .assertElementEnabled('button.btn-revert-changes', '"Cancel Changes" button is enabled')
                .clickByCssSelector('button.btn-revert-changes')
                .assertElementDisabled('button.btn-revert-changes', '"Cancel Changes" button is disabled')
                .assertElementNotExists('div.has-error', 'Settings canceled successfully');
        },
        createNetworkGroup: function(groupTitle) {
            var self = this;
            return this.remote
                .assertElementEnabled('button.add-nodegroup-btn', '"Add New Node Network Group" button is enabled')
                .clickByCssSelector('button.add-nodegroup-btn')
                .then(function() {
                    return self.modal.waitToOpen();
                })
                .then(function() {
                    return self.modal.checkTitle('Add New Node Network Group');
                })
                .assertElementEnabled('input.node-group-input-name', '"Name" textfield is enabled')
                .setInputValue('input.node-group-input-name', groupTitle)
                .then(function() {
                    return self.modal.clickFooterButton('Add Group');
                })
                .then(function() {
                    return self.modal.waitToClose();
                })
                .assertElementAppears('ul.node-network-groups-list', 2000, 'Node network groups list appears')
                .assertElementDisplayed('li.active a[class="subtab-link-' + groupTitle + '"]',
                    'New network group is shown and selected')
                .assertElementTextEquals('a[class="subtab-link-' + groupTitle + '"]', groupTitle,
                    'Name of new network group of is correct')
                .catch(function(e) {
                    throw new Error('Unexpected error via network group creation: ' + e);
                });
                //.type('\uE00C')
                //.wait(5000);
        },
        checkDefaultNetGroup: function() {
            return this.remote
                .assertElementDisplayed('a.subtab-link-default', '"Default" network group is shown')
                .assertElementTextEquals('a.subtab-link-default', 'Default',
                    'Name of "Default" network group is correct')
                .assertElementPropertyEquals('li.default', 'offsetTop', '50', '"Default" network group is on top');
        },
        deleteNetworkGroup: function(groupTitle) {
            var self = this;
            return this.remote
                .assertElementDisplayed('a[class="subtab-link-' + groupTitle + '"]',
                    '"' + groupTitle + '" network group is shown')
                .assertElementTextEquals('a[class="subtab-link-' + groupTitle + '"]', groupTitle,
                    'Name of "' + groupTitle + '" network group of is correct')
                .clickByCssSelector('a[class="subtab-link-' + groupTitle + '"]')
                .assertElementAppears('.glyphicon-remove', 1000, 'Remove icon is shown')
                .clickByCssSelector('.glyphicon-remove')
                .then(function() {
                    return self.modal.waitToOpen();
                })
                .then(function() {
                    return self.modal.checkTitle('Remove Node Network Group');
                })
                .then(function() {
                    return self.modal.clickFooterButton('Delete');
                })
                .then(function() {
                    return self.modal.waitToClose();
                })
                .assertElementDisappears('a[class="subtab-link-' + groupTitle + '"]', 2000,
                    '"' + groupTitle + '" network group deleted from network groups list')
                .assertElementDisappears('div[class="network-group-name"] button.btn-link', 1000,
                    '"' + groupTitle + '" network group disappears')
                .catch(function(e) {
                    throw new Error('Unexpected error via network group deletion: ' + e);
                });
        },
        checkGateways: function(groupTitle) {
            return this.remote
                .assertElementDisabled('div.storage input[name="gateway"]',
                    'Storage "Gateway" field exists and disabled for "' + groupTitle + '" network group')
                .assertElementDisabled('div.management input[name="gateway"]',
                    'Management "Gateway" field exists and disabled for "' + groupTitle + '" network group')
                .assertElementDisabled('div.private div.input[name="gateway"]',
                    'Private "Gateway" field exists and disabled for "' + groupTitle + '" network group')
                .catch(function() {});
        },
        checkVLANs: function(groupTitle) {
            return this.remote
                .assertElementPropertyEquals('div.storage div.vlan_start input[type="text"]', 'value', '102',
                    'Storage "Use VLAN tagging" textfield has default value for "' + groupTitle + '" network group')
                .assertElementPropertyEquals('div.management div.vlan_start input[type="text"]', 'value', '101',
                    'Management "Use VLAN tagging" textfield has default value for "' + groupTitle + '" network group')
                .assertElementPropertyEquals('div.private div.vlan_start input[type="text"]', 'value', '103',
                    'Private "Use VLAN tagging" textfield has default value for "' + groupTitle + '" network group')
                .assertElementDisabled('button.apply-btn', '"Save Settings" button is disabled')
                .assertElementDisabled('button.btn-revert-changes', '"Cancel Changes" button is disabled')
                .assertElementNotExists('div.has-error', 'No errors are observed')
                .catch(function() {});
        }
    };
    return NetworksLib;
});
