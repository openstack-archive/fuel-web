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
    'tests/helpers',
    'tests/functional/pages/common'
], function(registerSuite, assert, helpers, Common) {
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
                    .setFindTimeout(1000)
                    .clickLinkByText('Environments')
                    .then(function() {
                        return common.createCluster(
                            clusterName,
                            {
                                'Name and Release': function() {
                                    var ModalWindow = require('tests/functional/pages/modal'),
                                        modal = new ModalWindow(this.remote);
                                    return this.remote
                                        .pressKeys('\uE007')
                                        .setFindTimeout(2000)
                                        .findAllByCssSelector('form.create-cluster-form span.help-block')
                                        .then(function(errorMessages) {
                                            assert.ok(errorMessages.length, 'Error message should be displayed if names are duplicated');
                                            return errorMessages[0]
                                                .getVisibleText()
                                                .then(function(errorMessage) {
                                                    assert.equal(
                                                        errorMessage,
                                                        'Environment with name "' + clusterName + '" already exists',
                                                        'Error message should say that environment with that name already exists'
                                                    );
                                                })
                                                .then(function() {
                                                    return modal.close();
                                                });
                                        })
                                }}
                            );
                });
            },
            'Testing cluster list page': function() {
                return this.remote
                    .setFindTimeout(1000)
                    .clickLinkByText('Environments')
                    .setFindTimeout(2000)
                    .then(function() {
                        return common.assertElementExists('.clusters-page .clusterbox', 'Cluster container exists');
                    })
                    .then(function() {
                        return common.assertElementExists('.create-cluster', 'Cluster creation control exists');
                    });
            }
        };
    });
});
