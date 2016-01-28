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
  'intern!object',
  'tests/functional/pages/common',
  'tests/functional/pages/cluster',
  'tests/functional/nightly/library/networks'
], function(registerSuite, Common, ClusterPage, NetworksLib) {
  'use strict';

  registerSuite(function() {
    var div,
      divIp,
      common,
      clusterPage,
      clusterName,
      networksLib;

    return {
      name: 'GUI support for Ironic',
      setup: function() {
        // Create cluster with additional service "Ironic"
        div = 'div.baremetal ';
        divIp = 'div.baremetal div.ip_ranges ';
        common = new Common(this.remote);
        clusterPage = new ClusterPage(this.remote);
        networksLib = new NetworksLib(this.remote);
        clusterName = common.pickRandomName('Ironic Cluster');

        return this.remote
          // Enabling Ironic when create environment
          .then(function() {
            return common.getIn();
          })
          .then(function() {
            return common.createCluster(
              clusterName,
              {
                'Additional Services': function() {
                  return this.remote
                    .clickByCssSelector('input[value$="ironic"]');
                }
              }
            );
          });
      },
      'Check Ironic item on Settings tab': function() {
        return this.remote
          // Check Ironic item on Settings tab
          .then(function() {
            return clusterPage.goToTab('Settings');
          })
          .clickLinkByText('OpenStack Services')
          .assertElementEnabled('input[name=ironic]', 'Ironic item is enabled')
          .assertElementSelected('input[name=ironic]', 'Ironic item is selected')
          // Check "Baremetal Network" initial state
          .then(function() {
            return clusterPage.goToTab('Networks');
          })
          .then(function() {
            return networksLib.checkNetrworkInitialState('Baremetal');
          });
      },
      'Baremetal Network "IP Ranges" correct changing': function() {
        return this.remote
          // Change network settings
          .setInputValue(divIp + 'input[name*="range-start"]', '192.168.3.15')
          .setInputValue(divIp + 'input[name*="range-end"]', '192.168.3.100')
          .assertElementNotExists(div + 'div.has-error', 'No Baremetal errors are observed')
          // Save settings
          .then(function() {
            return networksLib.saveSettings();
          });
      },
      'Baremetal Network "IP Ranges" adding and deletion additional fields': function() {
        return this.remote
          // Change network settings
          .setInputValue(divIp + 'input[name*="range-start"]', '192.168.3.1')
          .setInputValue(divIp + 'input[name*="range-end"]', '192.168.3.50')
          // Add new IP range
          .clickByCssSelector(divIp + 'button.ip-ranges-add')
          .assertElementEnabled(divIp + 'div.range-row[data-reactid$="$1"] ' +
            'input[name*="range-start"]', 'Baremetal new "Start IP Range" textfield is enabled')
          .assertElementEnabled(divIp + 'div.range-row[data-reactid$="$1"] ' +
            'input[name*="range-end"]', 'Baremetal new "End IP Range" textfield is enabled')
          .setInputValue(divIp + 'div.range-row[data-reactid$="$1"] input[name*="range-start"]',
            '192.168.3.55')
          .setInputValue(divIp + 'div.range-row[data-reactid$="$1"] input[name*="range-end"]',
            '192.168.3.70')
          .assertElementNotExists(div + 'div.has-error', 'No Baremetal errors are observed')
          // Save settings
          .then(function() {
            return networksLib.saveSettings();
          })
          // Remove just added IP range
          .assertElementEnabled(divIp + '.range-row[data-reactid$="$1"] .ip-ranges-delete',
            'Delete IP range button is enabled')
          .clickByCssSelector(divIp + '.range-row[data-reactid$="$1"] .ip-ranges-delete')
          .assertElementNotExists(divIp + 'div.range-row[data-reactid$="$1"',
            'Baremetal new IP range is disappeared')
          .assertElementNotExists(div + 'div.has-error', 'No Baremetal errors are observed')
          // Save settings
          .then(function() {
            return networksLib.saveSettings();
          });
      },
      'Baremetal and other networks intersections': function() {
        this.timeout = 45000;
        return this.remote
          // Check Storage and Baremetal intersection
          .setInputValue(div + 'div.cidr input[type="text"]', '192.168.1.0/24')
          .setInputValue(divIp + 'input[name*="range-start"]', '192.168.1.1')
          .setInputValue(divIp + 'input[name*="range-end"]', '192.168.1.50')
          .assertElementNotExists(div + 'div.has-error', 'No Baremetal errors are observed')
          .assertElementExists('a[class$="neutron_l3"]', '"Neutron L3" link is existed')
          .clickByCssSelector('a[class$="neutron_l3"]')

          .assertElementEnabled('input[name="range-start_baremetal_range"]',
            '"Ironic IP range" Start textfield is enabled')
          .setInputValue('input[name="range-start_baremetal_range"]', '192.168.1.52')
          .assertElementEnabled('input[name="range-end_baremetal_range"]',
            '"Ironic IP range" End textfield is enabled')
          .setInputValue('input[name="range-end_baremetal_range"]', '192.168.1.254')
          .assertElementEnabled('input[name="baremetal_gateway"]',
            '"Ironic gateway " textfield is enabled')
          .setInputValue('input[name="baremetal_gateway"]', '192.168.1.51')
          .assertElementNotExists('div[data-reactid$="$baremetal-net"] div.has-error',
            'No Ironic errors are observed')
          .assertElementExists('a[class$="default"]', '"Default" link is existed')
          .clickByCssSelector('a[class$="default"]')

          .assertElementEnabled('button.apply-btn', '"Save Settings" button is enabled')
          .clickByCssSelector('button.apply-btn')
          .assertElementEnabled('div.storage div.cidr div.has-error input[type="text"]',
            'Storage "CIDR" textfield is "red" marked')
          .assertElementEnabled(div + 'div.cidr div.has-error input[type="text"]',
            'Baremetal "CIDR" textfield is "red" marked')
          .assertElementExists('div.network-alert', 'Error message is observed')
          .assertElementContainsText('div.network-alert',
            'Address space intersection between networks', 'True error message is displayed')
          .assertElementContainsText('div.network-alert', 'storage',
            'True error message is displayed')
          .assertElementContainsText('div.network-alert', 'baremetal',
            'True error message is displayed')
          .then(function() {
            return networksLib.cancelChanges();
          })
          // Check Management and Baremetal intersection
          .setInputValue(div + 'div.cidr input[type="text"]', '192.168.0.0/24')
          .setInputValue(divIp + 'input[name*="range-start"]', '192.168.0.1')
          .setInputValue(divIp + 'input[name*="range-end"]', '192.168.0.50')
          .assertElementNotExists(div + 'div.has-error', 'No Baremetal errors are observed')
          .assertElementExists('a[class$="neutron_l3"]', '"Neutron L3" link is existed')
          .clickByCssSelector('a[class$="neutron_l3"]')

          .assertElementEnabled('input[name="range-start_baremetal_range"]',
            '"Ironic IP range" Start textfield is enabled')
          .setInputValue('input[name="range-start_baremetal_range"]', '192.168.0.52')
          .assertElementEnabled('input[name="range-end_baremetal_range"]',
            '"Ironic IP range" End textfield is enabled')
          .setInputValue('input[name="range-end_baremetal_range"]', '192.168.0.254')
          .assertElementEnabled('input[name="baremetal_gateway"]',
            '"Ironic gateway " textfield is enabled')
          .setInputValue('input[name="baremetal_gateway"]', '192.168.0.51')
          .assertElementNotExists('div[data-reactid$="$baremetal-net"] div.has-error',
            'No Ironic errors are observed')
          .assertElementExists('a[class$="default"]', '"Default" link is existed')
          .clickByCssSelector('a[class$="default"]')

          .assertElementEnabled('button.apply-btn', '"Save Settings" button is enabled')
          .clickByCssSelector('button.apply-btn')
          .assertElementEnabled('div.management div.cidr div.has-error input[type="text"]',
            'Management "CIDR" textfield is "red" marked')
          .assertElementEnabled(div + 'div.cidr div.has-error input[type="text"]',
            'Baremetal "CIDR" textfield is "red" marked')
          .assertElementExists('div.network-alert', 'Error message is observed')
          .assertElementContainsText('div.network-alert',
            'Address space intersection between networks', 'True error message is displayed')
          .assertElementContainsText('div.network-alert', 'management',
            'True error message is displayed')
          .assertElementContainsText('div.network-alert', 'baremetal',
            'True error message is displayed')
          .then(function() {
            return networksLib.cancelChanges();
          })
          // Check Public and Baremetal intersection
          .setInputValue(div + 'div.cidr input[type="text"]', '172.16.0.0/24')
          .setInputValue(divIp + 'input[name*="range-start"]', '172.16.0.1')
          .setInputValue(divIp + 'input[name*="range-end"]', '172.16.0.50')
          .assertElementNotExists(div + 'div.has-error', 'No Baremetal errors are observed')
          .assertElementExists('a[class$="neutron_l3"]', '"Neutron L3" link is existed')
          .clickByCssSelector('a[class$="neutron_l3"]')

          .assertElementEnabled('input[name="range-start_baremetal_range"]',
            '"Ironic IP range" Start textfield is enabled')
          .setInputValue('input[name="range-start_baremetal_range"]', '172.16.0.51')
          .assertElementEnabled('input[name="range-end_baremetal_range"]',
            '"Ironic IP range" End textfield is enabled')
          .setInputValue('input[name="range-end_baremetal_range"]', '172.16.0.254')
          .assertElementEnabled('input[name="baremetal_gateway"]',
            '"Ironic gateway " textfield is enabled')
          .setInputValue('input[name="baremetal_gateway"]', '172.16.0.52')
          .assertElementNotExists('div[data-reactid$="$baremetal-net"] div.has-error',
            'No Ironic errors are observed')
          .assertElementExists('a[class$="default"]', '"Default" link is existed')
          .clickByCssSelector('a[class$="default"]')

          .assertElementEnabled('button.apply-btn', '"Save Settings" button is enabled')
          .clickByCssSelector('button.apply-btn')
          .assertElementEnabled('div.public div.cidr div.has-error input[type="text"]',
            'Public "CIDR" textfield is "red" marked')
          .assertElementEnabled(div + 'div.cidr div.has-error input[type="text"]',
            'Baremetal "CIDR" textfield is "red" marked')
          .assertElementExists('div.network-alert', 'Error message is observed')
          .assertElementContainsText('div.network-alert',
            'Address space intersection between networks', 'True error message is displayed')
          .assertElementContainsText('div.network-alert', 'public',
            'True error message is displayed')
          .assertElementContainsText('div.network-alert', 'baremetal',
            'True error message is displayed')
          .then(function() {
            return networksLib.cancelChanges();
          });
      },
      'Baremetal Network "Use VLAN tagging" option works': function() {
        return this.remote
          // Unselect "Use VLAN tagging" option
          .clickByCssSelector(div + 'div.vlan_start input[type="checkbox"]')
          .assertElementEnabled(div + 'div.vlan_start input[type="checkbox"]',
            'Baremetal "Use VLAN tagging" checkbox is enabled')
          .assertElementNotSelected(div + 'div.vlan_start input[type="checkbox"]',
            'Baremetal "Use VLAN tagging" checkbox is not selected')
          .assertElementNotExists(div + 'div.vlan_start input[type="text"]',
            'Baremetal "Use VLAN tagging" textfield is not existed')
          .assertElementNotExists(div + 'div.has-error', 'No Baremetal errors are observed')
          // Save settings
          .then(function() {
            return networksLib.saveSettings();
          })
          // Select back "Use VLAN tagging" option
          .assertElementEnabled(div + 'div.vlan_start input[type="checkbox"]',
            'Baremetal "Use VLAN tagging" checkbox is enabled')
          .clickByCssSelector(div + 'div.vlan_start input[type="checkbox"]')
          .assertElementEnabled(div + 'div.vlan_start input[type="checkbox"]',
            'Baremetal "Use VLAN tagging" checkbox is enabled')
          .assertElementSelected(div + 'div.vlan_start input[type="checkbox"]',
            'Baremetal "Use VLAN tagging" checkbox is selected')
          .assertElementEnabled(div + 'div.vlan_start input[type="text"]',
            'Baremetal "Use VLAN tagging" textfield is enabled')
          .assertElementContainsText(div + 'div.vlan_start div.has-error span[class^="help"]',
            'Invalid VLAN ID', 'True error message is displayed')
          .setInputValue(div + 'div.vlan_start input[type="text"]', '104')
          .assertElementNotExists(div + 'div.has-error', 'No Baremetal errors are observed')
          // Save settings
          .then(function() {
            return networksLib.saveSettings();
          });
      },
      'Baremetal Network "Use VLAN tagging" option validation': function() {
        return this.remote
          // Check "Use VLAN tagging" text field
          .setInputValue(div + 'div.vlan_start input[type="text"]', '0')
          .assertElementContainsText(div + 'div.vlan_start div.has-error span[class^="help"]',
            'Invalid VLAN ID', 'True error message is displayed')
          .then(function() {
            return networksLib.checkIncorrectValueInput();
          })
          .setInputValue(div + 'div.vlan_start input[type="text"]', '10000')
          .assertElementContainsText(div + 'div.vlan_start div.has-error span[class^="help"]',
            'Invalid VLAN ID', 'True error message is displayed')
          .then(function() {
            return networksLib.checkIncorrectValueInput();
          })
          .setInputValue(div + 'div.vlan_start input[type="text"]', '4095')
          .assertElementContainsText(div + 'div.vlan_start div.has-error span[class^="help"]',
            'Invalid VLAN ID', 'True error message is displayed')
          .then(function() {
            return networksLib.checkIncorrectValueInput();
          })
          .setInputValue(div + 'div.vlan_start input[type="text"]', '')
          .assertElementContainsText(div + 'div.vlan_start div.has-error span[class^="help"]',
            'Invalid VLAN ID', 'True error message is displayed')
          .then(function() {
            return networksLib.checkIncorrectValueInput();
          })
          .setInputValue(div + 'div.vlan_start input[type="text"]', '1')
          .assertElementNotExists(div + 'div.has-error', 'No Baremetal errors are observed')
          .assertElementEnabled('button.apply-btn', 'Save Settings button is enabled')
          .setInputValue(div + 'div.vlan_start input[type="text"]', '4094')
          .assertElementNotExists(div + 'div.has-error', 'No Baremetal errors are observed')
          .assertElementEnabled('button.apply-btn', 'Save Settings button is enabled')
          // Cancel changes
          .then(function() {
            return networksLib.cancelChanges();
          })
          .then(function() {
            return networksLib.checkNetrworkInitialState('Baremetal');
          });
      },
      'Baremetal Network "CIDR" field validation': function() {
        return this.remote
          // Check "CIDR" text field
          .setInputValue(div + 'div.cidr input[type="text"]', '192.168.3.0/245')
          .assertElementContainsText(div + 'div.cidr div.has-error span[class^="help"]',
            'Invalid CIDR', 'True error message is displayed')
          .then(function() {
            return networksLib.checkIncorrectValueInput();
          })
          .setInputValue(div + 'div.cidr input[type="text"]', '192.168.3.0/0')
          .assertElementContainsText(div + 'div.cidr div.has-error span[class^="help"]',
            'Invalid CIDR', 'True error message is displayed')
          .then(function() {
            return networksLib.checkIncorrectValueInput();
          })
          .setInputValue(div + 'div.cidr input[type="text"]', '192.168.3.0/1')
          .assertElementContainsText(div + 'div.cidr div.has-error span[class^="help"]',
            'Network is too large', 'True error message is displayed')
          .then(function() {
            return networksLib.checkIncorrectValueInput();
          })
          .setInputValue(div + 'div.cidr input[type="text"]', '192.168.3.0/31')
          .assertElementContainsText(div + 'div.cidr div.has-error span[class^="help"]',
            'Network is too small', 'True error message is displayed')
          .then(function() {
            return networksLib.checkIncorrectValueInput();
          })
          .setInputValue(div + 'div.cidr input[type="text"]', '192.168.3.0/33')
          .assertElementContainsText(div + 'div.cidr div.has-error span[class^="help"]',
            'Invalid CIDR', 'True error message is displayed')
          .then(function() {
            return networksLib.checkIncorrectValueInput();
          })
          .setInputValue(div + 'div.cidr input[type="text"]', '192.168.3.0/25')
          .assertElementExists('a[class$="neutron_l3"]', '"Neutron L3" link is existed')
          .assertElementExists('a[class$="neutron_l3"] i.glyphicon-danger-sign',
            'Error icon is observed before Neutron L3 link')
          .clickByCssSelector('a[class$="neutron_l3"]')
          .assertElementExists('div.has-error input[name="range-end_baremetal_range"]',
            '"Ironic IP range" End textfield is "red" marked')
          .assertElementContainsText('div[data-reactid$="$baremetal-net"] div.validation-error ' +
            'span[class^="help"]', 'IP address does not match the network CIDR',
            'True error message is displayed')
          .assertElementExists('a[class$="default"]', '"Default" link is existed')
          .clickByCssSelector('a[class$="default"]')
          .then(function() {
            return networksLib.checkIncorrectValueInput();
          })
          // Cancel changes
          .then(function() {
            return networksLib.cancelChanges();
          })
          .then(function() {
            return networksLib.checkNetrworkInitialState('Baremetal');
          });
      },
      'Baremetal Network "Use the whole CIDR" option works': function() {
        return this.remote
          // Select "Use the whole CIDR" option
          .clickByCssSelector(div + 'div.cidr input[type="checkbox"]')
          .assertElementEnabled(div + 'div.cidr input[type="checkbox"]',
            'Baremetal "Use the whole CIDR" checkbox is enabled')
          .assertElementSelected(div + 'div.cidr input[type="checkbox"]',
            'Baremetal "Use the whole CIDR" checkbox is selected')
          .assertElementDisabled(divIp + 'input[name*="range-start"]',
            'Baremetal "Start IP Range" textfield is disabled')
          .assertElementDisabled(divIp + 'input[name*="range-end"]',
            'Baremetal "End IP Range" textfield is disabled')
          .assertElementPropertyEquals(divIp + 'input[name*="range-start"]', 'value',
            '192.168.3.1', 'Baremetal "Start IP Range" textfield  has true value')
          .assertElementPropertyEquals(divIp + 'input[name*="range-end"]', 'value',
            '192.168.3.254', 'Baremetal "End IP Range" textfield has true value')
          .assertElementNotExists(div + 'div.has-error', 'No Baremetal errors are observed')
          // Save settings
          .then(function() {
            return networksLib.saveSettings();
          });
      }
    };
  });
});
