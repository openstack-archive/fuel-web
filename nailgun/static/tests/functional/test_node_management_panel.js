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
    'tests/helpers'
], function(registerSuite, assert, Common, ClusterPage) {
    'use strict';

    registerSuite(function() {
        var common,
            clusterPage,
            clusterName,
            searchButtonSelector = '.node-management-panel .btn-search',
            sortingButtonSelector = '.node-management-panel .btn-sorters';

        return {
            name: 'Node manamenet panel: sorting, filtering, search, labels',
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
            teardown: function() {
                return this.remote
                    .then(function() {
                        return common.removeCluster(clusterName);
                    });
            },
            'Test new environment': function() {
                return this.remote
                    .then(function() {
                        return common.assertElementDisabled(searchButtonSelector, 'Search button is locked if there are no nodes in environment');
                    })
                    .then(function() {
                        return common.assertElementDisabled(sortingButtonSelector, 'Sorting button is locked if there are no nodes in environment');
                    })
                    .then(function() {
                        return common.assertElementNotExists('.active-sorters-filters', 'Applied sorters and filters are not shown for empty environment');
                    })
                    .then(function() {
                        return common.addNodesToCluster(3, ['Controller']);
                    })
                    .then(function() {
                        return common.addNodesToCluster(1, ['Compute']);
                    });
            },
            'Test search control': function() {
                var searchInputSelector = '.node-management-panel [name=search]';
                return this.remote
                    .clickByCssSelector(searchButtonSelector)
                    .waitForCssSelector(searchInputSelector, 200)
                    .setInputValue(searchInputSelector, 'Super')
                    // need to wait debounced search input
                    .sleep(200)
                    .findAllByCssSelector('.node-list .node')
                        .then(function(elements) {
                            return assert.equal(elements.length, 2, 'Search was successfull');
                        })
                        .end()
                    .clickByCssSelector('.node-list')
                    .then(function() {
                        return common.assertElementNotExists(searchButtonSelector, 'Active search control remains open when clicking outside the input');
                    })
                    .clickByCssSelector('.node-management-panel .btn-clear-search')
                    .findAllByCssSelector('.node-list .node')
                        .then(function(elements) {
                            return assert.equal(elements.length, 4, 'Search was reset');
                        })
                        .end()
                    .then(function() {
                        return common.assertElementNotExists(searchButtonSelector, 'Search input is still shown after search reset');
                    })
                    .clickByCssSelector('.node-list')
                    .then(function() {
                        return common.assertElementExists(searchButtonSelector, 'Empty search control is closed when clicking outside the input');
                    });
            },
            'Test node list sorting': function() {
                var activeSortersPanelSelector = '.active-sorters',
                    moreControlSelector = '.sorters .more-control',
                    firstNodeName;
                return this.remote
                    // active sorters panel is shown
                    .findByCssSelector(activeSortersPanelSelector)
                        .end()
                    .then(function() {
                        return common.assertElementNotExists(activeSortersPanelSelector + '.btn-reset-sorting', 'Default sorting can not be reset from active sorters panel');
                    })
                    .clickByCssSelector(sortingButtonSelector)
                    .findAllByCssSelector('.sorters .sorter-control')
                        .then(function(elements) {
                            return assert.equal(elements.length, 1, 'Cluster node list has one sorting by default');
                        })
                        .end()
                    // check default sorting
                    .findByCssSelector('.sorters .sort-by-roles-asc')
                        .end()
                    .then(function() {
                        return common.assertElementNotExists('.sorters .sorter-control .btn-remove-sorting', 'Node list should have at least one applied sorting');
                    })
                    .then(function() {
                        return common.assertElementNotExists('.sorters .btn-reset-sorting', 'Default sorting can not be reset');
                    })
                    .findByCssSelector('.node-list .node-name .name p')
                        .getVisibleText().then(function(text) {
                            firstNodeName = text;
                        })
                        .end()
                    // change order of sorting by roles
                    .clickByCssSelector('.sorters .sort-by-roles-asc button')
                    .findByCssSelector('.node-list .node-name .name p')
                        .getVisibleText().then(function(text) {
                            assert.isTrue(firstNodeName != text, 'Order of sorting by roles was changed');
                        })
                        .end()
                    .clickByCssSelector(moreControlSelector + ' button')
                    .findAllByCssSelector(moreControlSelector + ' .popover .checkbox-group')
                        .then(function(elements) {
                            return assert.equal(elements.length, 11, 'Standard node sorters are presented');
                        })
                        .end()
                    // add sorting by CPU (real)
                    .clickByCssSelector(moreControlSelector + ' .popover [name=cores]')
                    // add sorting by manufacturer
                    .clickByCssSelector(moreControlSelector + ' .popover [name=manufacturer]')
                    .findAllByCssSelector('.node-list .nodes-group')
                        .then(function(elements) {
                            return assert.equal(elements.length, 4, 'New sorting was applied and nodes were grouped');
                        })
                        .end()
                    // remove sorting by manufacturer
                    .clickByCssSelector('.sorters .sort-by-manufacturer-asc .btn-remove-sorting')
                    .findAllByCssSelector('.node-list .nodes-group')
                        .then(function(elements) {
                            return assert.equal(elements.length, 3, 'Particular sorting removal works');
                        })
                        .end()
                    .clickByCssSelector('.sorters .btn-reset-sorting')
                    .findAllByCssSelector('.node-list .nodes-group')
                        .then(function(elements) {
                            return assert.equal(elements.length, 2, 'Sorting was successfully reset to default');
                        })
                        .end()
                    .clickByCssSelector(sortingButtonSelector)
                    .clickByCssSelector(activeSortersPanelSelector)
                    // check active sorters panel is clickable and opens sorters panel
                    .findByCssSelector('.sorters')
                        .end();
            }
        };
    });
});
