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
  'tests/functional/pages/cluster',
  'tests/functional/pages/dashboard',
  'tests/functional/pages/modal'
], function(_, registerSuite, assert, helpers, Common, ClusterPage, DashboardPage, ModalWindow) {
  'use strict';

  registerSuite(function() {
    var common,
      clusterPage,
      dashboardPage,
      modal,
      clusterName;

    return {
      name: 'Cluster deployment',
      setup: function() {
        common = new Common(this.remote);
        clusterPage = new ClusterPage(this.remote);
        dashboardPage = new DashboardPage(this.remote);
        modal = new ModalWindow(this.remote);
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
      'No deployment button when there are no nodes added': function() {
        return this.remote
          .assertElementNotExists(dashboardPage.deployButtonSelector,
            'No deployment should be possible without nodes added');
      },
      'Provision nodes': function() {
        return this.remote
          .then(function() {
            return common.addNodesToCluster(3, ['Controller']);
          })
          .then(function() {
            return clusterPage.goToTab('Dashboard');
          })
          .assertElementAppears('.dashboard-tab', 200, 'Dashboard tab opened')
          .clickByCssSelector('.deploy-btn-group .dropdown-toggle')
          .clickByCssSelector('.btn-provision')
          .then(function() {
            return modal.waitToOpen();
          })
          .then(function() {
            return modal.checkTitle('Provision Nodes');
          })
          .then(function() {
            return modal.clickFooterButton('Start Provisioning');
          })
          .then(function() {
            return modal.waitToClose();
          })
          .assertElementAppears('div.deploy-process div.progress', 2000, 'Provisioning started')
          .assertElementDisappears('div.deploy-process div.progress', 5000, 'Provisioning finished')
          .assertElementContainsText(
            'div.alert-success strong',
            'Success',
            'Provisioning successfully finished'
          )
          // deletion of provisioned node from environment
          // the following check should be restored after #1515893 fix
          //.then(function() {
          //  return clusterPage.goToTab('Nodes');
          //})
          //.waitForCssSelector('.node', 3000)
          //.clickByCssSelector('.node > label')
          //.clickByCssSelector('.control-buttons-box .btn.btn-delete-nodes')
          //.then(function() {
          //  return modal.waitToOpen();
          //})
          //.then(function() {
          //  return modal.clickFooterButton('Delete');
          //})
          //.then(function() {
          //  return modal.waitToClose();
          //})
          //.assertElementsExist('.node', 2, 'Provisioned node was succesfully deleted')
          .then(function() {
            return clusterPage.isTabLocked('Networks');
          })
          .then(function(isLocked) {
            assert.isFalse(isLocked, 'Networks tab is not locked after nodes were provisioned');
          })
          .then(function() {
            return clusterPage.isTabLocked('Settings');
          })
          .then(function(isLocked) {
            assert.isFalse(isLocked, 'Settings tab is not locked after nodes were provisioned');
          })
          .then(function() {
            return clusterPage.goToTab('Dashboard');
          })
          .assertElementExists('.deploy-btn', 'Provisioned nodes can be deployed');
          // should be also restored after #1515893 fix
          //.assertElementNotExists(
          //  '.deploy-btn-group .dropdown-toggle',
          //  'Only deployment available for provisioned nodes'
          //);
      },
      'Discard changes': function() {
        return this.remote
          .then(function() {
            // Adding three controllers
            return common.addNodesToCluster(1, ['Controller']);
          })
          .then(function() {
            return clusterPage.goToTab('Dashboard');
          })
          .clickByCssSelector('.btn-discard-changes')
          .then(function() {
            return modal.waitToOpen();
          })
          .assertElementContainsText('h4.modal-title', 'Discard Changes',
            'Discard Changes confirmation modal expected')
          .then(function() {
            return modal.clickFooterButton('Discard');
          })
          .then(function() {
            return modal.waitToClose();
          })
          .assertElementAppears('.dashboard-block a.btn-add-nodes', 2000,
            'All changes discarded, add nodes button gets visible in deploy readiness block');
      },
      'Start/stop deployment': function() {
        this.timeout = 100000;
        return this.remote
          .then(function() {
            return common.addNodesToCluster(3, ['Controller']);
          })
          .then(function() {
            return clusterPage.goToTab('Dashboard');
          })
          .assertElementAppears('.dashboard-tab', 200, 'Dashboard tab opened')
          .then(function() {
            return dashboardPage.startDeployment();
          })
          .assertElementAppears('div.deploy-process div.progress', 2000, 'Deployment started')
          .assertElementAppears('button.stop-deployment-btn:not(:disabled)', 5000,
            'Stop button appears')
          .then(function() {
            return dashboardPage.stopDeployment();
          })
          .assertElementDisappears('div.deploy-process div.progress', 20000, 'Deployment stopped')
          .assertElementAppears(dashboardPage.deployButtonSelector, 1000,
            'Deployment button available')
          .assertElementContainsText('div.alert-warning strong', 'Success',
            'Deployment successfully stopped alert is expected')
          .assertElementNotExists('.go-to-healthcheck',
            'Healthcheck link is not visible after stopped deploy')
          // Reset environment button is available
          .then(function() {
            return clusterPage.resetEnvironment(clusterName);
          });
      },
      'Test tabs locking after deployment completed': function() {
        this.timeout = 100000;
        return this.remote
          .then(function() {
            // Adding single controller (enough for deployment)
            return common.addNodesToCluster(1, ['Controller']);
          })
          .then(function() {
            return clusterPage.isTabLocked('Networks');
          })
          .then(function(isLocked) {
            assert.isFalse(isLocked, 'Networks tab is not locked for undeployed cluster');
          })
          .then(function() {
            return clusterPage.isTabLocked('Settings');
          })
          .then(function(isLocked) {
            assert.isFalse(isLocked, 'Settings tab is not locked for undeployed cluster');
          })
          .then(function() {
            return clusterPage.goToTab('Dashboard');
          })
          .then(function() {
            return dashboardPage.startDeployment();
          })
          .assertElementDisappears('.dashboard-block .progress', 60000,
            'Progress bar disappears after deployment')
          .assertElementAppears('.links-block', 5000, 'Deployment completed')
          .assertElementExists('.go-to-healthcheck', 'Healthcheck link is visible after deploy')
          .findByLinkText('Horizon')
            .getAttribute('href')
            .then(function(value) {
              return assert.isTrue(_.startsWith(value, 'http'), 'Link to Horizon is formed');
            })
            .end()
          .then(function() {
            return clusterPage.isTabLocked('Networks');
          })
          .then(function(isLocked) {
            assert.isTrue(isLocked, 'Networks tab should turn locked after deployment');
          })
          .assertElementEnabled('.add-nodegroup-btn',
            'Add Node network group button is enabled after cluster deploy')
          .then(function() {
            return clusterPage.isTabLocked('Settings');
          })
          .then(function(isLocked) {
            assert.isTrue(isLocked, 'Settings tab should turn locked after deployment');
          })
          .then(function() {
            return clusterPage.goToTab('Dashboard');
          })
          .then(function() {
            return clusterPage.resetEnvironment(clusterName);
          });
      }
    };
  });
});
