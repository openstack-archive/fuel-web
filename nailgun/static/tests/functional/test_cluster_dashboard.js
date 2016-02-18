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
  'intern!object',
  'intern/chai!assert',
  'tests/functional/pages/common',
  'tests/functional/pages/cluster',
  'tests/functional/pages/clusters',
  'tests/functional/pages/dashboard'
], function(registerSuite, assert, Common, ClusterPage, ClustersPage, DashboardPage) {
  'use strict';

  registerSuite(function() {
    var common,
      clusterPage,
      clustersPage,
      dashboardPage,
      clusterName;

    return {
      name: 'Dashboard tab',
      setup: function() {
        common = new Common(this.remote);
        clusterPage = new ClusterPage(this.remote);
        clustersPage = new ClustersPage(this.remote);
        dashboardPage = new DashboardPage(this.remote);
        clusterName = common.pickRandomName('Test Cluster');

        return this.remote
          .then(function() {
            return common.getIn();
          })
          .then(function() {
            return common.createCluster(clusterName);
          });
      },
      beforeEach: function() {
        return this.remote
          .then(function() {
            return clusterPage.goToTab('Dashboard');
          });
      },
      'Renaming cluster works': function() {
        var initialName = clusterName;
        var newName = clusterName + '!!!';
        var renameInputSelector = '.rename-block input[type=text]';
        var nameSelector = '.cluster-info-value.name .btn-link';
        return this.remote
          .then(function() {
            return dashboardPage.startClusterRenaming();
          })
          .findByCssSelector(renameInputSelector)
            // Escape
            .type('\uE00C')
            .end()
          .assertElementNotExists(renameInputSelector, 'Rename control disappears')
          .assertElementTextEquals(
            nameSelector,
            initialName,
            'Switching rename control does not change cluster name'
          )
          .then(function() {
            return dashboardPage.setClusterName(newName);
          })
          .assertElementTextEquals(nameSelector, newName, 'New name is applied')
          .then(function() {
            return dashboardPage.setClusterName(initialName);
          })
          .then(function() {
            return common.createCluster(newName);
          })
          .then(function() {
            return clusterPage.goToTab('Dashboard');
          })
          .then(function() {
            return dashboardPage.setClusterName(initialName);
          })
          .assertElementAppears(
            '.rename-block.has-error',
            1000,
            'Error style for duplicate name is applied'
          )
          .assertElementTextEquals(
            '.rename-block .text-danger',
            'Environment with this name already exists',
            'Duplicate name error text appears'
          )
          .findByCssSelector(renameInputSelector)
            // Escape
            .type('\uE00C')
            .end()
          .clickLinkByText('Environments')
          .waitForCssSelector(clustersPage.clusterSelector, 2000)
          .then(function() {
            return clustersPage.goToEnvironment(initialName);
          });
      },
      'Provision VMs button availability': function() {
        return this.remote
          .then(function() {
            return common.addNodesToCluster(1, ['Virtual']);
          })
          .then(function() {
            return clusterPage.goToTab('Dashboard');
          })
          .waitForCssSelector('.dashboard-tab', 200)
          .clickByCssSelector('.actions-panel li.spawn_vms')
          .assertElementAppears(
            '.actions-panel .btn-provision-vms',
            1000,
            'Provision VMs action appears on the Dashboard'
          )
          .clickByCssSelector('.actions-panel li.deploy')
          .then(function() {
            return dashboardPage.discardChanges();
          });
      },
      'Network validation error warning': function() {
        return this.remote
          .then(function() {
            return common.addNodesToCluster(1, ['Controller']);
          })
          .then(function() {
            return clusterPage.goToTab('Networks');
          })
          .clickByCssSelector('.subtab-link-network_verification')
          .assertElementContainsText(
            '.alert-warning',
            'At least two online nodes are required',
            'Network verification warning appears if only one node added'
          )
          .then(function() {
            return clusterPage.goToTab('Dashboard');
          })
          .waitForCssSelector('.dashboard-tab', 200)
          .assertElementContainsText(
            '.actions-panel .warnings-block',
            'Please verify your network settings before deployment',
            'Network verification warning is shown'
          )
          .then(function() {
            return dashboardPage.discardChanges();
          });
      },
      'No controller warning': function() {
        return this.remote
          .then(function() {
            return common.addNodesToCluster(1, ['Compute']);
          })
          .then(function() {
            return clusterPage.goToTab('Dashboard');
          })
          .assertElementDisabled(
            dashboardPage.deployButtonSelector,
            'No deployment should be possible without controller nodes added'
          )
          .assertElementExists('div.instruction.invalid', 'Invalid configuration message is shown')
          .assertElementContainsText(
            '.task-alerts ul.text-danger li',
            'At least 1 Controller nodes are required (0 selected currently).',
            'No controllers added warning should be shown'
          )
          .then(function() {
            return dashboardPage.discardChanges();
          });
      },
      'Capacity table tests': function() {
        return this.remote
          .then(function() {
            return common.addNodesToCluster(1, ['Controller', 'Cinder']);
          })
          .then(function() {
            return common.addNodesToCluster(2, ['Compute']);
          })
          .then(function() {
            return clusterPage.goToTab('Dashboard');
          })
          .assertIsIntegerContentPositive('.capacity-items .cpu .capacity-value', 'CPU')
          .assertIsIntegerContentPositive('.capacity-items .hdd .capacity-value', 'HDD')
          .assertIsIntegerContentPositive('.capacity-items .ram .capacity-value', 'RAM')
          .then(function() {
            return dashboardPage.discardChanges();
          });
      },
      'Test statistics update': function() {
        this.timeout = 120000;
        var controllerNodes = 3;
        var storageCinderNodes = 1;
        var computeNodes = 2;
        var operatingSystemNodes = 1;
        var virtualNodes = 1;
        var valueSelector = '.statistics-block .cluster-info-value';
        var total = controllerNodes + storageCinderNodes + computeNodes + operatingSystemNodes +
          virtualNodes;
        return this.remote
          .then(function() {
            return common.addNodesToCluster(controllerNodes, ['Controller']);
          })
          .then(function() {
            return common.addNodesToCluster(storageCinderNodes, ['Cinder']);
          })
          .then(function() {
            return common.addNodesToCluster(computeNodes, ['Compute']);
          })
          .then(function() {
            return common.addNodesToCluster(operatingSystemNodes, ['Operating System'], 'error');
          })
          .then(function() {
            return common.addNodesToCluster(virtualNodes, ['Virtual'], 'offline');
          })
          .then(function() {
            return clusterPage.goToTab('Dashboard');
          })
          .assertElementTextEquals(
            valueSelector + '.total',
            total,
            'The number of Total nodes in statistics is correct'
          )
          .assertElementTextEquals(
            valueSelector + '.controller',
            controllerNodes,
            'The number of controllerNodes nodes in statistics is correct'
          )
          .assertElementTextEquals(
            valueSelector + '.compute',
            computeNodes,
            'The number of Compute nodes in statistics is correct'
          )
          .assertElementTextEquals(
            valueSelector + '.base-os',
            operatingSystemNodes,
            'The number of Operating Systems nodes in statistics is correct'
          )
          .assertElementTextEquals(
            valueSelector + '.virt',
            virtualNodes,
            'The number of Virtual nodes in statistics is corrects'
          )
          .assertElementTextEquals(
            valueSelector + '.offline',
            1,
            'The number of Offline nodes in statistics is correct'
          )
          .assertElementTextEquals(
            valueSelector + '.error',
            1,
            'The number of Error nodes in statistics is correct'
          )
          .assertElementTextEquals(
            valueSelector + '.pending_addition',
            total,
            'The number of Pending Addition nodes in statistics is correct'
          )
          .then(function() {
            return dashboardPage.discardChanges();
          });
      }
    };
  });
});
