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
  'tests/functional/nightly/library/networks',
  'tests/functional/nightly/library/settings'
], function(registerSuite, Common, ClusterPage, NetworksLib, SettingsLib) {
  'use strict';

  registerSuite(function() {
    var common,
      clusterPage,
      clusterName,
      networksLib,
      settingsLib;
    var networkName = 'Baremetal';
    var baremetalSelector = 'div.' + networkName.toLowerCase() + ' ';
    var ipRangesSelector = baremetalSelector + 'div.ip_ranges ';
    var cidrSelector = baremetalSelector + 'div.cidr input[type="text"]';
    var vlanSelector = baremetalSelector + 'div.vlan_start input[type="text"]';
    var vlanErrorSelector = baremetalSelector + 'div.vlan_start div.has-error span[class^="help"]';
    var errorSelector = baremetalSelector + 'div.has-error ';
    var startIpSelector = ipRangesSelector + 'input[name*="range-start"] ';
    var endIpSelector = ipRangesSelector + 'input[name*="range-end"] ';

    return {
      name: 'GUI support for Ironic',
      setup: function() {
        // Create cluster with additional service "Ironic"
        common = new Common(this.remote);
        clusterPage = new ClusterPage(this.remote);
        networksLib = new NetworksLib(this.remote);
        settingsLib = new SettingsLib(this.remote);
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
        var ironicSelector = 'input[name=ironic]:enabled:checked';
        return this.remote
          // Check Ironic item on Settings tab
          .then(function() {
            return clusterPage.goToTab('Settings');
          })
          .then(function() {
            return settingsLib.gotoOpenStackSettings('OpenStack Services');
          })
          .assertElementsExist(ironicSelector, 'Ironic checkbox is enabled and selected')
          // Check "Baremetal Network" initial state
          .then(function() {
            return clusterPage.goToTab('Networks');
          })
          .then(function() {
            return networksLib.checkNetworkInitialState(networkName);
          });
      },
      'Baremetal Network "IP Ranges" correct changing': function() {
        var correctIpRange = ['192.168.3.15', '192.168.3.100'];
        return this.remote
          // Change network settings
          .setInputValue(startIpSelector, correctIpRange[0])
          .setInputValue(endIpSelector, correctIpRange[1])
          .assertElementNotExists(errorSelector, 'No Baremetal errors are observed')
          .then(function() {
            return networksLib.saveSettings();
          });
      },
      'Baremetal Network "IP Ranges" adding and deleting additional fields': function() {
        var correctIpRange = ['192.168.3.1', '192.168.3.50'];
        var newIpRange = ['192.168.3.55', '192.168.3.70'];
        return this.remote
          // Change network settings
          .setInputValue(startIpSelector, correctIpRange[0])
          .setInputValue(endIpSelector, correctIpRange[1])
          // Add new IP range
          .then(function() {
            return networksLib.addNewIpRange(networkName, newIpRange);
          })
          .then(function() {
            return networksLib.saveSettings();
          })
          // Remove just added IP range
          .then(function() {
            return networksLib.deleteIpRange(networkName);
          })
          .then(function() {
            return networksLib.saveSettings();
          });
      },
      'Baremetal and other networks intersections': function() {
        this.timeout = 45000;
        // [Baremetal CIDR, Baremetal Start IP, Baremetal End IP, Ironic Start IP,
        // Ironic End IP, Ironic Gateway]
        var storageValues = ['192.168.1.0/24', '192.168.1.1', '192.168.1.50', '192.168.1.52',
          '192.168.1.254', '192.168.1.51'];
        var managementValues = ['192.168.0.0/24', '192.168.0.1', '192.168.0.50', '192.168.0.52',
          '192.168.0.254', '192.168.0.51'];
        var publicValues = ['172.16.0.0/24', '172.16.0.1', '172.16.0.50', '172.16.0.51',
          '172.16.0.254', '172.16.0.52'];
        return this.remote
          .then(function() {
            return networksLib.checkBaremetalIntersection('storage', storageValues);
          })
          .then(function() {
            return networksLib.checkBaremetalIntersection('management', managementValues);
          })
          .then(function() {
            return networksLib.checkBaremetalIntersection('public', publicValues);
          });
      },
      'Baremetal Network "Use VLAN tagging" option works': function() {
        var chboxVlanSelector = baremetalSelector + 'div.vlan_start input[type="checkbox"]';
        var vlanTag = '104';
        return this.remote
          // Unselect "Use VLAN tagging" option
          .clickByCssSelector(chboxVlanSelector)
          .assertElementNotSelected(chboxVlanSelector + ':enabled',
            'Baremetal "Use VLAN tagging" checkbox is enabled and not selected')
          .assertElementNotExists(vlanSelector,
            'Baremetal "Use VLAN tagging" textfield does not exist')
          .assertElementNotExists(errorSelector, 'No Baremetal errors are observed')
          .then(function() {
            return networksLib.saveSettings();
          })
          // Select back "Use VLAN tagging" option
          .clickByCssSelector(chboxVlanSelector)
          .assertElementsExist(chboxVlanSelector + ':enabled:checked',
            'Baremetal "Use VLAN tagging" checkbox is enabled and selected')
          .assertElementEnabled(vlanSelector,
            'Baremetal "Use VLAN tagging" textfield is enabled')
          .assertElementContainsText(vlanErrorSelector,
            'Invalid VLAN ID', 'True error message is displayed')
          .setInputValue(vlanSelector, vlanTag)
          .assertElementNotExists(errorSelector, 'No Baremetal errors are observed')
          .then(function() {
            return networksLib.saveSettings();
          });
      },
      'Baremetal Network "Use VLAN tagging" option validation': function() {
        var btnSaveSelector = 'button.apply-btn';
        var vlanTag = ['0', '10000', '4095', '', '1', '4094'];
        var errorMessage = 'Invalid VLAN ID';
        return this.remote
          // Check "Use VLAN tagging" text field
          .then(function() {
            return networksLib.checkIncorrectValueInput(vlanSelector, vlanTag[0], vlanErrorSelector,
              errorMessage);
          })
          .then(function() {
            return networksLib.checkIncorrectValueInput(vlanSelector, vlanTag[1], vlanErrorSelector,
              errorMessage);
          })
          .then(function() {
            return networksLib.checkIncorrectValueInput(vlanSelector, vlanTag[2], vlanErrorSelector,
              errorMessage);
          })
          .then(function() {
            return networksLib.checkIncorrectValueInput(vlanSelector, vlanTag[3], vlanErrorSelector,
              errorMessage);
          })
          .setInputValue(vlanSelector, vlanTag[4])
          .assertElementNotExists(errorSelector, 'No Baremetal errors are observed')
          .assertElementEnabled(btnSaveSelector, 'Save Settings button is enabled')
          .setInputValue(vlanSelector, vlanTag[5])
          .assertElementNotExists(errorSelector, 'No Baremetal errors are observed')
          .assertElementEnabled(btnSaveSelector, 'Save Settings button is enabled')
          // Cancel changes
          .then(function() {
            return networksLib.cancelChanges();
          })
          .then(function() {
            return networksLib.checkNetworkInitialState(networkName);
          });
      },
      'Baremetal Network "CIDR" field validation': function() {
        var cidrErrorSelector = baremetalSelector + 'div.cidr div.has-error span[class^="help"]';
        var l3Selector = 'a[class$="neutron_l3"] ';
        var cidrPart1 = '192.168.3.0/';
        var cidrPart2 = ['245', '0', '1', '31', '33', '25'];
        var errorMessage = 'Invalid CIDR';
        return this.remote
          // Check "CIDR" text field
          .then(function() {
            return networksLib.checkIncorrectValueInput(cidrSelector, cidrPart1 + cidrPart2[0],
              cidrErrorSelector, errorMessage);
          })
          .then(function() {
            return networksLib.checkIncorrectValueInput(cidrSelector, cidrPart1 + cidrPart2[1],
              cidrErrorSelector, errorMessage);
          })
          .then(function() {
            return networksLib.checkIncorrectValueInput(cidrSelector, cidrPart1 + cidrPart2[2],
              cidrErrorSelector, 'Network is too large');
          })
          .then(function() {
            return networksLib.checkIncorrectValueInput(cidrSelector, cidrPart1 + cidrPart2[3],
              cidrErrorSelector, 'Network is too small');
          })
          .then(function() {
            return networksLib.checkIncorrectValueInput(cidrSelector, cidrPart1 + cidrPart2[4],
              cidrErrorSelector, errorMessage);
          })
          .setInputValue(cidrSelector, cidrPart1 + cidrPart2[5])
          .assertElementExists(l3Selector, '"Neutron L3" link exists')
          .assertElementExists(l3Selector + 'i.glyphicon-danger-sign',
            'Error icon is observed before Neutron L3 link')
          .clickByCssSelector(l3Selector)
          .assertElementExists('div.has-error input[name="range-end_baremetal_range"]',
            '"Ironic IP range" End textfield is "red" marked')
          .assertElementContainsText('div.form-baremetal-network div.validation-error ' +
            'span[class^="help"]', 'IP address does not match the network CIDR',
            'True error message is displayed')
          .then(function() {
            return networksLib.checkMultirackVerification();
          })
          // Cancel changes
          .then(function() {
            return networksLib.cancelChanges();
          })
          .then(function() {
            return networksLib.checkNetworkInitialState(networkName);
          });
      },
      'Baremetal Network "Use the whole CIDR" option works': function() {
        return this.remote
          .then(function() {
            return networksLib.checkCidrOption(networkName);
          })
          .then(function() {
            return networksLib.saveSettings();
          });
      }
    };
  });
});
