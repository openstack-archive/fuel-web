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
    'jquery',
    'underscore',
    'react',
    'models',
    'views/cluster_page_tabs/nodes_tab_screens/node_list_screen',
    'views/cluster_page_tabs/nodes_tab_screens/node_list_screen_objects'
],
function($, _, React, models, NodeListScreen, objects) {
    'use strict';

    var AddNodesScreen = React.createClass({
        statics: {
            fetchData(options) {
                var nodes = new models.Nodes();
                nodes.fetch = function(options) {
                    return this.constructor.__super__.fetch.call(this, _.extend({data: {cluster_id: ''}}, options));
                };
                return $.when(
                    nodes.fetch(),
                    options.cluster.get('roles').fetch(),
                    options.cluster.get('settings').fetch({cache: true})
                ).then(() => ({nodes}));
            }
        },
        getInitialState() {
            var defaultFilters = {status: []},
                activeFilters = objects.Filter.fromObject(defaultFilters, false);
            _.invoke(activeFilters, 'updateLimits', this.props.nodes, false);

            var defaultSorting = [{status: 'asc'}],
                activeSorters = _.map(defaultSorting, _.partial(objects.Sorter.fromObject, _, false));

            var roles = this.props.cluster.get('roles').pluck('name'),
                selectedRoles = this.props.nodes.length ? _.filter(roles, (role) => !this.props.nodes.any((node) => !node.hasRole(role))) : [],
                indeterminateRoles = this.props.nodes.length ? _.filter(roles, (role) => !_.contains(selectedRoles, role) && this.props.nodes.any((node) => node.hasRole(role))) : [];

            var configModels = {
                    cluster: this.props.cluster,
                    settings: this.props.cluster.get('settings'),
                    version: app.version,
                    default: this.props.cluster.get('settings')
                };

            return {
                defaultFilters,
                activeFilters,
                defaultSorting,
                activeSorters,
                selectedRoles,
                indeterminateRoles,
                configModels
            };
        },
        updateSearch(value) {
            this.setState({search: value});
        },
        changeViewMode(value) {
            this.setState({viewMode: value});
        },
        updateSorting(sorters) {
            this.setState({activeSorters: sorters});
        },
        updateFilters(filters) {
            this.setState({activeFilters: filters});
        },
        selectRoles(role, checked) {
            var selectedRoles = this.state.selectedRoles;
            if (checked) {
                selectedRoles.push(role);
            } else {
                selectedRoles = _.without(selectedRoles, role);
            }
            this.setState({
                selectedRoles: selectedRoles,
                indeterminateRoles: _.without(this.state.indeterminateRoles, role)
            });
        },
        render() {
            var nodes = this.props.cluster.get('nodes');
            return <NodeListScreen
                ref='screen'
                {... _.omit(this.props, 'screenOptions')}
                {...this.state}
                {... _.pick(this,
                    'updateSearch',
                    'changeViewMode',
                    'updateSorting',
                    'updateFilters',
                    'selectRoles'
                )}
                mode='add'
                roles={this.props.cluster.get('roles')}
                showRolePanel
                availableSorters={
                    _.without(models.Nodes.prototype.sorters,
                        'cluster',
                        'roles',
                        'group_id'
                    ).map((name) => new objects.Sorter(name, 'asc', false))
                }
                availableFilters={
                    _.without(models.Nodes.prototype.filters,
                        'cluster',
                        'roles',
                        'group_id'
                    ).map((name) => {
                        var filter = new objects.Filter(name, [], false);
                        filter.updateLimits(nodes, true);
                        return filter;
                    })
                }
                statusesToFilter={
                    _.without(models.Node.prototype.statuses,
                        'ready',
                        'pending_addition',
                        'pending_deletion',
                        'provisioned',
                        'provisioning',
                        'deploying'
                    )
                }
            />;
        }
    });

    return AddNodesScreen;
});
