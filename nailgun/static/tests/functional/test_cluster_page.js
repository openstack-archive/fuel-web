/*
 * Copyright 2015 Mirantis, Inc.
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
  'intern/dojo/node!lodash',
  'intern!object',
  'intern/chai!assert',
  'tests/functional/helpers',
  'tests/functional/pages/common',
  'tests/functional/pages/cluster'
], function(_, registerSuite, assert, helpers, Common, ClusterPage) {
  'use strict';

  registerSuite(function() {
    var common, clusterPage, clusterName;
    var nodesAmount = 3;
    var applyButtonSelector = 'button.btn-apply';

    return {
      name: 'Cluster page',
      setup: function() {
        common = new Common(this.remote);
        clusterPage = new ClusterPage(this.remote);
        clusterName = common.pickRandomName('Test Cluster');

        return this.remote
          .then(function() {
            return common.getIn();
          })
          .then(function() {
            return common.createCluster(clusterName);
          })
          .then(function() {
            return clusterPage.goToTab('Nodes');
          });
      },
      'Add Cluster Nodes': function() {
        var self = this;
        return this.remote
          .assertElementExists(
            '.node-list .alert-warning',
            'Node list shows warning if there are no nodes in environment'
          )
          .clickByCssSelector('.btn-add-nodes')
          .assertElementsAppear('.node', 2000, 'Unallocated nodes loaded')
          .assertElementDisabled(applyButtonSelector,
            'Apply button is disabled until both roles and nodes chosen')
          .assertElementsExist('.role-panel .row', 4, 'Roles are splitted in groups')
          .assertElementExists('.role-block.mongo.disabled', 'Unavailable role is locked')
          .assertElementExists(
            '.role-block.mongo i.glyphicon-warning-sign',
            'Unavailable role has warning icon'
          )
          .findByCssSelector('.role-block.mongo')
            .then(function(element) {
              return self.remote.moveMouseTo(element);
            })
            .end()
          // the following timeout as we have 0.5s transition time for role popover
          .sleep(600)
          .assertElementExists(
            '.role-block.mongo .popover .text-warning',
            'Role popover is opened and the role warning is shown in the popover'
          )
          .then(function() {
            return clusterPage.checkNodeRoles(['Controller', 'Cinder']);
          })
          .assertElementExists(
            '.role-block.controller i.glyphicon-selected-role',
            'Selected role has checkbox icon'
          )
          .assertElementExists(
            '.role-block.compute.disabled',
            'Compute role can not be added together with selected roles'
          )
          .assertElementDisabled(
            applyButtonSelector,
            'Apply button is disabled until both roles and nodes chosen'
          )
          .then(function() {
            return clusterPage.checkNodes(nodesAmount);
          })
          .clickByCssSelector(applyButtonSelector)
          .waitForElementDeletion(applyButtonSelector, 2000)
          .assertElementAppears('.nodes-group', 2000, 'Cluster node list loaded')
          .assertElementsExist(
            '.node-list .node',
            nodesAmount,
            nodesAmount + ' nodes were successfully added to the cluster'
          )
          .assertElementExists('.nodes-group', 'One node group is present');
      },
      'Edit cluster node roles': function() {
        return this.remote
          .then(function() {
            return common.addNodesToCluster(1, ['Cinder']);
          })
          .assertElementsExist('.nodes-group', 2, 'Two node groups are present')
          // select all nodes
          .clickByCssSelector('.select-all label')
          .clickByCssSelector('.btn-edit-roles')
          .assertElementDisappears('.btn-edit-roles', 2000, 'Cluster nodes screen unmounted')
          .assertElementNotExists(
            '.node-box [type=checkbox]:not(:disabled)',
            'Node selection is locked on Edit Roles screen'
          )
          .assertElementNotExists(
            '[name=select-all]:not(:disabled)',
            'Select All checkboxes are locked on Edit Roles screen'
          )
          .assertElementExists(
            '.role-block.controller i.glyphicon-indeterminated-role',
            'Controller role has indeterminate state'
          )
          // uncheck Cinder role
          .then(function() {
            return clusterPage.checkNodeRoles(['Cinder', 'Cinder']);
          })
          .clickByCssSelector(applyButtonSelector)
          .assertElementDisappears('.btn-apply', 3000, 'Role editing screen unmounted')
          .assertElementsExist(
            '.node-list .node',
            nodesAmount,
            'One node was removed from cluster after editing roles'
          );
      },
      'Remove Cluster': function() {
        return this.remote
          .then(function() {
            return common.doesClusterExist(clusterName);
          })
          .then(function(result) {
            assert.ok(result, 'Cluster exists');
          })
          .then(function() {
            return common.removeCluster(clusterName);
          })
          .then(function() {
            return common.doesClusterExist(clusterName);
          })
          .then(function(result) {
            assert.notOk(result, 'Cluster removed successfully');
          });
      }
    };
  });
});
