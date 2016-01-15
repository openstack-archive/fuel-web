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
  'tests/functional/helpers',
  'tests/functional/pages/common',
  'tests/functional/pages/modal'
], function(registerSuite, assert, helpers, Common, ModalWindow) {
  'use strict';

  registerSuite(function() {
    var common,
      clusterName;

    return {
      name: 'Clusters page',
      setup: function() {
        common = new Common(this.remote);
        clusterName = common.pickRandomName('Test Cluster');

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
            return common.removeCluster(clusterName);
          });
      },
      'Create Cluster': function() {
        return this.remote
          .then(function() {
            return common.doesClusterExist(clusterName);
          })
          .then(function(result) {
            assert.ok(result, 'Newly created cluster found in the list');
          });
      },
      'Attempt to create cluster with duplicate name': function() {
        return this.remote
          .clickLinkByText('Environments')
          .waitForCssSelector('.clusters-page', 2000)
          .then(function() {
            return common.createCluster(
              clusterName,
              {
                'Name and Release': function() {
                  var modal = new ModalWindow(this.remote);
                  return this.remote
                    .pressKeys('\uE007')
                    .assertElementTextEquals(
                      '.create-cluster-form span.help-block',
                      'Environment with name "' + clusterName + '" already exists',
                      'Error message should say that environment with that name already exists'
                    )
                    .then(function() {
                      return modal.close();
                    });
                }}
              );
          });
      },
      'Testing cluster list page': function() {
        return this.remote
          .clickLinkByText('Environments')
          .assertElementAppears('.clusters-page .clusterbox', 2000, 'Cluster container exists')
          .assertElementExists('.create-cluster', 'Cluster creation control exists');
      }
    };
  });
});
