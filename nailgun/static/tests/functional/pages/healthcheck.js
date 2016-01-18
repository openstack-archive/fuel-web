/*
 * Copyright 2016 Mirantis, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the 'License'); you may
 * not use this file except in compliance with the License. You may obtain
 * a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an 'AS IS' BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations
 * under the License.
 **/

define([
  'tests/functional/helpers'
], function() {
  'use strict';

  function HealthcheckPage(remote) {
    this.remote = remote;
  }

  HealthcheckPage.prototype = {
    constructor: HealthcheckPage,
    createFakeServerForNotRunnedTests: function() {
      return this.remote
        .execute(function() {
          window.server = sinon.fakeServer.create();
          window.server.autoRespond = true;

          window.server.respondWith('GET', /\/ostf\/testsets\/.*/, [
            200, {'Content-Type': 'application/json'}, JSON.stringify([
              // @FIXME(morale): multiple testsets don't seem to work as expected
              {
                id: 'general_test',
                name: 'General fake tests. Duration - 10s'
              }]
            )
          ]);
          window.server.respondWith('GET', /\/ostf\/tests\/.*/, [
            200, {'Content-Type': 'application/json'}, JSON.stringify([
              {
                status: null,
                step: null,
                taken: null,
                testset: 'general_test',
                name: 'Check disk space outage on controller and compute nodes',
                duration: '20s',
                message: null,
                id: 'fuel_health.tests.check_disk',
                description: 'Target component: Nova        Scenario: 1. Check outage on controller and compute nodes'
              },
              {
                status: null,
                step: null,
                taken: null,
                testset: 'general_test',
                name: 'Stopped test',
                duration: '20s',
                message: null,
                id: 'fuel_health.tests.stopped',
                description: 'Testing test stop'
              },
              {
                status: null,
                taken: null,
                step: null,
                testset: 'general_test',
                name: 'Check log rotation configuration on all nodes',
                duration: '30s.',
                message: null,
                id: 'fuel_health.tests.general',
                description: 'Target component: Logging        Scenario:            1. Check logrotate cron job on all controller and compute nodes'
              },
              {
                status: null,
                taken: null,
                step: null,
                testset: 'general_test',
                name: 'Check usage of default credentials on master node',
                duration: '1sec',
                message: null,
                id: 'fuel_health.tests.credentials',
                description: 'Target component: Configuration        Scenario: 1. Check user can not ssh on master node with default credentials.            '
              },
              {
                status: null,
                taken: null,
                step: null,
                testset: 'general_test',
                name: 'Check if default credentials for OpenStack cluster have changed',
                duration: '',
                message: null,
                id: 'fuel_health.tests.credentials_change',
                description: 'Target component: Configuration        Scenario:      1. Check if default credentials for OpenStack cluster have changed.   '
              },
              {
                status: null,
                taken: null,
                step: null,
                testset: 'general_test',
                name: 'Checking common credentials',
                duration: '',
                message: null,
                id: 'fuel_health.tests.credentials_common',
                description: 'Checking common'
              },
              {
                status: null,
                taken: null,
                step: null,
                testset: 'general_test',
                name: 'Checking error credentials',
                duration: '',
                message: null,
                id: 'fuel_health.tests.credentials_erros',
                description: 'Target component: Configuration        Scenario:      1. Check if default credentials for OpenStack cluster have changed.   '
              }]
            )
          ]);
          window.server.respondWith('GET', /\ostf\/testruns\/last.*/, [
            200, {'Content-Type': 'application/json'},
            '[]'
          ]);
        });
    },
    createFakeServerForRunningTests: function() {
      return this.remote
        // running tests
        .execute(function() {
          window.server = sinon.fakeServer.create();
          window.server.autoRespond = true;

          window.server.respondWith('GET', /\/ostf\/testsets\/.*/, [
            200, {'Content-Type': 'application/json'}, JSON.stringify([
              {
                id: 'general_test',
                name: 'General fake tests. Duration - 10s'
              }]
            )
          ]);
            // All possible statuses covered at once
          window.server.respondWith('GET', /\/ostf\/tests\/.*/, [
            200, {'Content-Type': 'application/json'}, JSON.stringify([
              {
                status: 'running',
                taken: null,
                step: null,
                testset: 'general_test',
                name: 'Check disk space outage on controller and compute nodes',
                duration: '20s',
                message: null,
                id: 'fuel_health.tests.check_disk',
                description: 'Target component: Nova        Scenario: 1. Check outage on controller and compute nodes'
              },
              {
                status: 'stopped',
                step: null,
                taken: 2.123123123,
                testset: 'general_test',
                name: 'Stopped test',
                duration: '20s',
                message: 'Successfully stopped',
                id: 'fuel_health.tests.stopped',
                description: 'Testing test stop'
              },
              {
                status: 'skipped',
                taken: null,
                step: null,
                testset: 'general_test',
                name: 'Check log rotation configuration on all nodes',
                duration: '30s.',
                message: 'Fast fail with message',
                id: 'fuel_health.tests.general',
                description: 'Target component: Logging        Scenario:            1. Check logrotate cron job on all controller and compute nodes'
              },
              {
                status: 'wait_running',
                taken: null,
                step: null,
                testset: 'general_test',
                name: 'Check usage of default credentials on master node',
                duration: '1sec',
                message: 'failure text message',
                id: 'fuel_health.tests.credentials',
                description: 'Target component: Configuration        Scenario: 1. Check user can not ssh on master node with default credentials.            '
              },
              {
                status: 'running',
                taken: '3s',
                step: null,
                testset: 'general_test',
                name: 'Check if default credentials for OpenStack cluster have changed',
                duration: '',
                message: 'Error message',
                id: 'fuel_health.tests.credentials_change',
                description: '  Target component: Configuration        Scenario:      1. Check if default credentials for OpenStack cluster have changed.   '
              },
              {
                status: 'wait_running',
                taken: null,
                step: null,
                testset: 'general_test',
                name: 'Checking common credentials',
                duration: '',
                message: null,
                id: 'fuel_health.tests.credentials_common',
                description: 'Checking common'
              },
              {
                status: 'running',
                taken: '3s',
                step: null,
                testset: 'general_test',
                name: 'Checking error credentials',
                duration: '',
                message: null,
                id: 'fuel_health.tests.credentials_erros',
                description: 'Target component: Configuration        Scenario:      1. Check if error credentials for OpenStack cluster not suit.'
              }]
            )
          ]);
          window.server.respondWith('GET', /\ostf\/testruns\/last.*/, [
            200, {'Content-Type': 'application/json'}, JSON.stringify([
              {
                status: 'running',
                cluster_id: 3,
                ended_at: '2015-09-24 12:15:33.262275',
                id: 1,
                meta: null,
                started_at: '2015-09-24 12:15:21.590927',
                testset: 'general_test',
                tests: [
                  {
                    status: 'running',
                    taken: null,
                    step: null,
                    testset: 'general_test',
                    name: 'Check disk space outage on controller and compute nodes',
                    duration: '20s',
                    message: null,
                    id: 'fuel_health.tests.check_disk',
                    description: 'Target component: Nova        Scenario: 1. Check outage on controller and compute nodes'
                  },
                  {
                    status: 'stopped',
                    step: null,
                    taken: 2.123123123,
                    testset: 'general_test',
                    name: 'Stopped test',
                    duration: '20s',
                    message: 'Successfully stopped',
                    id: 'fuel_health.tests.stopped',
                    description: 'Testing test stop'
                  },
                  {
                    status: 'skipped',
                    taken: null,
                    step: null,
                    testset: 'general_test',
                    name: 'Check log rotation configuration on all nodes',
                    duration: '30s.',
                    message: 'Fast fail with message',
                    id: 'fuel_health.tests.general',
                    description: 'Target component: Logging        Scenario:            1. Check logrotate cron job on all controller and compute nodes'
                  },
                  {
                    status: 'wait_running',
                    taken: null,
                    step: null,
                    testset: 'general_test',
                    name: 'Check usage of default credentials on master node',
                    duration: '1sec',
                    message: 'failure text message',
                    id: 'fuel_health.tests.credentials',
                    description: 'Target component: Configuration        Scenario: 1. Check user can not ssh on master node with default credentials.            '
                  },
                  {
                    status: 'running',
                    taken: '3s',
                    step: null,
                    testset: 'general_test',
                    name: 'Check if default credentials for OpenStack cluster have changed',
                    duration: '',
                    message: 'Error message',
                    id: 'fuel_health.tests.credentials_change',
                    description: '  Target component: Configuration        Scenario:      1. Check if default credentials for OpenStack cluster have changed.   '
                  },
                  {
                    status: 'wait_running',
                    taken: null,
                    step: null,
                    testset: 'general_test',
                    name: 'Checking common credentials',
                    duration: '',
                    message: null,
                    id: 'fuel_health.tests.credentials_common',
                    description: 'Checking common'
                  },
                  {
                    status: 'running',
                    taken: '3s',
                    step: null,
                    testset: 'general_test',
                    name: 'Checking error credentials',
                    duration: '',
                    message: null,
                    id: 'fuel_health.tests.credentials_erros',
                    description: 'Target component: Configuration        Scenario:      1. Check if error credentials for OpenStack cluster not suit.'
                  }
                ]
              }]
            )
          ]);
        });
    },
    createFakeServerForFinishedTests: function() {
      return this.remote
        // running tests
        .execute(function() {
          window.server = sinon.fakeServer.create();
          window.server.autoRespond = true;

          window.server.respondWith('GET', /\/ostf\/testsets\/.*/, [
            200, {'Content-Type': 'application/json'}, JSON.stringify([
              {
                id: 'general_test',
                name: 'General fake tests. Duration - 10s'
              }]
            )
          ]);
          // All possible statuses covered at once
          window.server.respondWith('GET', /\/ostf\/tests\/.*/, [
            200, {'Content-Type': 'application/json'}, JSON.stringify([
              {
                status: 'success',
                taken: 1.71715784072876,
                step: null,
                testset: 'general_test',
                name: 'Check disk space outage on controller and compute nodes',
                duration: '20s',
                message: null,
                id: 'fuel_health.tests.check_disk',
                description: 'Target component: Nova        Scenario: 1. Check outage on controller and compute nodes'
              },
              {
                status: 'stopped',
                step: null,
                taken: 2.123123123,
                testset: 'general_test',
                name: 'Stopped test',
                duration: '20s',
                message: 'Successfully stopped',
                id: 'fuel_health.tests.stopped',
                description: 'Testing test stop'
              },
              {
                status: 'failure',
                taken: 2.7339019775390598,
                step: null,
                testset: 'general_test',
                name: 'Check log rotation configuration on all nodes',
                duration: '30s.',
                message: 'Fast fail with message',
                id: 'fuel_health.tests.general',
                description: 'Target component: Logging        Scenario:            1. Check logrotate cron job on all controller and compute nodes'
              },
              {
                status: 'skipped',
                taken: null,
                step: null,
                testset: 'general_test',
                name: 'Check usage of default credentials on master node',
                duration: '1sec',
                message: 'failure text message',
                id: 'fuel_health.tests.credentials',
                description: 'Target component: Configuration        Scenario: 1. Check user can not ssh on master node with default credentials.            '
              },
              {
                status: 'success',
                taken: '3s',
                step: null,
                testset: 'general_test',
                name: 'Check if default credentials for OpenStack cluster have changed',
                duration: '',
                message: 'Error message',
                id: 'fuel_health.tests.credentials_change',
                description: '  Target component: Configuration        Scenario:      1. Check if default credentials for OpenStack cluster have changed.   '
              },
              {
                status: 'failure',
                taken: 3.89809381,
                step: null,
                testset: 'general_test',
                name: 'Checking common credentials',
                duration: '',
                message: 'Failure message',
                id: 'fuel_health.tests.credentials_common',
                description: 'Checking common'
              },
              {
                status: 'error',
                taken: '3s',
                step: null,
                testset: 'general_test',
                name: 'Checking error credentials',
                duration: '',
                message: null,
                id: 'fuel_health.tests.credentials_erros',
                description: 'Target component: Configuration        Scenario:      1. Check if error credentials for OpenStack cluster not suit.'
              }
            ])
          ]);
          window.server.respondWith('GET', /\ostf\/testruns\/last.*/, [
            200, {'Content-Type': 'application/json'}, JSON.stringify([
              {
                status: 'finished',
                cluster_id: 4,
                ended_at: '2015-09-24 12:15:33.262275',
                id: 1,
                meta: null,
                started_at: '2015-09-24 12:15:21.590927',
                testset: 'general_test',
                tests: [
                  {
                    status: 'success',
                    taken: 1.71715784072876,
                    step: null,
                    testset: 'general_test',
                    name: 'Check disk space outage on controller and compute nodes',
                    duration: '20s',
                    message: null,
                    id: 'fuel_health.tests.check_disk',
                    description: 'Target component: Nova        Scenario: 1. Check outage on controller and compute nodes'
                  },
                  {
                    status: 'stopped',
                    step: null,
                    taken: 2.123123123,
                    testset: 'general_test',
                    name: 'Stopped test',
                    duration: '20s',
                    message: 'Successfully stopped',
                    id: 'fuel_health.tests.stopped',
                    description: 'Testing test stop'
                  },
                  {
                    status: 'failure',
                    taken: 2.7339019775390598,
                    step: null,
                    testset: 'general_test',
                    name: 'Check log rotation configuration on all nodes',
                    duration: '30s.',
                    message: 'Fast fail with message',
                    id: 'fuel_health.tests.general',
                    description: 'Target component: Logging        Scenario:            1. Check logrotate cron job on all controller and compute nodes'
                  },
                  {
                    status: 'skipped',
                    taken: null,
                    step: null,
                    testset: 'general_test',
                    name: 'Check usage of default credentials on master node',
                    duration: '1sec',
                    message: 'failure text message',
                    id: 'fuel_health.tests.credentials',
                    description: 'Target component: Configuration        Scenario: 1. Check user can not ssh on master node with default credentials.            '
                  },
                  {
                    status: 'success',
                    taken: '3s',
                    step: null,
                    testset: 'general_test',
                    name: 'Check if default credentials for OpenStack cluster have changed',
                    duration: '',
                    message: 'Error message',
                    id: 'fuel_health.tests.credentials_change',
                    description: '  Target component: Configuration        Scenario:      1. Check if default credentials for OpenStack cluster have changed.   '
                  },
                  {
                    status: 'failure',
                    taken: 3.89809381,
                    step: null,
                    testset: 'general_test',
                    name: 'Checking common credentials',
                    duration: '',
                    message: 'Failure message',
                    id: 'fuel_health.tests.credentials_common',
                    description: 'Checking common'
                  },
                  {
                    status: 'error',
                    taken: '3s',
                    step: null,
                    testset: 'general_test',
                    name: 'Checking error credentials',
                    duration: '',
                    message: null,
                    id: 'fuel_health.tests.credentials_erros',
                    description: 'Target component: Configuration        Scenario:      1. Check if error credentials for OpenStack cluster not suit.'
                  }
                ]
              }]
            )
          ]);
        });
    },
    restoreServer: function() {
      return this.remote
        .execute(function() {
          window.server.restore();
        });
    }
  };
  return HealthcheckPage;
});
