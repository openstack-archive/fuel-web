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
  'tests/functional/pages/healthcheck'
], function(registerSuite, Common, ClusterPage, HealthcheckPage) {
  'use strict';

  registerSuite(function() {
    var common,
      clusterPage,
      clusterName,
      healthCheckPage;

    return {
      name: 'Healthcheck page',
      setup: function() {
        common = new Common(this.remote);
        clusterPage = new ClusterPage(this.remote);
        clusterName = common.pickRandomName('Healthcheck test');
        healthCheckPage = new HealthcheckPage(this.remote);
        return this.remote
          .then(function() {
            return common.getIn();
          });
      },
      beforeEach: function() {
        return this.remote
          .then(function() {
            return common.createCluster(clusterName);
          });
      },
      afterEach: function() {
        return this.remote
          .then(function() {
            return healthCheckPage.restoreServer();
          })
          .then(function() {
            return common.removeCluster(clusterName);
          });
      },
      'Health Check tests are rendered if response received': function() {
        return this.remote
          .then(function() {
            return healthCheckPage.createFakeServerForNotRunnedTests();
          })
          .then(function() {
            return clusterPage.goToTab('Health Check');
          })
          .assertElementsAppear('.healthcheck-table', 5000, 'Healthcheck tables are rendered')
          .assertElementDisabled('.custom-tumbler input[type=checkbox]',
            'Test checkbox is disabled')
          .assertElementContainsText('.alert-warning',
            'Before you can test an OpenStack environment, ' +
            'you must deploy the OpenStack environment',
          'Warning to deploy cluster is shown')
          .assertElementNotExists('.run-tests-btn',
            'Run tests button is not shown in new OpenStack environment')
          .assertElementNotExists('.stop-tests-btn',
          'Stop tests button is not shown in new OpenStack environment');
      },
      //@TODO (morale): imitate tests stop
      'Check Healthcheck tab manipulations after deploy': function() {
        this.timeout = 100000;
        return this.remote
          .then(function() {
            return common.addNodesToCluster(1, ['Controller']);
          })
          .then(function() {
            return clusterPage.deployEnvironment();
          })
          .then(function() {
            return healthCheckPage.createFakeServerForNotRunnedTests();
          })
          .then(function() {
            return clusterPage.goToTab('Health Check');
          })
          .assertElementEnabled('.custom-tumbler input[type=checkbox]',
            'Test checkbox is enabled after deploy')
          // 'run tests' button interactions
          .assertElementDisabled('.run-tests-btn',
            'Run tests button is disabled if no tests checked')
          .assertElementNotExists('.stop-tests-btn',
            'Stop tests button is not visible if no tests checked')
          .assertElementExists('.toggle-credentials', 'Toggle credentials button is visible')
          // provide credentials tests
          .clickByCssSelector('.toggle-credentials')
          .assertElementsAppear('.credentials input[type=text]', 500, 'Text inputs appear')
          .clickByCssSelector('.toggle-credentials')
          .waitForElementDeletion('.credentials', 2000)
          .clickByCssSelector('#testset-checkbox-general_test')
          .waitForCssSelector('.run-tests-btn', 1000)
          .assertElementEnabled('.run-tests-btn',
            '"Run Tests" button is enabled if there are checked tests');
      },
      'Check running tests': function() {
        this.timeout = 100000;
        return this.remote
          .then(function() {
            return common.addNodesToCluster(1, ['Controller']);
          })
          .then(function() {
            return clusterPage.deployEnvironment();
          })
          .then(function() {
            return healthCheckPage.createFakeServerForRunningTests();
          })
          .then(function() {
            return clusterPage.goToTab('Health Check');
          })
          .assertElementNotExists('.run-tests-btn',
            'Run tests button is not shown if tests are running')
          .assertElementEnabled('.stop-tests-btn', 'Stop tests button is enabled during tests run')
          .assertElementsAppear('.glyphicon-refresh.animate-spin', 1000,
            'Running status is reflected')
          .assertElementsAppear('.glyphicon-time', 1000, 'Waiting to run status is reflected')
          .assertElementsAppear('.healthcheck-status-skipped', 1000, 'Skipped status is reflected')
          .assertElementsAppear('.healthcheck-status-stopped', 1000, 'Stopped status is reflected');
      },
      'Check finished tests': function() {
        this.timeout = 100000;
        return this.remote
          .then(function() {
            return common.addNodesToCluster(1, ['Controller']);
          })
          .then(function() {
            return clusterPage.deployEnvironment();
          })
          .then(function() {
            return healthCheckPage.createFakeServerForFinishedTests();
          })
          .then(function() {
            return clusterPage.goToTab('Health Check');
          })
          .assertElementNotExists('.stop-tests-btn',
            'Stop tests button is not shown if tests are finished')
          .assertElementsAppear('.glyphicon-ok', 1000, 'Success status is reflected')
          .assertElementsAppear('.glyphicon-remove', 1000,
            'Error and Failure statuses are reflected');
      }
    };
  });
});
