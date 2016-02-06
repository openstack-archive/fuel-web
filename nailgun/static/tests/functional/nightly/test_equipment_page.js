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
  'tests/functional/pages/clusters',
  'tests/functional/pages/dashboard',
  'tests/functional/pages/modal',
  'intern/dojo/node!leadfoot/Command',
  'tests/functional/nightly/library/generic',
  'tests/functional/nightly/library/equipment'
], function(registerSuite, Common, ClusterPage, DashboardPage, ModalWindow, Command, GenericLib,
  EquipmentLib) {
  'use strict';

  registerSuite(function() {
    var common,
      clusterPage,
      clusterName,
      dashboardPage,
      modal,
      command,
      genericLib,
      equipmentLib;
    var controllerName = '###EpicBoost###_Node_1';
    var computeName = '###EpicBoost###_Node_2';
    var correlationName = '###EpicBoost###';
    var computeMac = '';
    var computeIp = '';
    var nodesController = 2;
    var nodesCompute = 1;
    var nodesDiscover = 3;
    var nodesError = 1;
    var nodesOffline = 1;
    var nodesCluster = nodesController + nodesCompute;
    var totalNodes = nodesCluster + nodesDiscover + nodesError + nodesOffline;
    var inputArray = [totalNodes, nodesCluster, nodesDiscover, nodesError, nodesOffline];
    var filterArray = [nodesCluster + nodesDiscover, nodesCluster, nodesDiscover, 0, 0];
    var nodeSelector = 'div.node';
    var clusterSelector = nodeSelector + '.pending_addition';

    return {
      name: 'Nodes across environment',
      setup: function() {
        common = new Common(this.remote);
        clusterPage = new ClusterPage(this.remote);
        clusterName = common.pickRandomName('VLAN Cluster');
        dashboardPage = new DashboardPage(this.remote);
        modal = new ModalWindow(this.remote);
        command = new Command(this.remote);
        genericLib = new GenericLib(this.remote);
        equipmentLib = new EquipmentLib(this.remote);

        return this.remote
          .then(function() {
            return common.getIn();
          })
          .then(function() {
            return common.createCluster(clusterName);
          })
          .then(function() {
            return common.addNodesToCluster(nodesController, ['Controller']);
          })
          .then(function() {
            return common.addNodesToCluster(nodesCompute, ['Compute']);
          });
      },
      'Node settings pop-up contains environment and node network group names': function() {
        var ipSelector = 'div[aria-labelledby="headinginterfaces"] .node-details-row:nth-child(3)';
        var sumSelector = 'div.node-summary';
        var descriptionClusterNode = RegExp(
          'Environment.*' + clusterName + '[\\s\\S]*' +
          'Node network group.*default[\\s\\S]*', 'i');
        var descriptionDiscoveredNode = RegExp(
          '[\\s\\S]*[^(Environment)].*[^(' + clusterName + ')]' +
          '[\\s\\S]*[^(Node network group)].*[^(default)][\\s\\S]*', 'i');
        return this.remote
          .then(function() {
            return genericLib.gotoPage('Equipment');
          })
          .assertElementsExist('div.nodes-group div.node', '"Equipment" page is not empty')
          // Check correct nodes addiction
          .then(function() {
            return equipmentLib.checkNodesSegmentation('standard', inputArray, false);
          })
          .assertElementContainsText(clusterSelector + ':nth-child(1)', 'CONTROLLER',
              '"Controller" node #1 was successfully added to cluster')
          .assertElementContainsText(clusterSelector + ':nth-child(2)', 'CONTROLLER',
              '"Controller" node #2 was successfully added to cluster')
          .assertElementContainsText(clusterSelector + ':nth-child(3)', 'COMPUTE',
              '"Compute" node was successfully added to cluster')
          // Precondition
          .then(function() {
            return equipmentLib.renameNode(clusterSelector + ':first-child', controllerName);
          })
          .then(function() {
            return equipmentLib.renameNode(clusterSelector + ':last-child', computeName);
          })
          // Check "Pending Addition" node
          .assertElementsExist(clusterSelector + ':last-child div.node-settings',
            'Node settings button for Compute node exists')
          .clickByCssSelector(clusterSelector + ':last-child div.node-settings')
          .then(function() {
            return modal.waitToOpen();
          })
          .then(function() {
            return modal.checkTitle(computeName);
          })
          .assertElementMatchesRegExp(sumSelector, descriptionClusterNode,
            'Environment name and "default" node network group name are exist and correct')
          // Get IP and MAC for next tests
          .findByCssSelector(sumSelector + ' div:nth-child(4) > span')
            .getVisibleText()
            .then(function(visibleText) {
              computeMac = visibleText;
            })
            .end()
          .clickByCssSelector('div[id="headinginterfaces"] i')
          .findByCssSelector(ipSelector + ' span')
            .getVisibleText()
            .then(function(visibleText) {
              computeIp = visibleText;
            })
            .end()
          .then(function() {
            return modal.close();
          })
          // Check clean "Discovered" node
          .clickByCssSelector(nodeSelector + '.discover div.node-settings')
          .then(function() {
            return modal.waitToOpen();
          })
          .assertElementMatchesRegExp(sumSelector, descriptionDiscoveredNode,
            'Environment name and "default" node network group name are not observed')
          .then(function() {
            return modal.close();
          });
      },
      'Standard and Compact Node view support': function() {
        var preSelector = 'input[name="view_mode"][value="';
        var compactSelector = preSelector + 'compact"]';
        var standardSelector = preSelector + 'standard"]';
        return this.remote
          // Check Compact Node view
          .assertElementsExist(compactSelector, '"Compact Node" button is available')
          .findByCssSelector(compactSelector)
            .type('\uE00D')
            .end()
          .then(function() {
            return equipmentLib.checkNodesSegmentation('compact', inputArray, false);
          })
          // Check Standard Node view
          .assertElementsExist(standardSelector, '"Standard Node" button is available')
          .findByCssSelector(standardSelector)
            .type('\uE00D')
            .end()
          .then(function() {
            return equipmentLib.checkNodesSegmentation('standard', inputArray, false);
          });
      },
      'Quick Search support for "Equipment" page': function() {
        var nodeNameSelector = clusterSelector + ' div.name p';
        var btnClearSelector = 'button.btn-clear-search';
        var txtSearchSelector = 'input[name="search"]';
        return this.remote
          .assertElementsExist('button.btn-search', '"Quick Search" button is exists')
          .clickByCssSelector('button.btn-search')
          .assertElementsAppear(txtSearchSelector, 1000, 'Textfield for search value appears')
          // Controller search
          .setInputValue(txtSearchSelector, controllerName)
          .sleep(500)
          .assertElementsExist(nodeSelector, 1, 'Only one node with correct Controller name "' +
            controllerName + '" is observed')
          .assertElementTextEquals(nodeNameSelector, controllerName,
            'Controller node is searched correctly')
          .assertElementsExist(btnClearSelector, '"Clear Search" button is exists')
          .clickByCssSelector(btnClearSelector)
          .assertElementsExist(nodeSelector, totalNodes, 'Default nodes quantity is observed')
          .assertElementPropertyEquals(txtSearchSelector, 'value', '',
            'Textfield for search value is cleared')
          // "Empty" search
          .setInputValue(txtSearchSelector, '><+_')
          .sleep(500)
          .assertElementNotExists(nodeSelector, 'No nodes are observed')
          .assertElementMatchesRegExp('div.alert-warning',
            /.*No nodes found matching the selected filters.*/i,
            'Default warning message is observed')
          .clickByCssSelector(btnClearSelector)
          // Compute MAC address search
          .setInputValue(txtSearchSelector, computeMac)
          .sleep(500)
          .assertElementsExist(nodeSelector, 1, 'Only one node with correct Compute MAC address "' +
            computeMac + '" is observed')
          .assertElementTextEquals(nodeNameSelector, computeName,
            'Compute node is searched correctly')
          .clickByCssSelector(btnClearSelector)
          // Correlation of controller and compute search
          .setInputValue(txtSearchSelector, correlationName)
          .sleep(500)
          .assertElementsExist(nodeSelector, 2, 'Only two nodes with correlation of their names "' +
            correlationName + '" are observed')
          .assertElementTextEquals(clusterSelector + ':first-child div.name p', controllerName,
            'Controller node is searched correctly')
          .assertElementTextEquals(clusterSelector + ':last-child div.name p', computeName,
            'Compute node is searched correctly')
          .clickByCssSelector(btnClearSelector)
          // Compute IP address search
          .setInputValue(txtSearchSelector, computeIp)
          .sleep(500)
          .assertElementsExist(nodeSelector, 1, 'Only one node with correct Compute IP address "' +
            computeIp + '" is observed')
          .assertElementTextEquals(nodeNameSelector, computeName,
            'Compute node is searched correctly');
      },
      'Quick Search results saved after refreshing of page': function() {
        return this.remote
          .then(function() {
            return command.refresh();
          })
          .then(function() {
            return equipmentLib.checkSearchPageSwitching('Equipment', computeName);
          });
      },
      'Quick Search results saved after switching to other page': function() {
        return this.remote
          .then(function() {
            return equipmentLib.checkSearchPageSwitching('Environments', computeName);
          })
          .then(function() {
            return equipmentLib.checkSearchPageSwitching('Releases', computeName);
          })
          .then(function() {
            return equipmentLib.checkSearchPageSwitching('Plugins', computeName);
          })
          .then(function() {
            return equipmentLib.checkSearchPageSwitching('Support', computeName);
          })
          .clickByCssSelector('button.btn-clear-search');
      },
      'Sorting support for "Equipment" page': function() {
        return this.remote
          .assertElementsExist('button.btn-sorters', '"Sort Nodes" button is exists')
          .clickByCssSelector('button.btn-sorters')
          .assertElementsAppear('div.sorters', 1000, '"Sort" pane is appears')
          .then(function() {
            return equipmentLib.checkDefaultSorting('down', inputArray);
          })
          .clickByCssSelector('div.sort-by-status-asc .btn-default')
          .then(function() {
            return equipmentLib.checkDefaultSorting('up', inputArray);
          });
      },
      'Filtering support for "Equipment" page': function() {
        var filterSelector = 'div.filter-by-status';
        return this.remote
          .assertElementsExist('button.btn-filters', '"Filter Nodes" button is exists')
          .clickByCssSelector('button.btn-filters')
          .assertElementsAppear('div.filters', 1000, '"Filter" pane is appears')
          .then(function() {
            return equipmentLib.checkNodesSegmentation('standard', inputArray, false);
          })
          .assertElementsExist(filterSelector, 'Filter sorting block is observed')
          .assertElementContainsText(filterSelector + ' .btn-default', 'Status',
            'Filter by status is default')
          .clickByCssSelector(filterSelector + ' .btn-default')
          .assertElementsAppear('div.popover', 1000, '"Status" filter popover is appears')
          .clickByCssSelector('input[name="discover"]')
          .clickByCssSelector('input[name="pending_addition"]')
          .assertElementsAppear(filterSelector, 1000, 'Filter by status is appears')
          .then(function() {
            return equipmentLib.checkSortingPageSwitching('Equipment', filterArray);
          });
      },
      'Sorting and Filtering results saved after refreshing of page': function() {
        return this.remote
          .then(function() {
            return command.refresh();
          })
          .then(function() {
            return equipmentLib.checkSortingPageSwitching('Equipment', filterArray);
          });
      },
      'Sorting and Filtering results saved after switching to other page': function() {
        return this.remote
          .then(function() {
            return equipmentLib.checkSortingPageSwitching('Environments', filterArray);
          })
          .then(function() {
            return equipmentLib.checkSortingPageSwitching('Releases', filterArray);
          })
          .then(function() {
            return equipmentLib.checkSortingPageSwitching('Plugins', filterArray);
          })
          .then(function() {
            return equipmentLib.checkSortingPageSwitching('Support', filterArray);
          })
          .clickByCssSelector('button.btn-reset-filters');
      },
      '"Offline" node deletion from "Equipment" page': function() {
        var offlineSelector = nodeSelector + '.offline';
        return this.remote
          .assertElementsExist(offlineSelector, '"Offline" node is observed')
          .assertElementsExist(offlineSelector + ' button.node-remove-button',
            'Remove offline node button is exists')
          .clickByCssSelector(offlineSelector + ' button.node-remove-button')
          .then(function() {
            return modal.waitToOpen();
          })
          .then(function() {
            return modal.checkTitle('Remove Node');
          })
          .assertElementsExist('button.btn-danger.btn-delete', 'Remove button is exists')
          .clickByCssSelector('button.btn-danger.btn-delete')
          .then(function() {
            return modal.waitToClose();
          })
          .then(function() {
            return command.refresh();
          })
          .assertElementsAppear('div.equipment-page', 5000, 'Page refreshed successfully')
          .assertElementNotExists(offlineSelector, '"Offline" node is gone');
      },
      'Node groups segmentation on "Equipment" page': function() {
        return this.remote
          .then(function() {
            return genericLib.gotoPage('Environments');
          })
          // Start deployment
          .then(function() {
            return clusterPage.goToEnvironment(clusterName);
          })
          .then(function() {
            return dashboardPage.startDeployment();
          })
          .assertElementExists('.dashboard-block .progress', 'Deployment is started')
          // Check node groups segmentation
          .then(function() {
            return genericLib.gotoPage('Equipment');
          })
          .assertElementNotExists(clusterSelector, '"Pending Addition" node group is gone')
          .then(function() {
            return equipmentLib.checkNodesSegmentation('standard', inputArray, true);
          });
      }
    };
  });
});
