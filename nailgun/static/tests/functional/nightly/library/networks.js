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
  'tests/functional/helpers'
], function(ModalWindow) {
  'use strict';

  function NetworksLib(remote) {
    this.remote = remote;
    this.modal = new ModalWindow(remote);
  }

  NetworksLib.prototype = {
    constructor: NetworksLib,
    btnSaveSelector: 'button.apply-btn',
    btnCancelSelector: 'button.btn-revert-changes',
    btnVerifySelector: 'button.verify-networks-btn',
    defaultPlaceholder: '127.0.0.1',

    gotoNodeNetworkSubTab: function(groupName) {
      var networkSubtabSelector = 'div[id="network-subtabs"]';
      return this.remote
        .assertElementAppears(networkSubtabSelector, 1000, 'Network subtab list exists')
        .assertElementContainsText(networkSubtabSelector, groupName,
          '"' + groupName + '" link exists')
        .findByCssSelector(networkSubtabSelector)
          .clickLinkByText(groupName)
          .sleep(500)
          .assertElementContainsText('li.active', groupName, '"' + groupName + '" link is opened')
          .end();
    },
    checkNetworkInitialState: function(networkName) {
      var chain = this.remote;
      var self = this;
      var mainDiv = 'div.' + networkName.toLowerCase() + ' ';
      var properNames = ['Public', 'Storage', 'Management', 'Baremetal', 'Private'];
      if (properNames.indexOf(networkName) === -1) {
        throw new Error('Invalid input value. Check networkName: "' + networkName +
          '" parameter and restart test.');
      }

      // Generic components
      chain = chain.then(function() {
        return self.gotoNodeNetworkSubTab('default');
      })
      .assertElementDisabled(this.btnSaveSelector, '"Save Settings" button is disabled')
      .assertElementDisabled(this.btnCancelSelector, '"Cancel Changes" button is disabled')
      .assertElementNotExists('div.has-error', 'No Network errors are observed')
      // CIDR
      .assertElementEnabled(mainDiv + 'div.cidr input[type="text"]',
        networkName + ' "CIDR" textfield is enabled')
      .assertElementEnabled(mainDiv + 'div.cidr input[type="checkbox"]',
        networkName + ' "Use the whole CIDR" checkbox is enabled')
      // IP Ranges
      .assertElementsExist(mainDiv + 'div.ip_ranges div.range-row', 1,
        'Only default IP range is observed for ' + networkName + ' network')
      // VLAN
      .assertElementEnabled(mainDiv + 'div.vlan_start input[type="checkbox"]',
        networkName + ' "Use VLAN tagging" checkbox is enabled');

      // Individual components
      if (networkName === 'Public' || networkName === 'Baremetal') {
        // CIDR
        chain = chain.assertElementNotSelected(mainDiv + 'div.cidr input[type="checkbox"]',
          networkName + ' "Use the whole CIDR" checkbox is not selected')
        // IP Ranges
        .assertElementEnabled(mainDiv + 'div.ip_ranges input[name*="range-start"]',
          networkName + ' "Start IP Range" textfield is enabled')
        .assertElementEnabled(mainDiv + 'div.ip_ranges input[name*="range-end"]',
          networkName + ' "End IP Range" textfield is enabled')
        .assertElementEnabled(mainDiv + 'div.ip_ranges button.ip-ranges-add',
          networkName + ' "Add new IP range" button is enabled');
        if (networkName === 'Public') {
          // CIDR
          chain = chain.assertElementPropertyEquals(mainDiv + 'div.cidr input[type="text"]',
            'value', '172.16.0.0/24', networkName + ' "CIDR" textfield has default value')
          // IP Ranges
          .assertElementPropertyEquals(mainDiv + 'div.ip_ranges input[name*="range-start"]',
            'value', '172.16.0.2', networkName + ' "Start IP Range" textfield  has default value')
          .assertElementPropertyEquals(mainDiv + 'div.ip_ranges input[name*="range-end"]',
            'value', '172.16.0.126', networkName + ' "End IP Range" textfield has default value')
          // Gateway
          .assertElementEnabled(mainDiv + 'input[name="gateway"][type="text"]',
            networkName + ' "Gateway" textfield is enabled')
          .assertElementPropertyEquals(mainDiv + 'input[name="gateway"][type="text"]',
            'value', '172.16.0.1', networkName + ' "Gateway" textfield  has default value')
          // VLAN
          .assertElementNotSelected(mainDiv + 'div.vlan_start input[type="checkbox"]',
            networkName + ' "Use VLAN tagging" checkbox is not selected')
          .assertElementNotExists(mainDiv + 'div.vlan_start input[type="text"]',
            networkName + ' "Use VLAN tagging" textfield is not exist');
        } else if (networkName === 'Baremetal') {
          // CIDR
          chain = chain.assertElementPropertyEquals(mainDiv + 'div.cidr input[type="text"]',
            'value', '192.168.3.0/24', networkName + ' "CIDR" textfield has default value')
          // IP Ranges
          .assertElementPropertyEquals(mainDiv + 'div.ip_ranges input[name*="range-start"]',
            'value', '192.168.3.1', networkName + ' "Start IP Range" textfield  has default value')
          .assertElementPropertyEquals(mainDiv + 'div.ip_ranges input[name*="range-end"]',
            'value', '192.168.3.50', networkName + ' "End IP Range" textfield has default value')
          // VLAN
          .assertElementSelected(mainDiv + 'div.vlan_start input[type="checkbox"]',
            networkName + ' "Use VLAN tagging" checkbox is selected')
          .assertElementEnabled(mainDiv + 'div.vlan_start input[type="text"]',
            networkName + ' "Use VLAN tagging" textfield is enabled')
          .assertElementPropertyEquals(mainDiv + 'div.vlan_start input[type="text"]', 'value',
            '104', networkName + ' "Use VLAN tagging" textfield has default value');
        }
      } else {
        // CIDR
        chain = chain.assertElementSelected(mainDiv + 'div.cidr input[type="checkbox"]',
          'Baremetal "Use the whole CIDR" checkbox is selected')
        // IP Ranges
        .assertElementDisabled(mainDiv + 'div.ip_ranges input[name*="range-start"]',
          networkName + ' "Start IP Range" textfield is disabled')
        .assertElementDisabled(mainDiv + 'div.ip_ranges input[name*="range-end"]',
          networkName + ' "End IP Range" textfield is disabled')
        .assertElementDisabled(mainDiv + 'div.ip_ranges button.ip-ranges-add',
          networkName + ' "Add new IP range" button is disabled')
        // VLAN
        .assertElementSelected(mainDiv + 'div.vlan_start input[type="checkbox"]',
          networkName + ' "Use VLAN tagging" checkbox is selected')
        .assertElementEnabled(mainDiv + 'div.vlan_start input[type="text"]',
          networkName + ' "Use VLAN tagging" textfield is enabled');
        if (networkName === 'Storage') {
          // CIDR
          chain = chain.assertElementPropertyEquals(mainDiv + 'div.cidr input[type="text"]',
            'value', '192.168.1.0/24', networkName + ' "CIDR" textfield has default value')
          // IP Ranges
          .assertElementPropertyEquals(mainDiv + 'div.ip_ranges input[name*="range-start"]',
            'value', '192.168.1.1', networkName + ' "Start IP Range" textfield  has default value')
          .assertElementPropertyEquals(mainDiv + 'div.ip_ranges input[name*="range-end"]',
            'value', '192.168.1.254', networkName + ' "End IP Range" textfield has default value')
          // VLAN
          .assertElementPropertyEquals(mainDiv + 'div.vlan_start input[type="text"]', 'value',
            '102', networkName + ' "Use VLAN tagging" textfield has default value');
        } else if (networkName === 'Management') {
          // CIDR
          chain = chain.assertElementPropertyEquals(mainDiv + 'div.cidr input[type="text"]',
            'value', '192.168.0.0/24', networkName + ' "CIDR" textfield has default value')
          // IP Ranges
          .assertElementPropertyEquals(mainDiv + 'div.ip_ranges input[name*="range-start"]',
            'value', '192.168.0.1', networkName + ' "Start IP Range" textfield  has default value')
          .assertElementPropertyEquals(mainDiv + 'div.ip_ranges input[name*="range-end"]',
            'value', '192.168.0.254', networkName + ' "End IP Range" textfield has default value')
          // VLAN
          .assertElementPropertyEquals(mainDiv + 'div.vlan_start input[type="text"]', 'value',
            '101', networkName + ' "Use VLAN tagging" textfield has default value');
        } else if (networkName === 'Private') {
          // CIDR
          chain = chain.assertElementPropertyEquals(mainDiv + 'div.cidr input[type="text"]',
            'value', '192.168.2.0/24', networkName + ' "CIDR" textfield has default value')
          // IP Ranges
          .assertElementPropertyEquals(mainDiv + 'div.ip_ranges input[name*="range-start"]',
            'value', '192.168.2.1', networkName + ' "Start IP Range" textfield  has default value')
          .assertElementPropertyEquals(mainDiv + 'div.ip_ranges input[name*="range-end"]',
            'value', '192.168.2.254', networkName + ' "End IP Range" textfield has default value')
          // VLAN
          .assertElementPropertyEquals(mainDiv + 'div.vlan_start input[type="text"]', 'value',
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
          '"VLAN ID range" start textfield enabled')
        .assertElementEnabled('input[name="range-end_vlan_range"]',
          '"VLAN ID range" end textfield enabled');
      } else {
        chain = chain.assertElementContainsText('div.network-description',
          'Neutron supports different types of network segmentation such as VLAN, GRE, VXLAN ' +
          'etc. This section is specific to a tunneling segmentation related parameters such as ' +
          'Tunnel ID ranges for tenant separation and the Base MAC address',
          '"Neutron L2" description is correct')
        .assertElementEnabled('input[name="range-start_gre_id_range"]',
          '"Tunnel ID range" start textfield enabled')
        .assertElementEnabled('input[name="range-end_gre_id_range"]',
          '"Tunnel ID range" end textfield enabled');
      }
      chain = chain.assertElementEnabled('input[name="base_mac"]',
        '"Base MAC address" textfield enabled')
      // Check Neutron L3 subtab
      .clickByCssSelector('.subtab-link-neutron_l3')
      .assertElementExists('li.active a.subtab-link-neutron_l3', '"Neutron L3" subtab is selected')
      .findByCssSelector('div.form-floating-network')
        .assertElementTextEquals('h3', 'Floating Network Parameters',
          'Default subgroup name is observed')
        .assertElementContainsText('div.network-description',
          'This network is used to assign Floating IPs to tenant VMs',
          'Default subgroup description is observed')
        .assertElementEnabled('input[name^="range-start"]',
          '"Floating IP range" start textfield enabled')
        .assertElementEnabled('input[name^="range-end"]',
          '"Floating IP range" end textfield enabled')
        .assertElementEnabled('input[name="floating_name"]',
          '"Floating network name" textfield enabled')
        .end()
      .findByCssSelector('div.form-internal-network')
        .assertElementTextEquals('h3', 'Internal Network Parameters',
          'Default subgroup name is observed')
        .assertElementContainsText('div.network-description',
          'The Internal network connects all OpenStack nodes in the environment. All components ' +
          'of an OpenStack environment communicate with each other using this network',
          'Default subgroup description is observed')
        .assertElementEnabled('input[name="internal_cidr"]',
          '"Internal network CIDR" textfield enabled')
        .assertElementEnabled('input[name="internal_gateway"]',
          '"Internal network gateway" textfield enabled')
        .assertElementEnabled('input[name="internal_name"]',
          '"Internal network name" textfield enabled')
        .end()
      .findByCssSelector('div.form-dns-nameservers')
        .assertElementTextEquals('h3', 'Guest OS DNS Servers', 'Default subgroup name is observed')
        .assertElementContainsText('div.network-description', 'This setting is used to specify ' +
          'the upstream name servers for the environment. These servers will be used to forward ' +
          'DNS queries for external DNS names to DNS servers outside the environment',
          'Default subgroup description is observed')
        .assertElementsExist('input[name=dns_nameservers]', 2,
          '"Guest OS DNS Servers" both textfields are exists')
        .end()
      // Check Other subtab
      .clickByCssSelector('.subtab-link-network_settings')
      .assertElementExists('li.active a.subtab-link-network_settings', '"Other" subtab is selected')
      .assertElementTextEquals('span.subtab-group-public_network_assignment',
        'Public network assignment', 'Default subgroup name is observed')
      .assertElementEnabled('input[name="assign_to_all_nodes"]',
        '"Assign public network to all nodes" checkbox enabled')
      .assertElementTextEquals('span.subtab-group-neutron_advanced_configuration',
        'Neutron Advanced Configuration', 'Default subgroup name is observed')
      .assertElementEnabled('input[name="neutron_l3_ha"]', '"Neutron L3 HA" checkbox enabled');
      if (neutronType === 'VLAN') {
        chain = chain.assertElementEnabled('input[name="neutron_dvr"]',
          '"Neutron DVR" checkbox enabled');
      } else {
        chain = chain.assertElementDisabled('input[name="neutron_dvr"]',
          '"Neutron DVR" checkbox disabled')
        .assertElementEnabled('input[name="neutron_l2_pop"]',
          '"Neutron L2 population" checkbox enabled');
      }
      chain = chain.assertElementTextEquals('span.subtab-group-external_dns', 'Host OS DNS Servers',
        'Default subgroup name is observed')
      .assertElementEnabled('input[name="dns_list"]', '"DNS list" textfield enabled')
      .assertElementTextEquals('span.subtab-group-external_ntp', 'Host OS NTP Servers',
        'Default subgroup name is observed')
      .assertElementEnabled('input[name="ntp_list"]', '"NTP server list" textfield enabled');
      return chain;
    },
    checkNetrworkVerificationSegment: function() {
      var connectSelector = 'div.connect-';
      var verifyNodeSelector = 'div.verification-node-';
      var descriptionConnectivityCheck = RegExp(
        'Network verification checks the following[\\s\\S]*' +
        'L2 connectivity checks between nodes in the environment[\\s\\S]*' +
        'DHCP discover check on all nodes[\\s\\S]*' +
        'Repository connectivity check from the Fuel Master node[\\s\\S]*' +
        'Repository connectivity check from the Fuel Slave nodes through the public & ' +
        'admin.*PXE.*networks[\\s\\S]*', 'i');
      return this.remote
        .clickByCssSelector('.subtab-link-network_verification')
        .assertElementExists('li.active .subtab-link-network_verification',
          '"Connectivity Check" subtab is selected')
        .assertElementTextEquals('h3', 'Connectivity Check',
          '"Connectivity Check" subtab is opened')
        // Check default picture router scheme
        .findByCssSelector('div.verification-network-placeholder')
          .assertElementExists('div.verification-router', 'Main router picture is observed')
          .assertElementExists(connectSelector + '1',
            'Connection line picture for "left" node #1 is observed')
          .assertElementExists(connectSelector + '2',
            'Connection line picture for "center" node #2 is observed')
          .assertElementExists(connectSelector + '3',
            'Connection line picture for "right" node #3 is observed')
          .assertElementExists(verifyNodeSelector + '1', '"Left" node #1 picture is observed')
          .assertElementExists(verifyNodeSelector + '2', '"Center" node #2 picture is observed')
          .assertElementExists(verifyNodeSelector + '3', '"Right" node #3 picture is observed')
          .end()
        // Check default verification description
        .assertElementExists('ol.verification-description',
          '"Connectivity check" description is observed')
        .assertElementMatchesRegExp('ol.verification-description', descriptionConnectivityCheck,
          'Default "Connectivity check" description is observed')
        .assertElementExists(this.btnVerifySelector, '"Verify Networks" is disabled')
        .assertElementExists(this.btnCancelSelector, '"Cancel Changes" button is disabled')
        .assertElementExists(this.btnSaveSelector, '"Save Settings" button is disabled');
    },
    checkNetrworkIpRanges: function(networkName, correctIpRange, newIpRange) {
      var self = this;
      var netSelector = 'div.' + networkName.toLowerCase() + ' ';
      var ipStartSelector = netSelector + 'div.ip_ranges input[name*="range-start"]';
      var ipEndSelector = netSelector + 'div.ip_ranges input[name*="range-end"]';
      var properNames = ['Public', 'Storage', 'Management', 'Baremetal', 'Private'];
      if (properNames.indexOf(networkName) === -1) {
        throw new Error('Invalid input value. Check networkName: "' + networkName +
          '" parameter and restart test.');
      }
      return this.remote
        // "Use the whole CIDR" option works
        .then(function() {
          return self.checkCidrOption(networkName);
        })
        .then(function() {
          return self.saveSettings();
        })
        // Correct changing of "IP Ranges" works
        .setInputValue(ipStartSelector, correctIpRange[0])
        .setInputValue(ipEndSelector, correctIpRange[1])
        .then(function() {
          return self.saveSettings();
        })
        .assertElementPropertyEquals(ipStartSelector, 'value', correctIpRange[0],
          networkName + ' "Start IP Range" textfield  has correct new value')
        .assertElementPropertyEquals(ipEndSelector, 'value', correctIpRange[1],
          networkName + ' "End IP Range" textfield has correct new value')
        // Adding and deleting additional "IP Ranges" fields
        .then(function() {
          return self.addNewIpRange(networkName, newIpRange);
        })
        .then(function() {
          return self.saveSettings();
        })
        .then(function() {
          return self.deleteIpRange(networkName);
        })
        .then(function() {
          return self.saveSettings();
        })
        // Check "IP Ranges" Start and End validation
        .then(function() {
          return self.checkIpRanges(networkName);
        });
    },
    checkIncorrectValueInput: function(inputSelector, value, errorSelector, errorMessage) {
      var self = this;
      return this.remote
        .assertElementEnabled(inputSelector, '"' + inputSelector + '" is enabled')
        .setInputValue(inputSelector, value)
        .assertElementAppears(errorSelector, 1000,
          'Error message appears for "' + inputSelector + '" with "' + value + '" value')
        .assertElementContainsText(errorSelector, errorMessage,
          'True error message is displayed for "' + inputSelector + '" with "' + value + '" value')
        .then(function() {
          return self.checkMultirackVerification();
        });
    },
    checkMultirackVerification: function() {
      var self = this;
      return this.remote
        .assertElementDisabled(this.btnSaveSelector, '"Save Settings" button is disabled')
        .then(function() {
          return self.gotoNodeNetworkSubTab('Connectivity Check');
        })
        .assertElementDisabled(this.btnVerifySelector, '"Verify Networks" button is disabled')
        .then(function() {
          return self.gotoNodeNetworkSubTab('default');
        });
    },
    saveSettings: function() {
      return this.remote
        .assertElementEnabled(this.btnSaveSelector, '"Save Settings" button is enabled')
        .clickByCssSelector(this.btnSaveSelector)
        .assertElementDisabled(this.btnSaveSelector, '"Save Settings" button is disabled')
        .assertElementNotExists('div.has-error', 'Settings saved successfully');
    },
    cancelChanges: function() {
      return this.remote
        .assertElementEnabled(this.btnCancelSelector, '"Cancel Changes" button is enabled')
        .clickByCssSelector(this.btnCancelSelector)
        .assertElementDisabled(this.btnCancelSelector, '"Cancel Changes" button is disabled')
        .assertElementNotExists('div.has-error', 'Settings canceled successfully');
    },
    createNetworkGroup: function(groupName) {
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
        .setInputValue('input.node-group-input-name', groupName)
        .then(function() {
          return self.modal.clickFooterButton('Add Group');
        })
        .then(function() {
          return self.modal.waitToClose();
        })
        .assertElementDisappears('.network-group-name .explanation', 1000, 'New subtab is shown')
        .findByCssSelector('ul.node_network_groups li.active')
          .assertElementTextEquals('a', groupName,
            'New network group is appears, selected and name is correct')
          .end()
        .assertElementTextEquals('div.network-group-name button.btn-link', groupName,
          '"' + groupName + '" node network group title appears')

        .catch(function(error) {
          self.remote.then(function() {
            return self.modal.close();
          });
          throw new Error('Unexpected error via network group creation: ' + error);
        });
    },
    deleteNetworkGroup: function(groupName) {
      var self = this;
      return this.remote
        .then(function() {
          return self.gotoNodeNetworkSubTab(groupName);
        })
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
        .assertElementAppears('.network-group-name .explanation', 1000, 'Default subtab is shown')
        .assertElementNotContainsText('ul.node_network_groups', groupName,
          '"' + groupName + '" node network group disappears from network group list')
        .assertElementNotContainsText('div.network-group-name button.btn-link', groupName,
          '"' + groupName + '" node network group title disappears from "Networks" tab')
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
    checkBaremetalIntersection: function(networkName, intersectionValues) {
      // Input array: Values to raise baremetal intersection: [Baremetal CIDR, Baremetal Start IP,
      // Baremetal End IP, Ironic Start IP, Ironic End IP, Ironic Gateway]
      var self = this;
      var cidrSelector = 'div.baremetal div.cidr input[type="text"]';
      var startSelector = 'div.baremetal div.ip_ranges input[name*="range-start"]';
      var endSelector = 'div.baremetal div.ip_ranges input[name*="range-end"]';
      var baremetalGatewaySelector = 'input[name="baremetal_gateway"]';
      var baremetalStartSelector = 'input[name="range-start_baremetal_range"]';
      var baremetalEndSelector = 'input[name="range-end_baremetal_range"]';
      var networkAlertSelector = 'div.network-alert';
      return this.remote
        .setInputValue(cidrSelector, intersectionValues[0])
        .setInputValue(startSelector, intersectionValues[1])
        .setInputValue(endSelector, intersectionValues[2])
        .then(function() {
          return self.checkNeutronL3ForBaremetal();
        })
        .setInputValue(baremetalStartSelector, intersectionValues[3])
        .setInputValue(baremetalEndSelector, intersectionValues[4])
        .setInputValue(baremetalGatewaySelector, intersectionValues[5])
        .assertElementNotExists('div.form-baremetal-network div.has-error',
          'No Ironic errors are observed for Storage and Baremetal intersection')
        .then(function() {
          return self.gotoNodeNetworkSubTab('default');
        })
        .assertElementEnabled(this.btnSaveSelector, '"Save Settings" button is enabled')
        .clickByCssSelector(this.btnSaveSelector)
        .assertElementEnabled('div.' + networkName + ' div.cidr div.has-error input[type="text"]',
          networkName + ' "CIDR" textfield is "red" marked')
        .assertElementEnabled('div.baremetal div.cidr div.has-error input[type="text"]',
          'Baremetal "CIDR" textfield is "red" marked')
        .assertElementExists(networkAlertSelector, 'Error message is observed')
        .assertElementContainsText(networkAlertSelector,
          'Address space intersection between networks', 'True error message is displayed')
        .assertElementContainsText(networkAlertSelector, networkName,
          'True error message is displayed')
        .assertElementContainsText(networkAlertSelector, 'baremetal',
          'True error message is displayed')
        .then(function() {
          return self.cancelChanges();
        });
    },
    checkDefaultNetGroup: function() {
      return this.remote
        .assertElementContainsText('ul.node_network_groups', 'default',
          '"default" network group is shown and name is correct')
        .assertElementPropertyEquals('ul.node_network_groups li[role="presentation"]',
          'offsetTop', '50', 'First node network group is found')
        .assertElementTextEquals('ul.node_network_groups  li[role="presentation"]', 'default',
          '"default" network group is on top');
    },
    checkGateways: function(groupName, neutronType) {
      var chain = this.remote;
      chain = chain.assertElementDisabled('div.storage input[name="gateway"]',
        'Storage "Gateway" field exists and disabled for "' + groupName + '" network group')
      .assertElementDisabled('div.management input[name="gateway"]',
        'Management "Gateway" field exists and disabled for "' + groupName + '" network group');
      if (neutronType === 'VLAN') {
        chain = chain.assertElementDisabled('div.private input[name="gateway"]',
          'Private "Gateway" field exists and disabled for "' + groupName + '" network group');
      }
      return chain;
    },
    checkVLANs: function(groupName, neutronType) {
      var chain = this.remote;
      chain = chain.assertElementPropertyEquals('div.storage div.vlan_start input[type="text"]',
        'value', '102', 'Storage "Use VLAN tagging" textfield has default value for "' +
        groupName + '" network group')
      .assertElementPropertyEquals('div.management div.vlan_start input[type="text"]',
        'value', '101', 'Management "Use VLAN tagging" textfield has default value for "' +
        groupName + '" network group');
      if (neutronType === 'VLAN') {
        chain = chain.assertElementPropertyEquals('div.private div.vlan_start input[type="text"]',
          'value', '103', 'Private "Use VLAN tagging" textfield has default value for "' +
          groupName + '" network group');
      }
      chain = chain.assertElementDisabled(this.btnSaveSelector, '"Save Settings" btn is disabled')
      .assertElementDisabled(this.btnCancelSelector, '"Cancel Changes" button is disabled')
      .assertElementNotExists('div.has-error', 'No errors are observed');
      return chain;
    },
    checkCidrOption: function(networkName) {
      var self = this;
      var netSelector = 'div.' + networkName.toLowerCase() + ' ';
      var cidrSelector = netSelector + 'div.cidr input[type="checkbox"]';
      var ipStartSelector = netSelector + 'div.ip_ranges input[name*="range-start"]';
      var ipEndSelector = netSelector + 'div.ip_ranges input[name*="range-end"]';
      var defaultIpRange = {Storage: '1', Management: '0', Private: '2', Baremetal: '3'};
      return this.remote
        .assertElementEnabled(cidrSelector,
          networkName + ' "Use the whole CIDR" checkbox is enabled before changing')
        .findByCssSelector(cidrSelector)
          .isSelected()
          .then(function(cidrStatus) {
            return self.selectCidrWay(networkName, cidrStatus, cidrSelector, ipStartSelector,
              ipEndSelector);
          })
          .end()
        .assertElementPropertyEquals(ipStartSelector, 'value',
          '192.168.' + defaultIpRange[networkName] + '.1',
          networkName + ' "Start IP Range" textfield  has default value')
        .assertElementPropertyEquals(ipEndSelector, 'value',
          '192.168.' + defaultIpRange[networkName] + '.254',
          networkName + ' "End IP Range" textfield has default value')
        .assertElementNotExists(netSelector + 'div.has-error',
          'No ' + networkName + ' errors are observed');
    },
    selectCidrWay: function(networkName, cidrStatus, cidrSelector, ipStartSelector, ipEndSelector) {
      var chain = this.remote;
      chain = chain.clickByCssSelector(cidrSelector)
      .assertElementEnabled(cidrSelector,
        networkName + ' "Use the whole CIDR" checkbox is enabled after changing');
      if (cidrStatus) {
        chain = chain.assertElementNotSelected(cidrSelector,
          networkName + ' "Use the whole CIDR" checkbox is not selected')
        .assertElementEnabled(ipStartSelector,
          networkName + ' "Start IP Range" textfield is enabled')
        .assertElementEnabled(ipEndSelector,
          networkName + ' "End IP Range" textfield is enabled');
      } else {
        chain = chain.assertElementSelected(cidrSelector,
          networkName + ' "Use the whole CIDR" checkbox is selected')
        .assertElementDisabled(ipStartSelector,
          networkName + ' "Start IP Range" textfield is disabled')
        .assertElementDisabled(ipEndSelector,
          networkName + ' "End IP Range" textfield is disabled');
      }
      return chain;
    },
    addNewIpRange: function(networkName, newIpRange) {
      // Works only with last range!
      // Input array "newIpRange": [Start IP, End IP]
      var self = this;
      var chain = this.remote;
      var netSelector = 'div.' + networkName.toLowerCase() + ' ';
      var rowRangeSelector = netSelector + 'div.range-row';
      var lastRangeSelector = rowRangeSelector + ':last-child ';
      var addRangeSelector = lastRangeSelector + 'button.ip-ranges-add ';
      var ipStartSelector = 'input[name*="range-start"]';
      var ipEndSelector = 'input[name*="range-end"]';
      chain = chain.assertElementEnabled(addRangeSelector, 'IP range add button enabled')
      .findAllByCssSelector(rowRangeSelector)
        .then(function(elements) {
          return self.checkIpRange(addRangeSelector, rowRangeSelector, elements.length + 1);
        })
        .end()
      .assertElementEnabled(lastRangeSelector + ipStartSelector,
        networkName + ' new "Start IP Range" textfield is enabled')
      .assertElementEnabled(lastRangeSelector + ipEndSelector,
        networkName + ' new "End IP Range" textfield is enabled')
      .assertElementPropertyEquals(lastRangeSelector + ipStartSelector, 'placeholder',
        this.defaultPlaceholder,
        networkName + ' new "Start IP Range" textfield has default placeholder')
      .assertElementPropertyEquals(lastRangeSelector + ipEndSelector, 'placeholder',
        this.defaultPlaceholder,
        networkName + ' new "End IP Range" textfield has default placeholder');
      if (newIpRange) {
        chain = chain.setInputValue(lastRangeSelector + ipStartSelector, newIpRange[0])
        .setInputValue(lastRangeSelector + ipEndSelector, newIpRange[1])
        .assertElementPropertyEquals(lastRangeSelector + ipStartSelector, 'value', newIpRange[0],
          networkName + ' new "Start IP Range" textfield has new value')
        .assertElementPropertyEquals(lastRangeSelector + ipEndSelector, 'value', newIpRange[1],
          networkName + ' new "End IP Range" textfield has new value');
      }
      chain = chain.assertElementNotExists(netSelector + 'div.has-error',
        'No ' + networkName + ' errors are observed');
      return chain;
    },
    deleteIpRange: function(networkName, rangeRow) {
      var self = this;
      var netSelector = 'div.' + networkName.toLowerCase() + ' ';
      var rowRangeSelector = netSelector + 'div.range-row';
      var rowSelector = rowRangeSelector + ':last-child ';
      if (rangeRow) {
        rowSelector = rowRangeSelector + ':nth-child(' + (rangeRow + 1).toString() + ') ';
      }
      var delRangeSelector = rowSelector + 'button.ip-ranges-delete';
      return this.remote
        .assertElementsExist(rowSelector, networkName + ' IP Range to delete exists')
        .assertElementEnabled(delRangeSelector, networkName + ' IP Range delete button enabled')
        .findAllByCssSelector(rowRangeSelector)
          .then(function(elements) {
            return self.checkIpRange(delRangeSelector, rowRangeSelector, elements.length - 1);
          })
          .end()
        // Add more powerfull check of range deletion (values disappears)
        .assertElementNotExists(netSelector + 'div.has-error',
          'No ' + networkName + ' errors are observed');
    },
    checkIpRange: function(addremoveRangeSelector, rowRangeSelector, numRanges) {
      return this.remote
        .clickByCssSelector(addremoveRangeSelector)
        .sleep(500)
        .assertElementsExist(rowRangeSelector, numRanges, 'Correct number of IP ranges exists');
    },
    checkIpRanges: function(networkName) {
      var self = this;
      var netSelector = 'div.' + networkName.toLowerCase() + ' ';
      var cidrSelector = netSelector + 'div.cidr input[type="text"]';
      var ipStartSelector = netSelector + 'div.ip_ranges input[name*="range-start"]';
      var ipStartErrorSel = netSelector + 'div.ip_ranges div.has-error input[name*="range-start"]';
      var ipEndSelector = netSelector + 'div.ip_ranges input[name*="range-end"]';
      var ipEndErrorSel = netSelector + 'div.ip_ranges div.has-error input[name*="range-end"]';
      var networkAlertSelector = netSelector + 'div.ip_ranges div.validation-error';
      var initValue = '192.168.';
      var errorValue = '192.168.5.0/24';
      var errorValues = ['.*', '.279', '.254', '.1', '.5'];
      var defaultIpRange = {Storage: '1', Management: '0', Private: '2'};
      return this.remote
        .assertElementEnabled(cidrSelector, networkName + ' "CIDR" textfield is enabled')
        .assertElementEnabled(ipStartSelector, networkName + ' "Start IP Range" txtfld is enabled')
        .assertElementEnabled(ipEndSelector, networkName + ' "End IP Range" textfield is enabled')
        // Check #1
        .setInputValue(ipStartSelector, initValue + defaultIpRange[networkName] + errorValues[0])
        .assertElementsExist(ipStartErrorSel,
          networkName + ' "Start IP Range" textfield is "red" marked')
        .assertElementMatchesRegExp(networkAlertSelector, /Invalid IP address/i,
          'True error message is displayed')
        .then(function() {
          return self.cancelChanges();
        })
        // Check #2
        .setInputValue(ipEndSelector, initValue + defaultIpRange[networkName] + errorValues[1])
        .assertElementsExist(ipEndErrorSel,
          networkName + ' "End IP Range" textfield is "red" marked')
        .assertElementMatchesRegExp(networkAlertSelector, /Invalid IP address/i,
          'True error message is displayed')
        .then(function() {
          return self.cancelChanges();
        })
        // Check #3
        .setInputValue(cidrSelector, errorValue)
        .assertElementsExist(ipStartErrorSel,
          networkName + ' "Start IP Range" textfield is "red" marked')
        .assertElementsExist(ipEndErrorSel,
          networkName + ' "End IP Range" textfield is "red" marked')
        .assertElementMatchesRegExp(networkAlertSelector,
          /IP address does not match the network CIDR/i, 'True error message is displayed')
        .then(function() {
          return self.cancelChanges();
        })
        // Check #4
        .setInputValue(ipStartSelector, initValue + defaultIpRange[networkName] + errorValues[2])
        .setInputValue(ipEndSelector, initValue + defaultIpRange[networkName] + errorValues[3])
        .assertElementsExist(ipStartErrorSel,
          networkName + ' "Start IP Range" textfield is "red" marked')
        .assertElementsExist(ipEndErrorSel,
          networkName + ' "End IP Range" textfield is "red" marked')
        .assertElementMatchesRegExp(networkAlertSelector,
          /Start IP address must be less than end IP address/i, 'True error message is displayed')
        .then(function() {
          return self.cancelChanges();
        })
        // Check #5
        .setInputValue(ipStartSelector, initValue + defaultIpRange[networkName] + errorValues[4])
        .setInputValue(ipEndSelector, initValue + defaultIpRange[networkName] + errorValues[4])
        .then(function() {
          return self.saveSettings();
        })
        // Check #6
        .setInputValue(ipStartSelector, ' ')
        .assertElementsExist(ipStartErrorSel,
          networkName + ' "Start IP Range" textfield is "red" marked')
        .assertElementMatchesRegExp(networkAlertSelector, /Invalid IP address/i,
          'True error message is displayed')
        .then(function() {
          return self.cancelChanges();
        })
        // Check #7
        .setInputValue(ipEndSelector, ' ')
        .assertElementsExist(ipEndErrorSel,
          networkName + ' "End IP Range" textfield is "red" marked')
        .assertElementMatchesRegExp(networkAlertSelector, /Invalid IP address/i,
          'True error message is displayed')
        .then(function() {
          return self.cancelChanges();
        });
    },
    checkNerworksIntersection: function(networkNameToEdit, networkName, editValues) {
      // Input array "editValues": [CIDR, Start IP, End IP]
      var self = this;
      var netSelector1 = 'div.' + networkNameToEdit.toLowerCase() + ' ';
      var cidrSelector = netSelector1 + 'div.cidr input[type="text"]';
      var cidrErrorSelector = 'div.cidr div.has-error input[type="text"]';
      var ipStartSelector = netSelector1 + 'div.ip_ranges input[name*="range-start"]';
      var ipEndSelector = netSelector1 + 'div.ip_ranges input[name*="range-end"]';
      var netSelector2 = 'div.' + networkName.toLowerCase() + ' ';
      var networkAlertSelector = 'div.network-alert';
      var networkAlertMessage = RegExp(
        'Address space intersection between networks[\\s\\S]*' +
        '(' + networkNameToEdit + '.*|' + networkName + '.*){2}[\\s\\S]*', 'i');
      return this.remote
        .assertElementEnabled(cidrSelector,
          networkNameToEdit + ' "CIDR" textfield is enabled')
        .assertElementEnabled(ipStartSelector,
          networkNameToEdit + ' "Start IP Range" textfield is enabled')
        .assertElementEnabled(ipEndSelector,
          networkNameToEdit + ' "End IP Range" textfield is enabled')
        .setInputValue(cidrSelector, editValues[0])
        .setInputValue(ipStartSelector, editValues[1])
        .setInputValue(ipEndSelector, editValues[2])
        .assertElementEnabled(this.btnSaveSelector, '"Save Settings" button is enabled')
        .clickByCssSelector(this.btnSaveSelector)
        .assertElementsExist(netSelector1 + cidrErrorSelector,
          networkNameToEdit + ' "CIDR" textfield is "red" marked')
        .assertElementsExist(netSelector2 + cidrErrorSelector,
          networkName + ' "CIDR" textfield is "red" marked')
        .assertElementsExist(networkAlertSelector, 'Error message is observed')
        .assertElementMatchesRegExp(networkAlertSelector, networkAlertMessage,
          'True error message is displayed for intersection between' +
          networkNameToEdit + ' and ' + networkName + ' networks')
        .then(function() {
          return self.cancelChanges();
        });
    }
  };
  return NetworksLib;
});
