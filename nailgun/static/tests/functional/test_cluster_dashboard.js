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
    'underscore',
    'intern!object',
    'intern/chai!assert',
    'tests/functional/pages/common',
    'tests/functional/pages/cluster',
    'tests/functional/pages/dashboard',
    'tests/functional/pages/modal'
], function(_, registerSuite, assert, Common, ClusterPage, DashboardPage, ModalWindow) {
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
            teardown: function() {
                return this.remote
                    .then(function() {
                        return common.removeCluster(clusterName);
                    });
            },

            'Add nodes button is present and works on freshly created cluster': function() {
                return this.remote
                    .then(function() {
                        return dashboardPage.isAddNodesButtonVisible();
                    })
                    .then(function(isVisible) {
                        assert.isTrue(isVisible, 'Add nodes button is visible on new cluster');
                    })
                        .end()
                    .findByCssSelector('.btn-add-nodes')
                        .click()
                        .end()
                    .getCurrentUrl()
                        .then(function(url) {
                            assert.isTrue(_.contains(url, 'nodes/add'), 'Add nodes button navigates from Dashboard to Add nodes screen');
                        })
                        .end();
            },

            'Renaming cluster works': function() {
                return this.remote
                    .setFindTimeout(100)
                    .findByCssSelector('.cluster-info-value.name .glyphicon-pencil')
                        .click()
                        .end()
                    .findAllByCssSelector('.rename-block input[type=text]')
                        .then(function(elements) {
                            assert.ok(elements.length, 'Rename control appears')
                        })
                    // Escape
                        .type('')
                        .end()
                    .findAllByCssSelector('.rename-block input[type=text]')
                        .then(function(elements) {
                            assert.notOk(elements.length, 'Rename control disappears')
                        })
            }
// @todo: reafactor rename and warnings appearence
        };
    });
});
