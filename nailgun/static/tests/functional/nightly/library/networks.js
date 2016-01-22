/*
 * Copyright 2016 Mirantis, Inc.
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

    checkNetrworkInitialState: function(networkName) {
      var chain = this.remote;
      var mainDIV;
      if (networkName === 'Public') {
        mainDIV = 'div.public ';
      } else if (networkName === 'Storage') {
        mainDIV = 'div.storage ';
      } else if (networkName === 'Management') {
        mainDIV = 'div.management ';
      } else if (networkName === 'Baremetal') {
        mainDIV = 'div.baremetal ';
      } else {
        throw new Error('Invalid input value. Check networkName: "' + networkName +
          '" parameter and restart test.');
      }

      // Generic components
      chain = chain.assertElementDisabled('button.apply-btn', '"Save Settings" button is disabled')
      .assertElementDisabled('button.btn-revert-changes', '"Cancel Changes" button is disabled')
      .assertElementNotExists('div.has-error', 'No Network errors are observed')
      // CIDR
      .assertElementEnabled(mainDIV + 'div.cidr input[type="text"]',
        networkName + ' "CIDR" textfield is enabled')
      .assertElementEnabled(mainDIV + 'div.cidr input[type="checkbox"]',
        networkName + ' "Use the whole CIDR" checkbox is enabled')
      // IP Ranges
      .assertElementNotExists(mainDIV + 'div.ip_ranges div.range-row[data-reactid$="$1"]',
        networkName + ' only default IP range is observed')
      // VLAN
      .assertElementEnabled(mainDIV + 'div.vlan_start input[type="checkbox"]',
        networkName + ' "Use VLAN tagging" checkbox is enabled');

      // Individual components
      if (networkName === 'Public' || networkName === 'Baremetal') {
        // CIDR
        chain = chain.assertElementNotSelected(mainDIV + 'div.cidr input[type="checkbox"]',
          networkName + ' "Use the whole CIDR" checkbox is not selected')
        // IP Ranges
        .assertElementEnabled(mainDIV + 'div.ip_ranges input[name*="range-start"]',
          networkName + ' "Start IP Range" textfield is enabled')
        .assertElementEnabled(mainDIV + 'div.ip_ranges input[name*="range-end"]',
          networkName + ' "End IP Range" textfield is enabled')
        .assertElementEnabled(mainDIV + 'div.ip_ranges button.ip-ranges-add',
          networkName + ' "Add new IP range" button is enabled');
        if (networkName === 'Public') {
          // CIDR
          chain = chain.assertElementPropertyEquals(mainDIV + 'div.cidr input[type="text"]', 'value',
            '172.16.0.0/24', networkName + ' "CIDR" textfield has default value')
          // IP Ranges
          .assertElementPropertyEquals(mainDIV + 'div.ip_ranges input[name*="range-start"]', 'value',
            '172.16.0.2', networkName + ' "Start IP Range" textfield  has default value')
          .assertElementPropertyEquals(mainDIV + 'div.ip_ranges input[name*="range-end"]', 'value',
            '172.16.0.126', networkName + ' "End IP Range" textfield has default value')
          // Gateway
          .assertElementEnabled(mainDIV + 'input[name="gateway"][type="text"]',
            networkName + ' "Gateway" textfield is enabled')
          .assertElementPropertyEquals(mainDIV + 'input[name="gateway"][type="text"]', 'value',
            '172.16.0.1', networkName + ' "Gateway" textfield  has default value')
          // VLAN
          .assertElementNotSelected(mainDIV + 'div.vlan_start input[type="checkbox"]',
            networkName + ' "Use VLAN tagging" checkbox is not selected')
          .assertElementNotExists(mainDIV + 'div.vlan_start input[type="text"]',
            networkName + ' "Use VLAN tagging" textfield is not exist');
        } else if (networkName === 'Baremetal') {
          // CIDR
          chain = chain.assertElementPropertyEquals(mainDIV + 'div.cidr input[type="text"]', 'value',
            '192.168.3.0/24', networkName + ' "CIDR" textfield has default value')
          // IP Ranges
          .assertElementPropertyEquals(mainDIV + 'div.ip_ranges input[name*="range-start"]', 'value',
            '192.168.3.1', networkName + ' "Start IP Range" textfield  has default value')
          .assertElementPropertyEquals(mainDIV + 'div.ip_ranges input[name*="range-end"]', 'value',
            '192.168.3.50', networkName + ' "End IP Range" textfield has default value')
          // VLAN
          .assertElementSelected(mainDIV + 'div.vlan_start input[type="checkbox"]',
            networkName + ' "Use VLAN tagging" checkbox is selected')
          .assertElementEnabled(mainDIV + 'div.vlan_start input[type="text"]',
            networkName + ' "Use VLAN tagging" textfield is enabled')
          .assertElementPropertyEquals(mainDIV + 'div.vlan_start input[type="text"]', 'value',
            '104', networkName + ' "Use VLAN tagging" textfield has default value');
        }
      } else {
        // CIDR
        chain = chain.assertElementSelected(mainDIV + 'div.cidr input[type="checkbox"]',
          'Baremetal "Use the whole CIDR" checkbox is selected')
        // IP Ranges
        .assertElementDisabled(mainDIV + 'div.ip_ranges input[name*="range-start"]',
          networkName + ' "Start IP Range" textfield is disabled')
        .assertElementDisabled(mainDIV + 'div.ip_ranges input[name*="range-end"]',
          networkName + ' "End IP Range" textfield is disabled')
        .assertElementDisabled(mainDIV + 'div.ip_ranges button.ip-ranges-add',
          networkName + ' "Add new IP range" button is disabled')
        // VLAN
        .assertElementSelected(mainDIV + 'div.vlan_start input[type="checkbox"]',
          networkName + ' "Use VLAN tagging" checkbox is selected')
        .assertElementEnabled(mainDIV + 'div.vlan_start input[type="text"]',
          networkName + ' "Use VLAN tagging" textfield is enabled');
        if (networkName === 'Storage') {
          // CIDR
          chain = chain.assertElementPropertyEquals(mainDIV + 'div.cidr input[type="text"]', 'value',
            '192.168.1.0/24', networkName + ' "CIDR" textfield has default value')
          // IP Ranges
          .assertElementPropertyEquals(mainDIV + 'div.ip_ranges input[name*="range-start"]', 'value',
            '192.168.1.1', networkName + ' "Start IP Range" textfield  has default value')
          .assertElementPropertyEquals(mainDIV + 'div.ip_ranges input[name*="range-end"]', 'value',
            '192.168.1.254', networkName + ' "End IP Range" textfield has default value')
          // VLAN
          .assertElementPropertyEquals(mainDIV + 'div.vlan_start input[type="text"]', 'value',
            '102', networkName + ' "Use VLAN tagging" textfield has default value');
        } else if (networkName === 'Management') {
          // CIDR
          chain = chain.assertElementPropertyEquals(mainDIV + 'div.cidr input[type="text"]', 'value',
            '192.168.0.0/24', networkName + ' "CIDR" textfield has default value')
          // IP Ranges
          .assertElementPropertyEquals(mainDIV + 'div.ip_ranges input[name*="range-start"]', 'value',
            '192.168.0.1', networkName + ' "Start IP Range" textfield  has default value')
          .assertElementPropertyEquals(mainDIV + 'div.ip_ranges input[name*="range-end"]', 'value',
            '192.168.0.254', networkName + ' "End IP Range" textfield has default value')
          // VLAN
          .assertElementPropertyEquals(mainDIV + 'div.vlan_start input[type="text"]', 'value',
            '101', networkName + ' "Use VLAN tagging" textfield has default value');
        }
      }
      return chain;
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
        .assertElementAppears('ul.node-network-groups-list', 1000, 'Node network groups list appears')
        .assertElementDisplayed('li.active a[class="subtab-link-' + groupTitle + '"]',
          'New network group is shown and selected')
        .assertElementTextEquals('a[class="subtab-link-' + groupTitle + '"]', groupTitle,
          'Name of new network group of is correct')
        .assertElementTextEquals('div.network-group-name button.btn-link', groupTitle,
          '"' + groupTitle + '" network group name "link" appears')
        .catch(function(error) {
          self.remote.then(function() {
            return self.modal.close();
          });
          throw new Error('Unexpected error via network group creation: ' + error);
        });
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
        .assertElementDisappears('a[class="subtab-link-' + groupTitle + '"]', 1000,
          '"' + groupTitle + '" network group deleted from network groups list')
        .assertElementTextEquals('div.network-group-name button.btn-link', 'default',
          '"' + groupTitle + '" network group name "link" disappears')
        .catch(function(error) {
          throw new Error('Unexpected error via network group deletion: ' + error);
        });
    },
    checkDefaultNetGroup: function() {
      return this.remote
        .assertElementDisplayed('a.subtab-link-default', '"default" network group is shown')
        .assertElementTextEquals('a.subtab-link-default', 'default',
          'Name of "default" network group is correct')
        .assertElementPropertyEquals('li[data-reactid$="$default"]', 'offsetTop', '50', '"default" network group is on top');
    },
    checkGateways: function(groupTitle, neutronType) {
      var chain = this.remote;

      chain = chain.assertElementDisabled('div.storage input[name="gateway"]',
        'Storage "Gateway" field exists and disabled for "' + groupTitle + '" network group')
      .assertElementDisabled('div.management input[name="gateway"]',
        'Management "Gateway" field exists and disabled for "' + groupTitle + '" network group');
      if (neutronType === 'VLAN') {
        chain = chain.assertElementDisabled('div.private input[name="gateway"]',
          'Private "Gateway" field exists and disabled for "' + groupTitle + '" network group');
      }
      return chain;
    },
    checkVLANs: function(groupTitle, neutronType) {
      var chain = this.remote;

      chain = chain.assertElementPropertyEquals('div.storage div.vlan_start input[type="text"]', 'value', '102',
        'Storage "Use VLAN tagging" textfield has default value for "' + groupTitle + '" network group')
      .assertElementPropertyEquals('div.management div.vlan_start input[type="text"]', 'value', '101',
        'Management "Use VLAN tagging" textfield has default value for "' + groupTitle + '" network group');
      if (neutronType === 'VLAN') {
        chain = chain.assertElementPropertyEquals('div.private div.vlan_start input[type="text"]', 'value', '103',
          'Private "Use VLAN tagging" textfield has default value for "' + groupTitle + '" network group');
      }
      chain = chain.assertElementDisabled('button.apply-btn', '"Save Settings" button is disabled')
      .assertElementDisabled('button.btn-revert-changes', '"Cancel Changes" button is disabled')
      .assertElementNotExists('div.has-error', 'No errors are observed');
      return chain;
    }
  };
  return NetworksLib;
});
