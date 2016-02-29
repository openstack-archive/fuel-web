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
  'tests/functional/pages/modal',
  'tests/functional/pages/common',
  'tests/functional/pages/cluster',
  'tests/functional/pages/dashboard',
  'intern/dojo/node!leadfoot/Command',
  'tests/functional/nightly/library/networks'
], function(registerSuite, ModalWindow, Common, ClusterPage, DashboardPage, Command, NetworksLib) {
  'use strict';

  registerSuite(function() {
    var common,
      clusterPage,
      clusterName,
      networksLib;

    return {
      name: 'Neutron tunneling segmentation',
      setup: function() {
        common = new Common(this.remote);
        clusterPage = new ClusterPage(this.remote);
        networksLib = new NetworksLib(this.remote);
        clusterName = common.pickRandomName('Tunneling Cluster');

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
                    .clickByCssSelector('input[value*="neutron"][value$=":vlan"]')
                    .clickByCssSelector('input[value*="neutron"][value$=":tun"]');
                }
              }
            );
          })
          .then(function() {
            return common.addNodesToCluster(1, ['Controller']);
          })
          .then(function() {
            return common.addNodesToCluster(1, ['Compute']);
          })
          .then(function() {
            return clusterPage.goToTab('Networks');
          });
      },
      'The same VLAN for different node network groups': function() {
        return this.remote
          .then(function() {
            return networksLib.createNetworkGroup('Network_Group_1');
          })
          .then(function() {
            return networksLib.createNetworkGroup('Network_Group_2');
          })
          .then(function() {
            return networksLib.checkVLANs('Network_Group_2', 'VLAN');
          })
          .then(function() {
            return networksLib.gotoNodeNetworkSubTab('Network_Group_1');
          })
          .then(function() {
            return networksLib.checkVLANs('Network_Group_1', 'VLAN');
          })
          .then(function() {
            return networksLib.gotoNodeNetworkSubTab('default');
          })
          .then(function() {
            return networksLib.checkVLANs('default', 'VLAN');
          });
      },
      'Gateways appear for two or more node network groups': function() {
        return this.remote
          .then(function() {
            return networksLib.gotoNodeNetworkSubTab('Network_Group_2');
          })
          .then(function() {
            return networksLib.checkGateways('Network_Group_2', 'VLAN');
          })
          .then(function() {
            return networksLib.gotoNodeNetworkSubTab('Network_Group_1');
          })
          .then(function() {
            return networksLib.checkGateways('Network_Group_1', 'VLAN');
          })
          .then(function() {
            return networksLib.gotoNodeNetworkSubTab('default');
          })
          .then(function() {
            return networksLib.checkGateways('default', 'VLAN');
          })
          .then(function() {
            return networksLib.gotoNodeNetworkSubTab('Network_Group_1');
          })
          .then(function() {
            return networksLib.deleteNetworkGroup('Network_Group_1');
          })
          .then(function() {
            return networksLib.checkDefaultNetGroup();
          })
          .then(function() {
            return networksLib.checkGateways('default', 'VLAN');
          })
          .assertElementEnabled('div.public input[name="gateway"]',
            'Public "Gateway" field exists and enabled for "default" network group');
      }
    };
  });

  registerSuite(function() {
    var common,
      command,
      modal,
      clusterPage,
      clusterName,
      networksLib,
      dashboardPage;
    var networkName = 'Public';
    var publicSelector = 'div.' + networkName.toLowerCase() + ' ';
    var ipRangesSelector = publicSelector + 'div.ip_ranges ';
    var startIpSelector = ipRangesSelector + 'input[name*="range-start"] ';
    var gatewaySelector = publicSelector + 'input[name="gateway"] ';
    var errorSelector = 'div.has-error';
    var networkGroupsSelector = 'ul.node_network_groups';
    var btnSaveSelector = 'button.apply-btn';
    var addGroupSelector = 'button.add-nodegroup-btn';
    var pencilSelector = '.glyphicon-pencil';
    var renameSelector = 'div.network-group-name input[type="text"]';
    var nameSelector = 'div.network-group-name button.btn-link';

    return {
      name: 'Neutron VLAN segmentation',
      setup: function() {
        common = new Common(this.remote);
        command = new Command(this.remote);
        modal = new ModalWindow(this.remote);
        clusterPage = new ClusterPage(this.remote);
        networksLib = new NetworksLib(this.remote);
        dashboardPage = new DashboardPage(this.remote);
        clusterName = common.pickRandomName('VLAN Cluster');

        return this.remote
          .then(function() {
            return common.getIn();
          })
          .then(function() {
            return common.createCluster(clusterName);
          })
          .then(function() {
            return common.addNodesToCluster(1, ['Controller']);
          })
          .then(function() {
            return common.addNodesToCluster(1, ['Compute']);
          })
          .then(function() {
            return clusterPage.goToTab('Networks');
          });
      },
      'Can not create node network group with the name of already existing group': function() {
        var errorHelpSelector = 'div.has-error.node-group-name span.help-block';
        return this.remote
          .then(function() {
            return networksLib.createNetworkGroup('Network_Group_1');
          })
          .assertElementEnabled(addGroupSelector, '"Add New Node Network Group" button is enabled')
          .clickByCssSelector(addGroupSelector)
          .then(function() {
            return modal.waitToOpen();
          })
          .then(function() {
            return modal.checkTitle('Add New Node Network Group');
          })
          .findByCssSelector('input.node-group-input-name')
            .clearValue()
            .type('Network_Group_1')
            .type('\uE007')
            .end()
          .assertElementAppears(errorHelpSelector, 1000, 'Error message appears')
          .assertElementContainsText(errorHelpSelector,
            'This node network group name is already taken', 'True error message presents')
          .then(function() {
            return modal.close();
          });
      },
      'Node network group deletion': function() {
        return this.remote
          .then(function() {
            return networksLib.gotoNodeNetworkSubTab('default');
          })
          .assertElementNotExists('.glyphicon-remove',
            'It is not possible to delete default node network group')
          .assertElementContainsText('span.explanation',
            'This node network group uses a shared admin network and cannot be deleted',
            'Default node network group description presented')
          .then(function() {
            return networksLib.deleteNetworkGroup('Network_Group_1');
          });
      },
      'Default network group the first in a list': function() {
        this.timeout = 60000;
        return this.remote
          .then(function() {
            return networksLib.createNetworkGroup('test');
          })
          .then(function() {
            return networksLib.checkDefaultNetGroup();
          })
          .then(function() {
            return networksLib.createNetworkGroup('abc');
          })
          .then(function() {
            return networksLib.checkDefaultNetGroup();
          })
          .then(function() {
            return networksLib.createNetworkGroup('1234');
          })
          .then(function() {
            return networksLib.checkDefaultNetGroup();
          })
          .then(function() {
            return networksLib.createNetworkGroup('yrter');
          })
          .then(function() {
            return networksLib.checkDefaultNetGroup();
          })
          .then(function() {
            return networksLib.createNetworkGroup('+-934847fdjfjdbh');
          })
          .then(function() {
            return networksLib.checkDefaultNetGroup();
          });
      },
      'Deletion of several node network groups one after another': function() {
        this.timeout = 60000;
        var explanationSelector = '.network-group-name .explanation';
        return this.remote
          .then(function() {
            return networksLib.deleteNetworkGroup('+-934847fdjfjdbh');
          })
          .then(function() {
            return networksLib.deleteNetworkGroup('yrter');
          })
          .then(function() {
            return networksLib.deleteNetworkGroup('1234');
          })
          .then(function() {
            return networksLib.deleteNetworkGroup('abc');
          })
          .then(function() {
            return command.refresh();
          })
          .assertElementsAppear(explanationSelector, 5000, 'Page refreshed successfully')
          .assertElementNotContainsText(networkGroupsSelector, '+-934847fdjfjdbh',
            'Network group deleted successfully')
          .assertElementNotContainsText(networkGroupsSelector, 'yrter',
            'Network group deleted successfully')
          .assertElementNotContainsText(networkGroupsSelector, '1234',
            'Network group deleted successfully')
          .assertElementNotContainsText(networkGroupsSelector, 'abc',
            'Network group deleted successfully')
          .then(function() {
            return networksLib.deleteNetworkGroup('test');
          })
          .then(function() {
            return command.refresh();
          })
          .assertElementsAppear(explanationSelector, 5000, 'Page refreshed successfully')
          .assertElementNotContainsText(networkGroupsSelector, 'test',
            'Deletion of several node network groups one after another is successfull');
      },
      'Can not create node network group without saving changes': function() {
        var errorTextSelector = 'div.text-error';
        var ipRangeStart = '172.16.0.25';
        return this.remote
          .assertElementEnabled(startIpSelector, 'Public "Start IP Range" textfield is enabled')
          .setInputValue(startIpSelector, ipRangeStart)
          .assertElementAppears('button.add-nodegroup-btn i.glyphicon-danger-sign', 1000,
            'Error icon appears')
          .assertElementEnabled(addGroupSelector, '"Add New Node Network Group" button is enabled')
          .clickByCssSelector(addGroupSelector)
          .then(function() {
            return modal.waitToOpen();
          })
          .then(function() {
            return modal.checkTitle('Node Network Group Creation Error');
          })
          .assertElementDisplayed(errorTextSelector, 'Error message exists')
          .assertElementContainsText(errorTextSelector,
            'It is necessary to save changes before creating a new node network group',
            'True error message presents')
          .then(function() {
            return modal.close();
          })
          .then(function() {
            return networksLib.cancelChanges();
          });
      },
      'Switching between node network groups without saved changes': function() {
        var modalSelector = 'div.modal-dialog';
        var group1Name = 'Network_Group_1';
        var group2Name = 'Network_Group_2';
        var startIpChanged = '172.16.0.26';
        var startIpDefault = '172.16.0.2';
        return this.remote
          .then(function() {
            return networksLib.createNetworkGroup(group1Name);
          })
          .then(function() {
            return networksLib.createNetworkGroup(group2Name);
          })
          .assertElementEnabled(startIpSelector, 'Public "Start IP Range" textfield is enabled')
          .setInputValue(startIpSelector, startIpChanged)
          .assertElementEnabled(btnSaveSelector,
            '"Save Settings" button is enabled for ' + group2Name)
          .then(function() {
            return networksLib.gotoNodeNetworkSubTab(group1Name);
          })
          .assertElementNotExists(modalSelector, 'No new dialogs appear for ' + group1Name)
          .assertElementNotExists(errorSelector, 'No errors are observed for ' + group1Name)
          .assertElementPropertyEquals(startIpSelector, 'value', startIpDefault,
            'Public "Start IP Range" textfield  has default value for ' + group1Name)
          .assertElementEnabled(btnSaveSelector,
            '"Save Settings" button is enabled for ' + group1Name)
          .then(function() {
            return networksLib.gotoNodeNetworkSubTab('default');
          })
          .assertElementNotExists(modalSelector,
            'No new dialogs appear for "default" node network group')
          .assertElementNotExists(errorSelector,
            'No errors are observed for "default" node network group')
          .assertElementPropertyEquals(startIpSelector, 'value', startIpDefault,
            'Public "Start IP Range" textfield  has default value for "default" node network group')
          .assertElementEnabled(btnSaveSelector,
            '"Save Settings" button is enabled for "default" node network group')
          .then(function() {
            return networksLib.gotoNodeNetworkSubTab(group2Name);
          })
          .assertElementNotExists(modalSelector, 'No new dialogs appear for ' + group2Name)
          .assertElementNotExists(errorSelector, 'No errors are observed for ' + group2Name)
          .assertElementPropertyEquals(startIpSelector, 'value', startIpChanged,
            'Public "Start IP Range" textfield  has changed value')
          .assertElementEnabled(btnSaveSelector, '"Save Settings" button is enabled')
          .then(function() {
            return networksLib.cancelChanges();
          });
      },
      'The same VLAN for different node network groups': function() {
        return this.remote
          .then(function() {
            return networksLib.gotoNodeNetworkSubTab('Network_Group_1');
          })
          .then(function() {
            return networksLib.checkGateways('Network_Group_1', 'TUN');
          })
          .then(function() {
            return networksLib.checkVLANs('Network_Group_1', 'TUN');
          })
          .then(function() {
            return networksLib.gotoNodeNetworkSubTab('Network_Group_2');
          })
          .then(function() {
            return networksLib.checkVLANs('Network_Group_2', 'TUN');
          })
          .then(function() {
            return networksLib.gotoNodeNetworkSubTab('default');
          })
          .then(function() {
            return networksLib.checkVLANs('default', 'TUN');
          });
      },
      'Gateways appear for two or more node network groups': function() {
        return this.remote
          .then(function() {
            return networksLib.gotoNodeNetworkSubTab('Network_Group_2');
          })
          .then(function() {
            return networksLib.checkGateways('Network_Group_2', 'TUN');
          })
          .then(function() {
            return networksLib.gotoNodeNetworkSubTab('Network_Group_1');
          })
          .then(function() {
            return networksLib.checkGateways('Network_Group_1', 'TUN');
          })
          .then(function() {
            return networksLib.gotoNodeNetworkSubTab('default');
          })
          .then(function() {
            return networksLib.checkGateways('default', 'TUN');
          })
          .then(function() {
            return networksLib.gotoNodeNetworkSubTab('Network_Group_1');
          })
          .then(function() {
            return networksLib.deleteNetworkGroup('Network_Group_1');
          })
          .then(function() {
            return networksLib.checkDefaultNetGroup();
          })
          .then(function() {
            return networksLib.checkGateways('default', 'TUN');
          })
          .assertElementEnabled(gatewaySelector,
            'Public "Gateway" field exists and enabled for "default" network group');
      },
      'Validation between default and non-default groups': function() {
        var networkAlertSelector = 'div.network-alert';
        var cidrValue = '192.168.12.0/24';
        var ipRangeStart = '192.168.12.2';
        var ipRangeEnd = '192.168.12.254';
        var gatewayArray = '192.168.12.1';
        return this.remote
          .then(function() {
            return networksLib.gotoNodeNetworkSubTab('default');
          })
          .assertElementEnabled('div.management  div.cidr input[type="text"]',
            'Management  "CIDR" textfield is enabled')
          .setInputValue('div.management div.cidr input[type="text"]', cidrValue)
          .assertElementPropertyEquals('div.management div.ip_ranges input[name*="range-start"]',
            'value', ipRangeStart, 'Management "Start IP Range" textfield  has true value')
          .assertElementPropertyEquals('div.management div.ip_ranges input[name*="range-end"]',
            'value', ipRangeEnd, 'Management "End IP Range" textfield has true value')
          .assertElementPropertyEquals('div.management input[name="gateway"]',
            'value', gatewayArray, 'Management "Gateway" textfield has true value')
          .then(function() {
            return networksLib.saveSettings();
          })
          .then(function() {
            return networksLib.gotoNodeNetworkSubTab('Network_Group_2');
          })
          .assertElementEnabled('div.storage  div.cidr input[type="text"]',
            'Storage  "CIDR" textfield is enabled')
          .setInputValue('div.storage div.cidr input[type="text"]', cidrValue)
          .assertElementPropertyEquals('div.storage div.ip_ranges input[name*="range-start"]',
            'value', ipRangeStart, 'Storage "Start IP Range" textfield  has true value')
          .assertElementPropertyEquals('div.storage div.ip_ranges input[name*="range-end"]',
            'value', ipRangeEnd, 'Storage "End IP Range" textfield has true value')
          .assertElementPropertyEquals('div.storage input[name="gateway"]',
            'value', gatewayArray, 'Storage "Gateway" textfield has true value')
          .assertElementEnabled(btnSaveSelector, '"Save Settings" button is enabled')
          .clickByCssSelector(btnSaveSelector)
          .assertElementExists(networkAlertSelector, 'Error message is observed')
          .assertElementContainsText(networkAlertSelector,
            'Address space intersection between networks', 'True error message is displayed')
          .assertElementContainsText(networkAlertSelector, 'management',
            'True error message is displayed')
          .assertElementContainsText(networkAlertSelector, 'storage',
            'True error message is displayed')
          .then(function() {
            return networksLib.cancelChanges();
          });
      },
      'Validation Floating IP range with non-default group with other CIDR': function() {
        var endIpSelector = ipRangesSelector + 'input[name*="range-end"] ';
        var cidrArray = ['172.16.5.0/24', '172.16.6.0/24', '172.16.7.0/24'];
        var ipRangeStart = ['172.16.5.2', '172.16.5.130'];
        var ipRangeEnd = ['172.16.5.126', '172.16.5.254'];
        var gatewayValue = '172.16.5.1';
        return this.remote
          .then(function() {
            return networksLib.gotoNodeNetworkSubTab('Network_Group_2');
          })
          .assertElementEnabled('div.public div.cidr input[type="text"]',
            'Public "CIDR" textfield is enabled')
          .setInputValue('div.public div.cidr input[type="text"]', cidrArray[0])
          .assertElementEnabled(startIpSelector,
            'Public "Start IP Range" textfield is enabled')
          .setInputValue(startIpSelector, ipRangeStart[0])
          .assertElementEnabled(endIpSelector, 'Public "End IP Range" textfield is enabled')
          .setInputValue(endIpSelector, ipRangeEnd[0])
          .assertElementEnabled(gatewaySelector,
            'Public "Gateway" textfield is enabled')
          .setInputValue(gatewaySelector, gatewayValue)
          .assertElementEnabled('div.storage div.cidr input[type="text"]',
            'Storage "CIDR" textfield is enabled')
          .setInputValue('div.storage div.cidr input[type="text"]', cidrArray[1])
          .assertElementEnabled('div.management  div.cidr input[type="text"]',
            'Management "CIDR" textfield is enabled')
          .setInputValue('div.management div.cidr input[type="text"]', cidrArray[2])
          .clickByCssSelector('a.subtab-link-neutron_l3')
          .assertElementEnabled('div.floating_ranges input[name*="start"]',
            'Floating IP ranges "Start" textfield is enabled')
          .setInputValue('div.floating_ranges input[name*="start"]', ipRangeStart[1])
          .assertElementEnabled('div.floating_ranges input[name*="end"]',
            'Floating IP ranges "End" textfield is enabled')
          .setInputValue('div.floating_ranges input[name*="end"]', ipRangeEnd[1])
          .assertElementNotExists(errorSelector, 'No errors are observed')
          .then(function() {
            return networksLib.saveSettings();
          });
      },
      'Renaming of Default and non-default network groups': function() {
        var errorRenameSelector = '.has-error.node-group-renaming ';
        return this.remote
          // Can rename "default" node network group
          .then(function() {
            return networksLib.gotoNodeNetworkSubTab('default');
          })
          .clickByCssSelector(pencilSelector)
          .assertElementAppears(renameSelector, 1000, 'Rename network group textfield appears')
          .findByCssSelector(renameSelector)
            .clearValue()
            .type('new_default')
            .type('\uE007')
            .end()
          .assertElementContainsText(networkGroupsSelector, 'new_default',
            'New subtab title is shown')
          .assertElementTextEquals(nameSelector, 'new_default',
            'It is possible to rename "default" node network group')
          // Can not rename non-default node network group to "default" name
          .then(function() {
            return networksLib.gotoNodeNetworkSubTab('Network_Group_2');
          })
          .clickByCssSelector(pencilSelector)
          .assertElementAppears(renameSelector, 1000, 'Node network group renaming control exists')
          .findByCssSelector(renameSelector)
            .clearValue()
            .type('new_default')
            .type('\uE007')
            .end()
          .assertElementAppears(errorRenameSelector, 1000,
            'Error is displayed in case of duplicate name')
          .assertElementContainsText(errorRenameSelector + 'span.help-block',
            'This node network group name is already taken', 'True error message presents')
          // Rename non-default node network group
          .findByCssSelector(renameSelector)
            .clearValue()
            .type('Network_Group_3')
            .type('\uE007')
            .end()
          .assertElementContainsText(networkGroupsSelector, 'Network_Group_3',
            'New subtab title is shown')
          .assertElementTextEquals(nameSelector, 'Network_Group_3',
            'New network group name "link" is shown');
      },
      'Correct bahaviour of long name for node network group': function() {
        var oldName = 'Network_Group_3';
        var newName = 'fgbhsjdkgbhsdjkbhsdjkbhfjkbhfbjhgjbhsfjgbhsfjgbhsg';
        var activeSelector = networkGroupsSelector + ' li.active';
        return this.remote
          .then(function() {
            return networksLib.gotoNodeNetworkSubTab(oldName);
          })
          .assertElementTextEquals(activeSelector, oldName,
            oldName + ' node network group is selected')
          .assertElementPropertyEquals(activeSelector, 'offsetHeight', '37',
            oldName + ' node network group has default height')
          .assertElementPropertyEquals(activeSelector, 'offsetWidth', '163',
            oldName + ' node network group has default width')
          .clickByCssSelector(pencilSelector)
          .assertElementAppears(renameSelector, 1000, 'Node network group Rename textfield appears')
          .findByCssSelector(renameSelector)
            .clearValue()
            .type(newName)
            .type('\uE007')
            .end()
          .assertElementTextEquals(activeSelector, newName,
            'New node network group ' + newName + ' is shown and selected')
          .assertElementTextEquals(nameSelector, newName,
            'New node network group name "link" is shown')
          .assertElementPropertyEquals(activeSelector, 'offsetHeight', '87',
            'Renamed node network group has correct height')
          .assertElementPropertyEquals(activeSelector, 'offsetWidth', '163',
            'Renamed node network group has correct width');
      },
      'User can add and cannot rename new node network group after deployment': function() {
        this.timeout = 60000;
        var progressSelector = '.dashboard-block .progress';
        return this.remote
          .then(function() {
            return clusterPage.goToTab('Dashboard');
          })
          .then(function() {
            return dashboardPage.startDeployment();
          })
          .assertElementExists(progressSelector, 'Deployment is started')
          .waitForElementDeletion(progressSelector, 45000)
          .then(function() {
            return clusterPage.goToTab('Networks');
          })
          .then(function() {
            return networksLib.createNetworkGroup('Network_Group_1');
          })
          .assertElementNotExists(pencilSelector,
            'It is not possible to rename new node network group after deployment');
      }
    };
  });
});
