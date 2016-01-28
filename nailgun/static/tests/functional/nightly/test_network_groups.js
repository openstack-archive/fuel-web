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
          .clickByCssSelector('.subtab-link-Network_Group_1')
          .then(function() {
            return networksLib.checkVLANs('Network_Group_1', 'VLAN');
          })
          .clickByCssSelector('.subtab-link-default')
          .then(function() {
            return networksLib.checkVLANs('default', 'VLAN');
          });
      },
      'Gateways appear for two or more node network groups': function() {
        return this.remote
          .clickByCssSelector('.subtab-link-Network_Group_2')
          .then(function() {
            return networksLib.checkGateways('Network_Group_2', 'VLAN');
          })
          .clickByCssSelector('.subtab-link-Network_Group_1')
          .then(function() {
            return networksLib.checkGateways('Network_Group_1', 'VLAN');
          })
          .clickByCssSelector('.subtab-link-default')
          .then(function() {
            return networksLib.checkGateways('default', 'VLAN');
          })
          .clickByCssSelector('.subtab-link-Network_Group_1')
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
      'Can not create node network group with name of already existing group': function() {
        return this.remote
          .then(function() {
            return networksLib.createNetworkGroup('Network_Group_1');
          })
          .assertElementEnabled('button.add-nodegroup-btn',
            '"Add New Node Network Group" button is enabled')
          .clickByCssSelector('button.add-nodegroup-btn')
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
          .assertElementAppears('div.has-error.node-group-name span.help-block', 1000,
            'Error message appears')
          .assertElementContainsText('div.has-error.node-group-name span.help-block',
            'This node network group name is already taken', 'True error message presents')
          .then(function() {
            return modal.close();
          });
      },
      'Node network group deletion': function() {
        return this.remote
          .clickByCssSelector('.subtab-link-default')
          .assertElementNotExists('.glyphicon-remove',
            'It is not possible to delete default node network group')
          .assertElementContainsText('span.explanation',
            'This node network group uses a shared admin network and cannot be deleted',
            'Default node network group description presented')
          .clickByCssSelector('.subtab-link-Network_Group_1')
          .assertElementAppears('.glyphicon-remove', 1000, 'Remove icon is shown')
          .clickByCssSelector('.glyphicon-remove')
          .then(function() {
            return modal.waitToOpen();
          })
          .assertElementContainsText('h4.modal-title', 'Remove Node Network Group',
            'Remove Node Network Group modal expected')
          .then(function() {
            return modal.clickFooterButton('Delete');
          })
          .then(function() {
            return modal.waitToClose();
          })
          .assertElementDisappears('.subtab-link-Network_Group_1', 2000,
            'Node network group disappears from network group list')
          .assertElementNotContainsText('.network-group-name .btn-link', 'Network_Group_1',
            'Node network group title disappears from "Networks" tab');
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
        return this.remote
          .assertElementDisplayed('ul.node-network-groups-list',
            'Node network groups list displayed')
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
          .assertElementsAppear('a.subtab-link-default', 5000, 'Page refreshed successfully')
          .assertElementNotExists('a[class="subtab-link-+-934847fdjfjdbh"]',
            'Network group deleted successfully')
          .assertElementNotExists('a.subtab-link-yrter', 'Network group deleted successfully')
          .assertElementNotExists('a.subtab-link-1234', 'Network group deleted successfully')
          .assertElementNotExists('a.subtab-link-abc', 'Network group deleted successfully')
          .then(function() {
            return networksLib.deleteNetworkGroup('test');
          })
          .then(function() {
            return command.refresh();
          })
          .assertElementsAppear('a.subtab-link-default', 5000, 'Page refreshed successfully')
          .assertElementNotExists('a.subtab-link-abc',
            'Deletion of several node network groups one after another is successfull');
      },
      'Can not create node network group without saving changes': function() {
        return this.remote
          .assertElementEnabled('div.public div.ip_ranges input[name*="range-start"]',
            'Public "Start IP Range" textfield is enabled')
          .setInputValue('div.public div.ip_ranges input[name*="range-start"]', '172.16.0.25')
          .assertElementAppears('button.add-nodegroup-btn i.glyphicon-danger-sign', 1000,
            'Error icon appears')
          .assertElementEnabled('button.add-nodegroup-btn',
            '"Add New Node Network Group" button is enabled')
          .clickByCssSelector('button.add-nodegroup-btn')
          .then(function() {
            return modal.waitToOpen();
          })
          .then(function() {
            return modal.checkTitle('Node Network Group Creation Error');
          })
          .assertElementDisplayed('div.text-error', 'Error message exists')
          .assertElementContainsText('div.text-error',
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
        return this.remote
          .then(function() {
            return networksLib.createNetworkGroup('Network_Group_1');
          })
          .then(function() {
            return networksLib.createNetworkGroup('Network_Group_2');
          })
          .assertElementEnabled('div.public div.ip_ranges input[name*="range-start"]',
            'Public "Start IP Range" textfield is enabled')
          .setInputValue('div.public div.ip_ranges input[name*="range-start"]', '172.16.0.26')
          .assertElementEnabled('button.apply-btn',
            '"Save Settings" button is enabled for "Network_Group_2"')
          .clickByCssSelector('.subtab-link-Network_Group_1')
          .assertElementNotExists('div.modal-dialog',
            'No new dialogs appear for "Network_Group_1"')
          .assertElementNotExists('div.has-error', 'No errors are observed for "Network_Group_1"')
          .assertElementPropertyEquals('div.public div.ip_ranges input[name*="range-start"]',
            'value', '172.16.0.2',
            'Public "Start IP Range" textfield  has default value for "Network_Group_1"')
          .assertElementEnabled('button.apply-btn',
            '"Save Settings" button is enabled for "Network_Group_1"')
          .clickByCssSelector('.subtab-link-default')
          .assertElementNotExists('div.modal-dialog',
            'No new dialogs appear for "default" node network group')
          .assertElementNotExists('div.has-error',
            'No errors are observed for "default" node network group')
          .assertElementPropertyEquals('div.public div.ip_ranges input[name*="range-start"]',
            'value', '172.16.0.2',
            'Public "Start IP Range" textfield  has default value for "default" node network group')
          .assertElementEnabled('button.apply-btn',
            '"Save Settings" button is enabled for "default" node network group')
          .clickByCssSelector('.subtab-link-Network_Group_2')
          .assertElementNotExists('div.modal-dialog', 'No new dialogs appear for "Network_Group_2"')
          .assertElementNotExists('div.has-error', 'No errors are observed for "Network_Group_2"')
          .assertElementPropertyEquals('div.public div.ip_ranges input[name*="range-start"]',
            'value', '172.16.0.26', 'Public "Start IP Range" textfield  has changed value')
          .assertElementEnabled('button.apply-btn', '"Save Settings" button is enabled')
          .then(function() {
            return networksLib.cancelChanges();
          });
      },
      'The same VLAN for different node network groups': function() {
        return this.remote
          .clickByCssSelector('.subtab-link-Network_Group_1')
          .then(function() {
            return networksLib.checkGateways('Network_Group_1', 'TUN');
          })
          .then(function() {
            return networksLib.checkVLANs('Network_Group_1', 'TUN');
          })
          .clickByCssSelector('.subtab-link-Network_Group_2')
          .then(function() {
            return networksLib.checkVLANs('Network_Group_2', 'TUN');
          })
          .clickByCssSelector('.subtab-link-default')
          .then(function() {
            return networksLib.checkVLANs('default', 'TUN');
          });
      },
      'Gateways appear for two or more node network groups': function() {
        return this.remote
          .clickByCssSelector('.subtab-link-Network_Group_2')
          .then(function() {
            return networksLib.checkGateways('Network_Group_2', 'TUN');
          })
          .clickByCssSelector('.subtab-link-Network_Group_1')
          .then(function() {
            return networksLib.checkGateways('Network_Group_1', 'TUN');
          })
          .clickByCssSelector('.subtab-link-default')
          .then(function() {
            return networksLib.checkGateways('default', 'TUN');
          })
          .clickByCssSelector('.subtab-link-Network_Group_1')
          .then(function() {
            return networksLib.deleteNetworkGroup('Network_Group_1');
          })
          .then(function() {
            return networksLib.checkDefaultNetGroup();
          })
          .then(function() {
            return networksLib.checkGateways('default', 'TUN');
          })
          .assertElementEnabled('div.public input[name="gateway"]',
            'Public "Gateway" field exists and enabled for "default" network group');
      },
      'Validation between default and non-default groups': function() {
        return this.remote
          .clickByCssSelector('.subtab-link-default')
          .assertElementEnabled('div.management  div.cidr input[type="text"]',
            'Management  "CIDR" textfield is enabled')
          .setInputValue('div.management div.cidr input[type="text"]', '192.168.12.0/24')
          .assertElementPropertyEquals('div.management div.ip_ranges input[name*="range-start"]',
            'value', '192.168.12.2', 'Management "Start IP Range" textfield  has true value')
          .assertElementPropertyEquals('div.management div.ip_ranges input[name*="range-end"]',
            'value', '192.168.12.254', 'Management "End IP Range" textfield has true value')
          .assertElementPropertyEquals('div.management input[name="gateway"]', 'value',
            '192.168.12.1', 'Management "Gateway" textfield has true value')
          .then(function() {
            return networksLib.saveSettings();
          })
          .clickByCssSelector('.subtab-link-Network_Group_2')
          .assertElementEnabled('div.storage  div.cidr input[type="text"]',
            'Storage  "CIDR" textfield is enabled')
          .setInputValue('div.storage div.cidr input[type="text"]', '192.168.12.0/24')
          .assertElementPropertyEquals('div.storage div.ip_ranges input[name*="range-start"]',
            'value', '192.168.12.2', 'Storage "Start IP Range" textfield  has true value')
          .assertElementPropertyEquals('div.storage div.ip_ranges input[name*="range-end"]',
            'value', '192.168.12.254', 'Storage "End IP Range" textfield has true value')
          .assertElementPropertyEquals('div.storage input[name="gateway"]', 'value',
            '192.168.12.1', 'Storage "Gateway" textfield has true value')
          .assertElementEnabled('button.apply-btn', '"Save Settings" button is enabled')
          .clickByCssSelector('button.apply-btn')
          .assertElementExists('div.network-alert', 'Error message is observed')
          .assertElementContainsText('div.network-alert',
            'Address space intersection between networks', 'True error message is displayed')
          .assertElementContainsText('div.network-alert', 'management',
            'True error message is displayed')
          .assertElementContainsText('div.network-alert', 'storage',
            'True error message is displayed')
          .then(function() {
            return networksLib.cancelChanges();
          });
      },
      'Validation Floating IP range with non-default group with other CIDR': function() {
        return this.remote
          .clickByCssSelector('.subtab-link-Network_Group_2')
          .assertElementEnabled('div.public div.cidr input[type="text"]',
            'Public "CIDR" textfield is enabled')
          .setInputValue('div.public div.cidr input[type="text"]', '172.16.5.0/24')
          .assertElementEnabled('div.public div.ip_ranges input[name*="range-start"]',
            'Public "Start IP Range" textfield is enabled')
          .setInputValue('div.public div.ip_ranges input[name*="range-start"]', '172.16.5.2')
          .assertElementEnabled('div.public div.ip_ranges input[name*="range-end"]',
            'Public "End IP Range" textfield is enabled')
          .setInputValue('div.public div.ip_ranges input[name*="range-end"]', '172.16.5.126')
          .assertElementEnabled('div.public input[name="gateway"]',
            'Public "Gateway" textfield is enabled')
          .setInputValue('div.public input[name="gateway"]', '172.16.5.1')
          .assertElementEnabled('div.storage div.cidr input[type="text"]',
            'Storage "CIDR" textfield is enabled')
          .setInputValue('div.storage div.cidr input[type="text"]', '172.16.6.0/24')
          .assertElementEnabled('div.management  div.cidr input[type="text"]',
            'Management "CIDR" textfield is enabled')
          .setInputValue('div.management div.cidr input[type="text"]', '172.16.7.0/24')
          .clickByCssSelector('a[class$="neutron_l3"]')
          .assertElementEnabled('div.floating_ranges input[name*="start"]',
            'Floating IP ranges "Start" textfield is enabled')
          .setInputValue('div.floating_ranges input[name*="start"]', '172.16.5.130')
          .assertElementEnabled('div.floating_ranges input[name*="end"]',
            'Floating IP ranges "End" textfield is enabled')
          .setInputValue('div.floating_ranges input[name*="end"]', '172.16.5.254')
          .assertElementNotExists('div.has-error', 'No errors are observed')
          .then(function() {
            return networksLib.saveSettings();
          });
      },
      'Renaming of Default and non-default network groups': function() {
        return this.remote
          // Can rename "default" node network group
          .clickByCssSelector('.subtab-link-default')
          .clickByCssSelector('.glyphicon-pencil')
          .assertElementAppears('div.network-group-name input[type="text"]', 1000,
            'Rename network group textfield appears')
          .findByCssSelector('div.network-group-name input[type="text"]')
            .clearValue()
            .type('new_default')
            .type('\uE007')
            .end()
          .assertElementDisplayed('.subtab-link-new_default', 'New subtab title is shown')
          .assertElementTextEquals('div.network-group-name button.btn-link', 'new_default',
            'It is possible to rename "default" node network group')
          // Can not rename non-default node network group to "default" name
          .clickByCssSelector('.subtab-link-Network_Group_2')
          .clickByCssSelector('.glyphicon-pencil')
          .assertElementAppears('.network-group-name input[type=text]', 1000,
            'Node network group renaming control is rendered')
          .findByCssSelector('.node-group-renaming input[type=text]')
            .clearValue()
            .type('new_default')
            .type('\uE007')
            .end()
          .assertElementAppears('.has-error.node-group-renaming', 1000,
            'Error is displayed in case of duplicate name')
          .assertElementContainsText('div.has-error.node-group-renaming span.help-block',
            'This node network group name is already taken', 'True error message presents')
          // Rename non-default node network group
          .findByCssSelector('.node-group-renaming input[type=text]')
            .clearValue()
            .type('Network_Group_3')
            .type('\uE007')
            .end()
          .assertElementDisplayed('.subtab-link-Network_Group_3', 'New subtab title is shown')
          .assertElementTextEquals('div.network-group-name button.btn-link', 'Network_Group_3',
            'New network group name "link" is shown');
      },
      'Correct bahaviour of long name for node network group': function() {
        return this.remote
          .clickByCssSelector('.subtab-link-Network_Group_3')
          .assertElementPropertyEquals('li[data-reactid$="$Network_Group_3"]',
            'offsetHeight', '37', '"Network_Group_3" has default height')
          .assertElementPropertyEquals('li[data-reactid$="$Network_Group_3"]',
            'offsetWidth', '163', '"Network_Group_3" has default width')
          .clickByCssSelector('.glyphicon-pencil')
          .assertElementAppears('div.network-group-name input[type="text"]', 1000,
            'Rename network group textfield appears')
          .findByCssSelector('.node-group-renaming input[type=text]')
            .clearValue()
            .type('fgbhsjdkgbhsdjkbhsdjkbhfjkbhfbjhgjbhsfjgbhsfjgbhsg')
            .type('\uE007')
            .end()
          .assertElementDisplayed('.subtab-link-' +
            'fgbhsjdkgbhsdjkbhsdjkbhfjkbhfbjhgjbhsfjgbhsfjgbhsg', 'New subtab title is shown')
          .assertElementTextEquals('div.network-group-name button.btn-link',
            'fgbhsjdkgbhsdjkbhsdjkbhfjkbhfbjhgjbhsfjgbhsfjgbhsg',
            'New network group name "link" is shown')
          .assertElementPropertyEquals('li[data-reactid$="$' +
            'fgbhsjdkgbhsdjkbhsdjkbhfjkbhfbjhgjbhsfjgbhsfjgbhsg"]', 'offsetHeight', '87',
            'Renamed network group has correct height')
          .assertElementPropertyEquals('li[data-reactid$="$' +
            'fgbhsjdkgbhsdjkbhsdjkbhfjkbhfbjhgjbhsfjgbhsfjgbhsg"]', 'offsetWidth', '163',
            'Renamed network group has correct width');
      },
      'User can add and cannot rename new node network group after deployment': function() {
        this.timeout = 60000;
        return this.remote
          .then(function() {
            return clusterPage.goToTab('Dashboard');
          })
          .then(function() {
            return dashboardPage.startDeployment();
          })
          .waitForElementDeletion('.dashboard-block .progress', 45000)
          .then(function() {
            return clusterPage.goToTab('Networks');
          })
          .then(function() {
            return networksLib.createNetworkGroup('Network_Group_1');
          })
          .assertElementNotExists('.glyphicon-pencil',
            'It is not possible to rename new node network group after deployment');
      }
    };
  });
});
