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
      } else if (networkName === 'Private') {
        mainDIV = 'div.private ';
      } else {
        throw new Error('Invalid input value. Check networkName: "' + networkName +
          '" parameter and restart test.');
      }

      // Generic components
      chain = chain.clickByCssSelector('.subtab-link-default')
      .assertElementDisabled('button.apply-btn', '"Save Settings" button is disabled')
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
          chain = chain.assertElementPropertyEquals(mainDIV + 'div.cidr input[type="text"]',
            'value', '172.16.0.0/24', networkName + ' "CIDR" textfield has default value')
          // IP Ranges
          .assertElementPropertyEquals(mainDIV + 'div.ip_ranges input[name*="range-start"]',
            'value', '172.16.0.2', networkName + ' "Start IP Range" textfield  has default value')
          .assertElementPropertyEquals(mainDIV + 'div.ip_ranges input[name*="range-end"]',
            'value', '172.16.0.126', networkName + ' "End IP Range" textfield has default value')
          // Gateway
          .assertElementEnabled(mainDIV + 'input[name="gateway"][type="text"]',
            networkName + ' "Gateway" textfield is enabled')
          .assertElementPropertyEquals(mainDIV + 'input[name="gateway"][type="text"]',
            'value', '172.16.0.1', networkName + ' "Gateway" textfield  has default value')
          // VLAN
          .assertElementNotSelected(mainDIV + 'div.vlan_start input[type="checkbox"]',
            networkName + ' "Use VLAN tagging" checkbox is not selected')
          .assertElementNotExists(mainDIV + 'div.vlan_start input[type="text"]',
            networkName + ' "Use VLAN tagging" textfield is not exist');
        } else if (networkName === 'Baremetal') {
          // CIDR
          chain = chain.assertElementPropertyEquals(mainDIV + 'div.cidr input[type="text"]',
            'value', '192.168.3.0/24', networkName + ' "CIDR" textfield has default value')
          // IP Ranges
          .assertElementPropertyEquals(mainDIV + 'div.ip_ranges input[name*="range-start"]',
            'value', '192.168.3.1', networkName + ' "Start IP Range" textfield  has default value')
          .assertElementPropertyEquals(mainDIV + 'div.ip_ranges input[name*="range-end"]',
            'value', '192.168.3.50', networkName + ' "End IP Range" textfield has default value')
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
          chain = chain.assertElementPropertyEquals(mainDIV + 'div.cidr input[type="text"]',
            'value', '192.168.1.0/24', networkName + ' "CIDR" textfield has default value')
          // IP Ranges
          .assertElementPropertyEquals(mainDIV + 'div.ip_ranges input[name*="range-start"]',
            'value', '192.168.1.1', networkName + ' "Start IP Range" textfield  has default value')
          .assertElementPropertyEquals(mainDIV + 'div.ip_ranges input[name*="range-end"]',
            'value', '192.168.1.254', networkName + ' "End IP Range" textfield has default value')
          // VLAN
          .assertElementPropertyEquals(mainDIV + 'div.vlan_start input[type="text"]', 'value',
            '102', networkName + ' "Use VLAN tagging" textfield has default value');
        } else if (networkName === 'Management') {
          // CIDR
          chain = chain.assertElementPropertyEquals(mainDIV + 'div.cidr input[type="text"]',
            'value', '192.168.0.0/24', networkName + ' "CIDR" textfield has default value')
          // IP Ranges
          .assertElementPropertyEquals(mainDIV + 'div.ip_ranges input[name*="range-start"]',
            'value', '192.168.0.1', networkName + ' "Start IP Range" textfield  has default value')
          .assertElementPropertyEquals(mainDIV + 'div.ip_ranges input[name*="range-end"]',
            'value', '192.168.0.254', networkName + ' "End IP Range" textfield has default value')
          // VLAN
          .assertElementPropertyEquals(mainDIV + 'div.vlan_start input[type="text"]', 'value',
            '101', networkName + ' "Use VLAN tagging" textfield has default value');
        } else if (networkName === 'Private') {
          // CIDR
          chain = chain.assertElementPropertyEquals(mainDIV + 'div.cidr input[type="text"]',
            'value', '192.168.2.0/24', networkName + ' "CIDR" textfield has default value')
          // IP Ranges
          .assertElementPropertyEquals(mainDIV + 'div.ip_ranges input[name*="range-start"]',
            'value', '192.168.2.1', networkName + ' "Start IP Range" textfield  has default value')
          .assertElementPropertyEquals(mainDIV + 'div.ip_ranges input[name*="range-end"]',
            'value', '192.168.2.254', networkName + ' "End IP Range" textfield has default value')
          // VLAN
          .assertElementPropertyEquals(mainDIV + 'div.vlan_start input[type="text"]', 'value',
            '103', networkName + ' "Use VLAN tagging" textfield has default value');
        }
      }
      return chain;
    },
    checkNetrworkSettingsSegment: function(neutronType) {
      var chain = this.remote;
      // Check Neutron L2 subtab
      chain = chain.clickByCssSelector('.subtab-link-neutron_l2')
      .assertElementExists('li.active a.subtab-link-neutron_l2', '"Neutron L2" subtab is selected')
      .assertElementTextEquals('h3.networks', 'Neutron L2 Configuration',
        '"Neutron L2" subtab is opened');
      if (neutronType === 'VLAN') {
        chain = chain.assertElementContainsText('div.network-description',
          'Neutron supports different types of network segmentation such as VLAN, GRE, VXLAN ' +
          'etc. This section is specific to VLAN segmentation related parameters such as VLAN ID ' +
          'ranges for tenant separation and the Base MAC address',
          '"Neutron L2" description is correct')
        .assertElementEnabled('input[name="range-start_vlan_range"]',
          '"VLAN ID range" start textfield exists')
        .assertElementEnabled('input[name="range-end_vlan_range"]',
          '"VLAN ID range" end textfield exists');
      } else {
        chain = chain.assertElementContainsText('div.network-description',
          'Neutron supports different types of network segmentation such as VLAN, GRE, VXLAN ' +
          'etc. This section is specific to a tunneling segmentation related parameters such as ' +
          'Tunnel ID ranges for tenant separation and the Base MAC address',
          '"Neutron L2" description is correct')
        .assertElementEnabled('input[name="range-start_gre_id_range"]',
          '"Tunnel ID range" start textfield exists')
        .assertElementEnabled('input[name="range-end_gre_id_range"]',
          '"Tunnel ID range" end textfield exists');
      }
      chain = chain.assertElementEnabled('input[name="base_mac"]',
        '"Base MAC address" textfield exists')
      // Check Neutron L3 subtab
      .clickByCssSelector('.subtab-link-neutron_l3')
      .assertElementExists('li.active a.subtab-link-neutron_l3', '"Neutron L3" subtab is selected')
      .findByCssSelector('div[data-reactid$="$floating-net"]')
        .assertElementTextEquals('h3', 'Floating Network Parameters',
          'True subgroup name is observed')
        .assertElementContainsText('div.network-description',
          'This network is used to assign Floating IPs to tenant VMs',
          'True subgroup description is observed')
        .assertElementEnabled('input[name^="range-start"]',
          '"Floating IP range" start textfield exists')
        .assertElementEnabled('input[name^="range-end"]',
          '"Floating IP range" end textfield exists')
        .assertElementEnabled('input[name="floating_name"]',
          '"Floating network name" textfield exists')
        .end()
      .findByCssSelector('div[data-reactid$="$internal-net"]')
        .assertElementTextEquals('h3', 'Internal Network Parameters',
          'True subgroup name is observed')
        .assertElementContainsText('div.network-description',
          'The Internal network connects all OpenStack nodes in the environment. All components ' +
          'of an OpenStack environment communicate with each other using this network',
          'True subgroup description is observed')
        .assertElementEnabled('input[name="internal_cidr"]',
          '"Internal network CIDR" textfield exists')
        .assertElementEnabled('input[name="internal_gateway"]',
          '"Internal network gateway" textfield exists')
        .assertElementEnabled('input[name="internal_name"]',
          '"Internal network name" textfield exists')
        .end()
      .findByCssSelector('div[data-reactid$="$dns-nameservers"]')
        .assertElementTextEquals('h3', 'Guest OS DNS Servers', 'True subgroup name is observed')
        .assertElementContainsText('div.network-description', 'This setting is used to specify ' +
          'the upstream name servers for the environment. These servers will be used to forward ' +
          'DNS queries for external DNS names to DNS servers outside the environment',
          'True subgroup description is observed')
        .assertElementEnabled('div[data-reactid$="$dns_nameservers0"] input[name=dns_nameservers]',
          '"Guest OS DNS Servers" textfield #1 exists')
        .assertElementEnabled('div[data-reactid$="$dns_nameservers1"] input[name=dns_nameservers]',
          '"Guest OS DNS Servers" textfield #2 exists')
        .end()
      // Check Other subtab
      .clickByCssSelector('.subtab-link-network_settings')
      .assertElementExists('li.active a.subtab-link-network_settings', '"Other" subtab is selected')
      .assertElementTextEquals('span.subtab-group-public_network_assignment',
        'Public network assignment', 'True subgroup name is observed')
      .assertElementEnabled('input[name="assign_to_all_nodes"]',
        '"Assign public network to all nodes" checkbox exists')
      .assertElementTextEquals('span.subtab-group-neutron_advanced_configuration',
        'Neutron Advanced Configuration', 'True subgroup name is observed')
      .assertElementEnabled('input[name="neutron_l3_ha"]', '"Neutron L3 HA" checkbox exists');
      if (neutronType === 'VLAN') {
        chain = chain.assertElementEnabled('input[name="neutron_dvr"]',
          '"Neutron DVR" checkbox exists');
      } else {
        chain = chain.assertElementDisabled('input[name="neutron_dvr"]',
          '"Neutron DVR" checkbox exists')
        .assertElementEnabled('input[name="neutron_l2_pop"]',
          '"Neutron L2 population" checkbox exists');
      }
      chain = chain.assertElementTextEquals('span.subtab-group-external_dns', 'Host OS DNS Servers',
        'True subgroup name is observed')
      .assertElementEnabled('input[name="dns_list"]', '"DNS list" textfield exists')
      .assertElementTextEquals('span.subtab-group-external_ntp', 'Host OS NTP Servers',
        'True subgroup name is observed')
      .assertElementEnabled('input[name="ntp_list"]', '"NTP server list" textfield exists');
      return chain;
    },
    checkNetrworkVerificationSegment: function() {
      return this.remote
        .clickByCssSelector('.subtab-link-network_verification')
        .assertElementExists('li.active .subtab-link-network_verification',
          '"Connectivity Check" subtab is selected')
        .assertElementTextEquals('h3', 'Connectivity Check',
          '"Connectivity Check" subtab is opened')
        // Check default picture router scheme
        .findByCssSelector('div.verification-network-placeholder')
          .assertElementExists('div.verification-router', 'Main router picture is observed')
          .assertElementExists('div.connect-1',
            'Connection line picture for "left" node #1 is observed')
          .assertElementExists('div.connect-2',
            'Connection line picture for "center" node #2 is observed')
          .assertElementExists('div.connect-3',
            'Connection line picture for "right" node #3 is observed')
          .assertElementExists('div.verification-node-1', '"Left" node #1 picture is observed')
          .assertElementExists('div.verification-node-2', '"Center" node #2 picture is observed')
          .assertElementExists('div.verification-node-3', '"Right" node #3 picture is observed')
          .end()
        // Check default verification description
        .findByCssSelector('ol.verification-description')
          .assertElementContainsText('li[data-reactid$="$0"]',
            'Network verification checks the following',
            'True "Verification description" header description is observed')
          .assertElementContainsText('li[data-reactid$="$1"]',
            'L2 connectivity checks between nodes in the environment',
            'True "Verification description" point #1 description is observed')
          .assertElementContainsText('li[data-reactid$="$2"]', 'DHCP discover check on all nodes',
            'True "Verification description" point #2 description is observed')
          .assertElementContainsText('li[data-reactid$="$3"]',
            'Repository connectivity check from the Fuel Master node',
            'True "Verification description" point #3 description is observed')
          .assertElementContainsText('li[data-reactid$="$4"]', 'Repository connectivity check ' +
            'from the Fuel Slave nodes through the public & admin (PXE) networks',
            'True "Verification description" point #4 description is observed')
          .end()
        .assertElementExists('button.verify-networks-btn', '"Verify Networks" is disabled')
        .assertElementExists('button.btn-revert-changes', '"Cancel Changes" button is disabled')
        .assertElementExists('button.apply-btn', '"Save Settings" button is disabled');
    },
    checkIncorrectValueInput: function() {
      return this.remote
        .assertElementDisabled('button.apply-btn', '"Save Settings" button is disabled')
        .assertElementExists('a[class$="network_verification"]',
          '"Connectivity Check" link is existed')
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
        .assertElementEnabled('button.add-nodegroup-btn',
          '"Add New Node Network Group" button is enabled')
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
        .assertElementAppears('li.active a[class="subtab-link-' + groupTitle + '"]', 1000,
          'New network group is appears and selected')
        .assertElementTextEquals('a[class="subtab-link-' + groupTitle + '"]', groupTitle,
          'Name of new network group of is correct')
        .assertElementTextEquals('div.network-group-name button.btn-link', groupTitle,
          '"' + groupTitle + '" node network group title appears')
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
          '"' + groupTitle + '" node network group disappears from network group list')
        .assertElementNotContainsText('div.network-group-name button.btn-link', groupTitle,
          '"' + groupTitle + '" node network group title disappears from "Networks" tab')
        .catch(function(error) {
          throw new Error('Unexpected error via network group deletion: ' + error);
        });
    },
    checkNeutronL3ForBaremetal: function() {
      return this.remote
        .assertElementNotExists('div.baremetal div.has-error', 'No Baremetal errors are observed')
        .assertElementExists('a[class$="neutron_l3"]', '"Neutron L3" link is existed')
        .clickByCssSelector('a[class$="neutron_l3"]')
        .assertElementEnabled('input[name="range-start_baremetal_range"]',
          '"Ironic IP range" Start textfield is enabled')
        .assertElementEnabled('input[name="range-end_baremetal_range"]',
          '"Ironic IP range" End textfield is enabled')
        .assertElementEnabled('input[name="baremetal_gateway"]',
          '"Ironic gateway " textfield is enabled');
    },
    checkBaremetalIntersection: function(networkName) {
      var self = this;
      return this.remote
        .assertElementEnabled('button.apply-btn', '"Save Settings" button is enabled')
        .clickByCssSelector('button.apply-btn')
        .assertElementEnabled('div.' + networkName + ' div.cidr div.has-error input[type="text"]',
          networkName + ' "CIDR" textfield is "red" marked')
        .assertElementEnabled('div.baremetal div.cidr div.has-error input[type="text"]',
          'Baremetal "CIDR" textfield is "red" marked')
        .assertElementExists('div.network-alert', 'Error message is observed')
        .assertElementContainsText('div.network-alert',
          'Address space intersection between networks', 'True error message is displayed')
        .assertElementContainsText('div.network-alert', networkName,
          'True error message is displayed')
        .assertElementContainsText('div.network-alert', 'baremetal',
          'True error message is displayed')
        .then(function() {
          return self.cancelChanges();
        });
    },
    checkDefaultNetGroup: function() {
      return this.remote
        .assertElementDisplayed('a.subtab-link-default', '"default" network group is shown')
        .assertElementTextEquals('a.subtab-link-default', 'default',
          'Name of "default" network group is correct')
        .assertElementPropertyEquals('li[data-reactid$="$default"]', 'offsetTop', '50',
          '"default" network group is on top');
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
      chain = chain.assertElementPropertyEquals('div.storage div.vlan_start input[type="text"]',
        'value', '102', 'Storage "Use VLAN tagging" textfield has default value for "' +
        groupTitle + '" network group')
      .assertElementPropertyEquals('div.management div.vlan_start input[type="text"]',
        'value', '101', 'Management "Use VLAN tagging" textfield has default value for "' +
        groupTitle + '" network group');
      if (neutronType === 'VLAN') {
        chain = chain.assertElementPropertyEquals('div.private div.vlan_start input[type="text"]',
          'value', '103', 'Private "Use VLAN tagging" textfield has default value for "' +
          groupTitle + '" network group');
      }
      chain = chain.assertElementDisabled('button.apply-btn', '"Save Settings" button is disabled')
      .assertElementDisabled('button.btn-revert-changes', '"Cancel Changes" button is disabled')
      .assertElementNotExists('div.has-error', 'No errors are observed');
      return chain;
    }
  };
  return NetworksLib;
});
