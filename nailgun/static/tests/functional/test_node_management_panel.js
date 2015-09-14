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
    'tests/functional/pages/dashboard',
    'tests/helpers'
], function(registerSuite, assert, Common, ClusterPage, DashboardPage) {
    'use strict';

    registerSuite(function() {
        var common,
            clusterPage,
            dashboardPage,
            clusterName,
            searchButtonSelector = '.node-management-panel .btn-search',
            sortingButtonSelector = '.node-management-panel .btn-sorters',
            filtersButtonSelector = '.node-management-panel .btn-filters';

        return {
            name: 'Node management panel on cluster nodes page: search, sorting, filtering',
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
            'Test management controls state in new environment': function() {
                return this.remote
                    .then(function() {
                        return common.assertElementDisabled(searchButtonSelector, 'Search button is locked if there are no nodes in environment');
                    })
                    .then(function() {
                        return common.assertElementDisabled(sortingButtonSelector, 'Sorting button is locked if there are no nodes in environment');
                    })
                    .then(function() {
                        return common.assertElementDisabled(filtersButtonSelector, 'Filters button is locked if there are no nodes in environment');
                    })
                    .then(function() {
                        return common.assertElementNotExists('.active-sorters-filters', 'Applied sorters and filters are not shown for empty environment');
                    });
            },
            'Test management controls behaviour': {
                setup: function() {
                    dashboardPage = new DashboardPage(this.remote);
                },
                beforeEach: function() {
                    return this.remote
                        .then(function() {
                            return common.addNodesToCluster(3, ['Controller']);
                        })
                        .then(function() {
                            return common.addNodesToCluster(1, ['Compute'], 'error');
                        });
                },
                afterEach: function() {
                    return this.remote
                        .then(function() {
                            return clusterPage.goToTab('Dashboard');
                        })
                        .then(function() {
                            return dashboardPage.discardChanges();
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
                                return assert.equal(elements.length, 3, 'Search was successfull');
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
                        .then(function() {
                            return common.assertElementExists(activeSortersPanelSelector, 'Active sorters panel is shown if there are nodes in cluster');
                        })
                        .then(function() {
                            return common.assertElementNotExists(activeSortersPanelSelector + '.btn-reset-sorting', 'Default sorting can not be reset from active sorters panel');
                        })
                        .clickByCssSelector(sortingButtonSelector)
                        .findAllByCssSelector('.sorters .sorter-control')
                            .then(function(elements) {
                                return assert.equal(elements.length, 1, 'Cluster node list has one sorting by default');
                            })
                            .end()
                        .then(function() {
                            return common.assertElementExists('.sorters .sort-by-roles-asc', 'Check default sorting by roles');
                        })
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
                        .clickByCssSelector('.sorters .sort-by-roles-asc button')
                        .findByCssSelector('.node-list .node-name .name p')
                            .getVisibleText().then(function(text) {
                                assert.notEqual(text, firstNodeName, 'Order of sorting by roles was changed to desc');
                            })
                            .end()
                        .clickByCssSelector('.sorters .sort-by-roles-desc button')
                        .then(function() {
                            return common.assertElementTextEqualTo('.node-list .node-name .name p', firstNodeName, 'Order of sorting by roles was changed to asc (default)');
                        })
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
                },
                'Test node list filtering': function() {
                    var activeFiltersPanelSelector = '.active-filters',
                        moreControlSelector = '.filters .more-control';
                    return this.remote
                        .then(function() {
                            return common.assertElementNotExists(activeFiltersPanelSelector , 'Environment has no active filters by default');
                        })
                        .clickByCssSelector(filtersButtonSelector)
                        .findAllByCssSelector('.filters .filter-control')
                            .then(function(elements) {
                                return assert.equal(elements.length, 2, 'Filters panel has 2 default filters');
                            })
                            .end()
                        .clickByCssSelector('.filter-by-roles')
                        .then(function() {
                            return common.assertElementNotExists('.filter-by-roles [type=checkbox]:checked' , 'There are no active options in Roles filter');
                        })
                        .then(function() {
                            return common.assertElementNotExists('.filters .filter-control .btn-remove-filter', 'Default filters can not be deleted from filters panel');
                        })
                        .then(function() {
                            return common.assertElementNotExists('.filters .btn-reset-filters', 'No filters to be reset');
                        })
                        .clickByCssSelector(moreControlSelector + ' button')
                        .findAllByCssSelector(moreControlSelector + ' .popover .checkbox-group')
                            .then(function(elements) {
                                return assert.equal(elements.length, 7, 'Standard node filters are presented');
                            })
                            .end()
                        .clickByCssSelector(moreControlSelector + ' [name=cores]')
                        .findAllByCssSelector('.filters .filter-control')
                            .then(function(elements) {
                                return assert.equal(elements.length, 3, 'New Cores (real) filter was added');
                            })
                            .end()
                        // check new filter is open
                        .findByCssSelector('.filter-by-cores .popover-content')
                            .end()
                        .clickByCssSelector('.filters .filter-by-cores .btn-remove-filter')
                        .findAllByCssSelector('.filters .filter-control')
                            .then(function(elements) {
                                return assert.equal(elements.length, 2, 'Particular filter removal works');
                            })
                            .end()
                        .clickByCssSelector(moreControlSelector + ' button')
                        .clickByCssSelector(moreControlSelector + ' [name=disks_amount]')
                        .findAllByCssSelector('.filters .filter-by-disks_amount input[type=number]:not(:disabled)')
                            .then(function(elements) {
                                return assert.equal(elements.length, 2, 'Number filter has 2 fields to set min and max value');
                            })
                            .end()
                        // set min value more than max value
                        .setInputValue('.filters .filter-by-disks_amount input[type=number][name=start]', '100')
                        // validation works for Number range filter
                        .waitForCssSelector('.filters .filter-by-disks_amount .form-group.has-error', 2000)
                        .findAllByCssSelector('.node-list .node')
                            .then(function(elements) {
                                return assert.equal(elements.length, 0, 'No nodes match invalid filter');
                            })
                            .end()
                        .clickByCssSelector('.filters .btn-reset-filters')
                        .findAllByCssSelector('.node-list .node')
                            .then(function(elements) {
                                return assert.equal(elements.length, 4, 'Node filtration was successfully reset');
                            })
                            .end()
                        .clickByCssSelector('.filters .filter-by-status button')
                        .clickByCssSelector('.filters .filter-by-status [name=error]')
                        .findAllByCssSelector('.node-list .node')
                            .then(function(elements) {
                                return assert.equal(elements.length, 1, 'Node with error status successfully filtered');
                            })
                            .end()
                        .clickByCssSelector('.filters .filter-by-status [name=pending_addition]')
                        .findAllByCssSelector('.node-list .node')
                            .then(function(elements) {
                                return assert.equal(elements.length, 4, 'All nodes shown');
                            })
                            .end()
                        .clickByCssSelector(filtersButtonSelector)
                        .then(function() {
                            return common.assertElementExists(activeFiltersPanelSelector , 'Applied filter is reflected in active filters panel');
                        })
                        // check Reset filters button exists in active filters panel
                        .findByCssSelector('.active-filters .btn-reset-filters')
                            .end();
                }
            }
        };
    });
});
