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
    'tests/functional/pages/common'
], function(registerSuite, assert, Common) {
    'use strict';

    registerSuite(function() {
        var common,
            clusterName;

        return {
            name: 'Clusters page',
            setup: function() {
                common = new Common(this.remote);
            },
            beforeEach: function() {
                clusterName = common.pickRandomName('Test Cluster');
                return this.remote
                    .then(function() {
                        return common.getIn();
                    })
                    .then(function() {
                        return common.createCluster(clusterName);
                    });
            },
            afterEach: function() {
                return this.remote
                    .then(function() {
                        return common.removeCluster(clusterName, true);
                    });
            },
            'Create Cluster': function() {
                return this.remote
                    .then(function() {
                        return common.doesClusterExist(clusterName);
                    })
                    .then(function(result) {
                        assert.ok(result, 'Newly created cluster name found in the list');
                    });
            },
            'Attempt to create cluster with duplicate name': function() {
                return this.remote
                    .then(function() {
                        return common.createCluster(clusterName, true);
                    })
                    .setFindTimeout(1000)
                    .findAllByCssSelector('.create-cluster-form .form-group.has-error')
                    .then(function(result) {
                        assert.strictEqual(result.length, 1, 'Cluster creation error exists');
                    });
            },
            'Testing cluster list page': function() {
                return this.remote
                    .findByCssSelector('.breadcrumb a')
                        .click()
                        .end()
                    .setFindTimeout(2000)
                    //Cluster container exists
                    .findAllByCssSelector('.clusters-page .clusterbox')
                        .then(function(elements) {
                            return assert.ok(elements.length, 'Cluster container exists');
                        })
                        .end()
                    .findAllByCssSelector('.create-cluster')
                        .then(function(elements) {
                            return assert.strictEqual(elements.length, 1, 'Cluster creation control exists');
                        })
                        .end()
            }
        };
    });
});
