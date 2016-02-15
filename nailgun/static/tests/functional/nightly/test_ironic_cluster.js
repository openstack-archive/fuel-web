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
          // Enabling Ironic when creating environment
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
            return networksLib.checkNetworkInitialState('Baremetal');
          });
      },
      'Baremetal Network "IP Ranges" correct changing': function() {
        var ipRangeStart = '192.168.3.15';
        var ipRangeEnd = '192.168.3.100';
        return this.remote
          // Change network settings
          .setInputValue(divIp + 'input[name*="range-start"]', ipRangeStart)
          .setInputValue(divIp + 'input[name*="range-end"]', ipRangeEnd)
          .assertElementNotExists(div + 'div.has-error', 'No Baremetal errors are observed')
          .then(function() {
            return networksLib.saveSettings();
          });
      },
      'Baremetal Network "IP Ranges" adding and deleting additional fields': function() {
        var ipRangeStart = ['192.168.3.1', '192.168.3.55'];
        var ipRangeEnd = ['192.168.3.50', '192.168.3.70'];
        return this.remote
          // Change network settings
          .setInputValue(divIp + 'input[name*="range-start"]', ipRangeStart[0])
          .setInputValue(divIp + 'input[name*="range-end"]', ipRangeEnd[0])
          // Add new IP range
          .clickByCssSelector(divIp + 'button.ip-ranges-add')
          .assertElementsExist(divIp + 'div.range-row', 2, 'New IP range is appears')
          .assertElementEnabled(divIp + 'div.range-row:nth-child(3) input[name*="range-start"]',
            'Baremetal new "Start IP Range" textfield is enabled')
          .assertElementEnabled(divIp + 'div.range-row:nth-child(3) input[name*="range-end"]',
            'Baremetal new "End IP Range" textfield is enabled')
          .setInputValue(divIp + 'div.range-row:nth-child(3) input[name*="range-start"]',
            ipRangeStart[1])
          .setInputValue(divIp + 'div.range-row:nth-child(3) input[name*="range-end"]',
            ipRangeEnd[1])
          .assertElementNotExists(div + 'div.has-error', 'No Baremetal errors are observed')
          .then(function() {
            return networksLib.saveSettings();
          })
          // Remove just added IP range
          .assertElementEnabled(divIp + 'div.range-row:nth-child(3) .ip-ranges-delete',
            'Delete IP range button is enabled')
          .clickByCssSelector(divIp + 'div.range-row:nth-child(3) .ip-ranges-delete')
          .assertElementNotExists(divIp + 'div.range-row:nth-child(3)',
            'Baremetal new IP range is disappeared')
          .assertElementsExist(divIp + 'div.range-row', 1, 'Only default IP range is exists')
          .assertElementNotExists(div + 'div.has-error', 'No Baremetal errors are observed')
          .then(function() {
            return networksLib.saveSettings();
          });
      },
      'Baremetal and other networks intersections': function() {
        this.timeout = 45000;
        var ipRangeStart = ['192.168.1.1', '192.168.0.1', '172.16.0.1'];
        var ipRangeEnd = ['192.168.1.50', '192.168.0.50', '172.16.0.50'];
        var cidrArray = ['192.168.1.0/24', '192.168.0.0/24', '172.16.0.0/24'];
        var ipBaremetalStart = ['192.168.1.52', '192.168.0.52', '172.16.0.51'];
        var ipBaremetalEnd = ['192.168.1.254', '192.168.0.254', '172.16.0.254'];
        var gatewayArray = ['192.168.1.51', '192.168.0.51', '172.16.0.52'];
        return this.remote
          // Check Storage and Baremetal intersection
          .setInputValue(div + 'div.cidr input[type="text"]', cidrArray[0])
          .setInputValue(divIp + 'input[name*="range-start"]', ipRangeStart[0])
          .setInputValue(divIp + 'input[name*="range-end"]', ipRangeEnd[0])
          .then(function() {
            return networksLib.checkNeutronL3ForBaremetal();
          })
          .setInputValue('input[name="range-start_baremetal_range"]', ipBaremetalStart[0])
          .setInputValue('input[name="range-end_baremetal_range"]', ipBaremetalEnd[0])
          .setInputValue('input[name="baremetal_gateway"]', gatewayArray[0])
          .assertElementNotExists('div.form-baremetal-network div.has-error',
            'No Ironic errors are observed for Storage and Baremetal intersection')
          .then(function() {
            return networksLib.gotoNodeNetworkGroup('default');
          })
          .then(function() {
            return networksLib.checkBaremetalIntersection('storage');
          })
          // Check Management and Baremetal intersection
          .setInputValue(div + 'div.cidr input[type="text"]', cidrArray[1])
          .setInputValue(divIp + 'input[name*="range-start"]', ipRangeStart[1])
          .setInputValue(divIp + 'input[name*="range-end"]', ipRangeEnd[1])
          .then(function() {
            return networksLib.checkNeutronL3ForBaremetal();
          })
          .setInputValue('input[name="range-start_baremetal_range"]', ipBaremetalStart[1])
          .setInputValue('input[name="range-end_baremetal_range"]', ipBaremetalEnd[1])
          .setInputValue('input[name="baremetal_gateway"]', gatewayArray[1])
          .assertElementNotExists('div.form-baremetal-network div.has-error',
            'No Ironic errors are observed for Management and Baremetal intersection')
          .then(function() {
            return networksLib.gotoNodeNetworkGroup('default');
          })
          .then(function() {
            return networksLib.checkBaremetalIntersection('management');
          })
          // Check Public and Baremetal intersection
          .setInputValue(div + 'div.cidr input[type="text"]', cidrArray[2])
          .setInputValue(divIp + 'input[name*="range-start"]', ipRangeStart[2])
          .setInputValue(divIp + 'input[name*="range-end"]', ipRangeEnd[2])
          .then(function() {
            return networksLib.checkNeutronL3ForBaremetal();
          })
          .setInputValue('input[name="range-start_baremetal_range"]', ipBaremetalStart[2])
          .setInputValue('input[name="range-end_baremetal_range"]', ipBaremetalEnd[2])
          .setInputValue('input[name="baremetal_gateway"]', gatewayArray[2])
          .assertElementNotExists('div.form-baremetal-network div.has-error',
            'No Ironic errors are observed for Public and Baremetal intersection')
          .then(function() {
            return networksLib.gotoNodeNetworkGroup('default');
          })
          .then(function() {
            return networksLib.checkBaremetalIntersection('public');
          });
      },
      'Baremetal Network "Use VLAN tagging" option works': function() {
        var vlanTag = '104';
        return this.remote
          // Unselect "Use VLAN tagging" option
          .clickByCssSelector(div + 'div.vlan_start input[type="checkbox"]')
          .assertElementEnabled(div + 'div.vlan_start input[type="checkbox"]',
            'Baremetal "Use VLAN tagging" checkbox is enabled')
          .assertElementNotSelected(div + 'div.vlan_start input[type="checkbox"]',
            'Baremetal "Use VLAN tagging" checkbox is not selected')
          .assertElementNotExists(div + 'div.vlan_start input[type="text"]',
            'Baremetal "Use VLAN tagging" textfield does not exist')
          .assertElementNotExists(div + 'div.has-error', 'No Baremetal errors are observed')
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
          .setInputValue(div + 'div.vlan_start input[type="text"]', vlanTag)
          .assertElementNotExists(div + 'div.has-error', 'No Baremetal errors are observed')
          .then(function() {
            return networksLib.saveSettings();
          });
      },
      'Baremetal Network "Use VLAN tagging" option validation': function() {
        var vlanTag = ['0', '10000', '4095', '', '1', '4094'];
        return this.remote
          // Check "Use VLAN tagging" text field
          .setInputValue(div + 'div.vlan_start input[type="text"]', vlanTag[0])
          .assertElementContainsText(div + 'div.vlan_start div.has-error span[class^="help"]',
            'Invalid VLAN ID', 'True error message is displayed')
          .then(function() {
            return networksLib.checkIncorrectValueInput();
          })
          .setInputValue(div + 'div.vlan_start input[type="text"]', vlanTag[1])
          .assertElementContainsText(div + 'div.vlan_start div.has-error span[class^="help"]',
            'Invalid VLAN ID', 'True error message is displayed')
          .then(function() {
            return networksLib.checkIncorrectValueInput();
          })
          .setInputValue(div + 'div.vlan_start input[type="text"]', vlanTag[2])
          .assertElementContainsText(div + 'div.vlan_start div.has-error span[class^="help"]',
            'Invalid VLAN ID', 'True error message is displayed')
          .then(function() {
            return networksLib.checkIncorrectValueInput();
          })
          .setInputValue(div + 'div.vlan_start input[type="text"]', vlanTag[3])
          .assertElementContainsText(div + 'div.vlan_start div.has-error span[class^="help"]',
            'Invalid VLAN ID', 'True error message is displayed')
          .then(function() {
            return networksLib.checkIncorrectValueInput();
          })
          .setInputValue(div + 'div.vlan_start input[type="text"]', vlanTag[4])
          .assertElementNotExists(div + 'div.has-error', 'No Baremetal errors are observed')
          .assertElementEnabled('button.apply-btn', 'Save Settings button is enabled')
          .setInputValue(div + 'div.vlan_start input[type="text"]', vlanTag[5])
          .assertElementNotExists(div + 'div.has-error', 'No Baremetal errors are observed')
          .assertElementEnabled('button.apply-btn', 'Save Settings button is enabled')
          // Cancel changes
          .then(function() {
            return networksLib.cancelChanges();
          })
          .then(function() {
            return networksLib.checkNetworkInitialState('Baremetal');
          });
      },
      'Baremetal Network "CIDR" field validation': function() {
        var cidrPart1 = '192.168.3.0/';
        var cidrPart2 = ['245', '0', '1', '31', '33', '25'];
        return this.remote
          // Check "CIDR" text field
          .setInputValue(div + 'div.cidr input[type="text"]', cidrPart1 + cidrPart2[0])
          .assertElementContainsText(div + 'div.cidr div.has-error span[class^="help"]',
            'Invalid CIDR', 'True error message is displayed')
          .then(function() {
            return networksLib.checkIncorrectValueInput();
          })
          .setInputValue(div + 'div.cidr input[type="text"]', cidrPart1 + cidrPart2[1])
          .assertElementContainsText(div + 'div.cidr div.has-error span[class^="help"]',
            'Invalid CIDR', 'True error message is displayed')
          .then(function() {
            return networksLib.checkIncorrectValueInput();
          })
          .setInputValue(div + 'div.cidr input[type="text"]', cidrPart1 + cidrPart2[2])
          .assertElementContainsText(div + 'div.cidr div.has-error span[class^="help"]',
            'Network is too large', 'True error message is displayed')
          .then(function() {
            return networksLib.checkIncorrectValueInput();
          })
          .setInputValue(div + 'div.cidr input[type="text"]', cidrPart1 + cidrPart2[3])
          .assertElementContainsText(div + 'div.cidr div.has-error span[class^="help"]',
            'Network is too small', 'True error message is displayed')
          .then(function() {
            return networksLib.checkIncorrectValueInput();
          })
          .setInputValue(div + 'div.cidr input[type="text"]', cidrPart1 + cidrPart2[4])
          .assertElementContainsText(div + 'div.cidr div.has-error span[class^="help"]',
            'Invalid CIDR', 'True error message is displayed')
          .then(function() {
            return networksLib.checkIncorrectValueInput();
          })
          .setInputValue(div + 'div.cidr input[type="text"]', cidrPart1 + cidrPart2[5])
          .assertElementExists('a[class$="neutron_l3"]', '"Neutron L3" link is existed')
          .assertElementExists('a[class$="neutron_l3"] i.glyphicon-danger-sign',
            'Error icon is observed before Neutron L3 link')
          .clickByCssSelector('a[class$="neutron_l3"]')
          .assertElementExists('div.has-error input[name="range-end_baremetal_range"]',
            '"Ironic IP range" End textfield is "red" marked')
          .assertElementContainsText('div.form-baremetal-network div.validation-error ' +
            'span[class^="help"]', 'IP address does not match the network CIDR',
            'True error message is displayed')
          .then(function() {
            return networksLib.gotoNodeNetworkGroup('default');
          })
          .then(function() {
            return networksLib.checkIncorrectValueInput();
          })
          // Cancel changes
          .then(function() {
            return networksLib.cancelChanges();
          })
          .then(function() {
            return networksLib.checkNetworkInitialState('Baremetal');
          });
      },
      'Baremetal Network "Use the whole CIDR" option works': function() {
        var ipRangeStart = '192.168.3.1';
        var ipRangeEnd = '192.168.3.254';
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
          .assertElementPropertyEquals(divIp + 'input[name*="range-start"]', 'value', ipRangeStart,
            'Baremetal "Start IP Range" textfield  has true value')
          .assertElementPropertyEquals(divIp + 'input[name*="range-end"]', 'value', ipRangeEnd,
            'Baremetal "End IP Range" textfield has true value')
          .assertElementNotExists(div + 'div.has-error', 'No Baremetal errors are observed')
          .then(function() {
            return networksLib.saveSettings();
          });
      }
    };
  });
});
