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
    '../../helpers'
], function() {
    'use strict';

    function NetworksPage(remote) {
        this.applyButtonSelector = '.apply-btn';
        this.remote = remote;
    }

    NetworksPage.prototype = {
        constructor: NetworksPage,
        switchNetworkManager: function() {
            return this.remote
                .clickByCssSelector('input[name=net_provider]:not(:checked)');
        },
        checkBaremetalInitialState: function() {
            return this.remote
                // CIDR
                .assertElementEnabled('div.baremetal div.cidr input[type="text"]', 'Baremetal "CIDR" textfield is enabled')
                .assertElementPropertyEquals('div.baremetal div.cidr input[type="text"]', 'value', '192.168.3.0/24', 'Baremetal "CIDR" textfield has default value')
                .assertElementEnabled('div.baremetal div.cidr input[type="checkbox"]', 'Baremetal "Use the whole CIDR" checkbox is enabled')
                .assertElementNotSelected('div.baremetal div.cidr input[type="checkbox"]', 'Baremetal "Use the whole CIDR" checkbox is not selected')
                // IP Ranges
                .assertElementEnabled('div.baremetal div.ip_ranges input[name*="range-start"]', 'Baremetal "Start IP Range" textfield is enabled')
                .assertElementEnabled('div.baremetal div.ip_ranges input[name*="range-end"]', 'Baremetal "End IP Range" textfield is enabled')
                .assertElementEnabled('div.baremetal div.ip_ranges button.ip-ranges-add', 'Add new IP range button is enabled')
                .assertElementNotExists('div.baremetal div.ip_ranges div.range-row[data-reactid$="$1"]', 'Only default IP range is observed')
                .assertElementPropertyEquals('div.baremetal div.ip_ranges input[name*="range-start"]', 'value', '192.168.3.1', 'Baremetal "Start IP Range" textfield  has default value')
                .assertElementPropertyEquals('div.baremetal div.ip_ranges input[name*="range-end"]', 'value', '192.168.3.50', 'Baremetal "End IP Range" textfield has default value')
                // VLAN
                .assertElementEnabled('div.baremetal div.vlan_start input[type="checkbox"]', 'Baremetal "Use VLAN tagging" checkbox is enabled')
                .assertElementSelected('div.baremetal div.vlan_start input[type="checkbox"]', 'Baremetal "Use VLAN tagging" checkbox is selected')
                .assertElementEnabled('div.baremetal div.vlan_start input[type="text"]', 'Baremetal "Use VLAN tagging" textfield is enabled')
                .assertElementPropertyEquals('div.baremetal div.vlan_start input[type="text"]', 'value', '104', 'Baremetal "Use VLAN tagging" textfield textfield has default value')
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
        }
    };
    return NetworksPage;
});
