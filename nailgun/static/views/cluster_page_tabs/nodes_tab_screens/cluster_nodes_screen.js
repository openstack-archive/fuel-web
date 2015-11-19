/*
 * Copyright 2014 Mirantis, Inc.
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
define(
[
    'underscore',
    'react',
    'models',
    'views/cluster_page_tabs/nodes_tab_screens/node_list_screen',
    'views/cluster_page_tabs/nodes_tab_screens/node_list_screen_objects'
],
function(_, React, models, NodeListScreen, objects) {
    'use strict';

    var ClusterNodesScreen = React.createClass({
        getInitialState() {
            var uiSettings = this.props.cluster.get('ui_settings');

            var defaultFilters = {roles: [], status: []},
                activeFilters = _.union(
                    objects.Filter.fromObject(_.extend({}, defaultFilters, uiSettings.filter), false),
                    objects.Filter.fromObject(uiSettings.filter_by_labels, true)
                );
            _.invoke(activeFilters, 'updateLimits', this.props.cluster.get('nodes'), false);

            var activeSorters = _.union(
                    _.map(uiSettings.sort, _.partial(objects.Sorter.fromObject, _, false)),
                    _.map(uiSettings.sort_by_labels, _.partial(objects.Sorter.fromObject, _, true))
                );

            var search = uiSettings.search,
                viewMode = uiSettings.view_mode;

            return {
                defaultFilters,
                activeFilters,
                activeSorters,
                search,
                viewMode
            };
        },
        updateSearch(value) {
            this.setState({search: value});
            this.props.updateUISettings('search', _.trim(value));
        },
        changeViewMode(value) {
            this.setState({viewMode: value});
            this.props.updateUISettings('view_mode', value);
        },
        updateSorting(sorters, updateLabelsOnly) {
            this.setState({activeSorters: sorters});
            var groupedSorters = _.groupBy(sorters, 'isLabel');
            if (!updateLabelsOnly) {
                this.props.updateUISettings('sort', _.map(groupedSorters.false, objects.Sorter.toObject));
            }
            this.props.updateUISettings('sort_by_labels', _.map(groupedSorters.true, objects.Sorter.toObject));
        },
        updateFilters(filters, updateLabelsOnly) {
            this.setState({activeFilters: filters});
            var groupedFilters = _.groupBy(filters, 'isLabel');
            if (!updateLabelsOnly) {
                this.props.updateUISettings('filter', objects.Filter.toObject(groupedFilters.false));
            }
            this.props.updateUISettings('filter_by_labels', objects.Filter.toObject(groupedFilters.true));
        },
        render() {
            var nodes = this.props.cluster.get('nodes');
            return <NodeListScreen
                ref='screen'
                {... _.omit(this.props, 'screenOptions', 'updateUISettings')}
                {...this.state}
                {... _.pick(this,
                    'updateSearch',
                    'changeViewMode',
                    'updateSorting',
                    'updateFilters'
                )}
                mode='list'
                nodes={nodes}
                roles={this.props.cluster.get('roles')}
                defaultSorting={[{roles: 'asc'}]}
                availableSorters={_.without(models.Nodes.prototype.sorters, 'cluster').map(
                    (name) => new objects.Sorter(name, 'asc', false)
                )}
                availableFilters={_.without(models.Nodes.prototype.filters, 'cluster').map((name) => {
                    var filter = new objects.Filter(name, [], false);
                    filter.updateLimits(nodes, true);
                    return filter;
                })}
                statusesToFilter={_.without(models.Node.prototype.statuses, 'discover')}
            />;
        }
    });

    return ClusterNodesScreen;
});
