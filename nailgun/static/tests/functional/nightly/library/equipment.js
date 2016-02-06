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
  'tests/functional/nightly/library/generic',
  'tests/functional/helpers'
], function(GenericLib) {
  'use strict';

  function EquipmentLib(remote) {
    this.remote = remote;
    this.generic = new GenericLib(remote);
  }

  EquipmentLib.prototype = {
    constructor: EquipmentLib,
    nodeSelector: 'div.node',

    checkNodesSegmentation: function(nodeView, nodesQuantity, provisioningFlag) {
      // Input array: Nodes quantity by groups.
      // [Total, Pending Addition (Provisioning), Discover, Error, Offline]
      var nodeSel = this.nodeSelector;
      var tempSelector = '.';
      var clusterSelector = 'pending_addition';
      if (nodeView === 'compact') {
        nodeSel = 'div.compact-node';
        tempSelector = ' div.';
      } else if (nodeView !== 'standard') {
        throw new Error('Invalid input value. Check nodeView: "' + nodeView +
          '" parameter and restart test.');
      }
      if (provisioningFlag) {
        clusterSelector = 'provisioning';
      }
      return this.remote
        .assertElementsAppear(nodeSel, 1000, '"' + nodeView + ' Node" view is loaded')
        .assertElementsExist(nodeSel, nodesQuantity[0],
          'Default nodes quantity is observed')
        .assertElementsExist(nodeSel + tempSelector + clusterSelector, nodesQuantity[1],
          '"Pending Addition/Provisioning" nodes are observed in "' + nodeView + '"" view')
        .assertElementsExist(nodeSel + tempSelector + 'discover', nodesQuantity[2],
          '"Discovered" nodes are observed in "' + nodeView + '"" view')
        .assertElementsExist(nodeSel + tempSelector + 'error', nodesQuantity[3],
          '"Error" nodes are observed in "' + nodeView + '"" view')
        .assertElementsExist(nodeSel + tempSelector + 'offline', nodesQuantity[4],
          '"Offline" nodes are observed in "' + nodeView + '"" view');
    },
    renameNode: function(nodeSelector, newName) {
      var nodeNameSelector = 'div.name p';
      var inputSelector = 'input.node-name-input';
      return this.remote
        .assertElementsExist(nodeSelector, 'Node to rename exists')
        .findByCssSelector(nodeSelector)
          .assertElementsExist(nodeNameSelector, 'Node name textlink exists')
          .clickByCssSelector(nodeNameSelector)
          .assertElementsAppear(inputSelector, 500, 'Rename textfield appears')
          .findByCssSelector(inputSelector)
            .clearValue()
            .type(newName)
            .pressKeys('\uE007')
            .end()
          .assertElementsAppear(nodeNameSelector, 1000, 'Node new name textlink appears')
          .assertElementTextEquals(nodeNameSelector, newName, 'Node name is changed successfully')
          .end();
    },
    checkSearchPageSwitching: function(pageName, nodeName) {
      var self = this;
      return this.remote
        .then(function() {
          return self.generic.gotoPage(pageName);
        })
        .then(function() {
          return self.generic.gotoPage('Equipment');
        })
        .assertElementsExist(this.nodeSelector, 1,
          'Search result saved after switching to "' + pageName + '"" page')
        .assertElementContainsText(this.nodeSelector + ' div.name p', nodeName,
          'Search result is correct after switching to "' + pageName + '"" page');
    },
    checkSortingPageSwitching: function(pageName, nodesQuantity) {
      // Input array: Nodes quantity by groups.
      // [Total, Pending Addition, Discover]
      var self = this;
      var groupSelector = 'div.nodes-group';
      return this.remote
        .then(function() {
          return self.generic.gotoPage(pageName);
        })
        .then(function() {
          return self.generic.gotoPage('Equipment');
        })
        .assertElementsExist(this.nodeSelector, nodesQuantity[0],
          'Filtered nodes quantity is observed after switching to "' + pageName + '"" page')
        .assertElementsExist(groupSelector, 2, 'Only "Pending Addition" and "Discovered"' +
          'node groups are correctly filtered after switching to "' + pageName + '"" page')
        .assertElementContainsText(groupSelector + ':nth-child(2) h4', 'Pending Addition',
          '"Pending Addition" node group is correctly sorted after' +
          'switching to "' + pageName + '"" page')
        .assertElementsExist(groupSelector + ':nth-child(2) div.node.pending_addition',
          nodesQuantity[1], 'Default quantity of "Pending Addition" nodes is observed after' +
          'switching to "' + pageName + '"" page')
        .assertElementContainsText(groupSelector + ':nth-child(1) h4', 'Discovered',
          '"Discovered" node group is correctly sorted after switching to "' + pageName + '"" page')
        .assertElementsExist(groupSelector + ':nth-child(1) div.node.discover',
          nodesQuantity[2], 'Default quantity of "Discovered" nodes is observed after' +
          'switching to "' + pageName + '"" page');
    },
    checkDefaultSorting: function(sortDirection, nodesQuantity) {
      // Input array: Nodes quantity by groups.
      // [Total, Pending Addition, Discover, Error, Offline]
      var groupSelector = 'div.nodes-group:nth-child(';
      var orderName, sortOrder, sortSelector;
      if (sortDirection === 'down') {
        sortOrder = [1, 2, 3, 4];
        orderName = 'asc';
      } else if (sortDirection === 'up') {
        sortOrder = [4, 3, 2, 1];
        orderName = 'desc';
      } else {
        throw new Error('Invalid sort direction value. Check sortDirection: "' + sortDirection +
          '" parameter and restart test.');
      }
      sortSelector = 'div.sort-by-status-' + orderName;
      return this.remote
        .assertElementsExist(sortSelector, 'Status sorting block is observed')
        .findByCssSelector(sortSelector)
          .assertElementContainsText('button.btn-default', 'Status', 'Sorting by status is default')
          .assertElementsExist('i.glyphicon-arrow-' + sortDirection,
            'Sorting in ' + orderName + ' order is observed')
          .end()
        .assertElementsExist(this.nodeSelector, nodesQuantity[0],
          'Default nodes quantity is observed')
        .assertElementContainsText(groupSelector + sortOrder[0] + ') h4', 'Pending Addition',
          '"Pending Addition" node group is correctly sorted')
        .assertElementsExist(groupSelector + sortOrder[0] + ') div.node.pending_addition',
          nodesQuantity[1], 'Default quantity of "Pending Addition" nodes is observed')
        .assertElementContainsText(groupSelector + sortOrder[1] + ') h4', 'Discovered',
          '"Discovered" node group is correctly sorted')
        .assertElementsExist(groupSelector + sortOrder[1] + ') div.node.discover',
          nodesQuantity[2], 'Default quantity of "Discovered" nodes is observed')
        .assertElementContainsText(groupSelector + sortOrder[2] + ') h4', 'Error',
          '"Error" node group is correctly sorted')
        .assertElementsExist(groupSelector + sortOrder[2] + ') div.node.error',
          nodesQuantity[3], 'Default quantity of "Error" nodes is observed')
        .assertElementContainsText(groupSelector + sortOrder[3] + ') h4', 'Offline',
          '"Offline" node group is correctly sorted')
        .assertElementsExist(groupSelector + sortOrder[3] + ') div.node.offline',
          nodesQuantity[4], 'Default quantity of "Offline" nodes is observed');
    }
  };
  return EquipmentLib;
});
