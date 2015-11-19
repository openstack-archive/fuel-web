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
define(
[
    'jquery',
    'underscore',
    'i18n',
    'react',
    'models',
    'component_mixins',
    'views/cluster_page_tabs/nodes_tab_screens/node_list_screen',
    'views/cluster_page_tabs/nodes_tab_screens/node_list_screen_objects'
],
function($, _, i18n, React, models, componentMixins, NodeListScreen, objects) {
    'use strict';

    var NodesPage;

    NodesPage = React.createClass({
        mixins: [componentMixins.backboneMixin('nodes')],
        statics: {
            title: i18n('nodes_page.title'),
            navbarActiveElement: 'nodes',
            breadcrumbsPath: [['home', '#'], 'nodes'],
            fetchData() {
                var nodes = new models.Nodes(),
                    clusters = new models.Clusters(),
                    {releases, nodeNetworkGroups, fuelSettings} = app;

                return $.when(
                    nodes.fetch(),
                    clusters.fetch(),
                    releases.fetch({cache: true}),
                    nodeNetworkGroups.fetch({cache: true}),
                    fuelSettings.fetch({cache: true})
                ).then(() => {
                    clusters.each(
                        (cluster) => cluster.set({
                            release: releases.get(cluster.get('release_id'))
                        })
                    );
                    return $.when(...clusters.map(function(cluster) {
                        var roles = new models.Roles();
                        roles.url = _.result(cluster, 'url') + '/roles';
                        cluster.set({roles: roles});
                        return roles.fetch();
                    }));
                }).then(() => ({nodes, clusters, nodeNetworkGroups, fuelSettings}));
            }
        },
        getInitialState() {
            var uiSettings = this.props.fuelSettings.get('ui_settings');

            var defaultFilters = {status: []},
                activeFilters = _.union(
                    objects.Filter.fromObject(_.extend({}, defaultFilters, uiSettings.filter), false),
                    objects.Filter.fromObject(uiSettings.filter_by_labels, true)
                );
            _.invoke(activeFilters, 'updateLimits', this.props.nodes, false);

            var activeSorters = _.union(
                    _.map(uiSettings.sort, _.partial(objects.Sorter.fromObject, _, false)),
                    _.map(uiSettings.sort_by_labels, _.partial(objects.Sorter.fromObject, _, true))
                );

            var search = uiSettings.search,
                viewMode = uiSettings.view_mode;

            var selectedNodeIds = [];

            return {
                defaultFilters,
                activeFilters,
                activeSorters,
                search,
                viewMode,
                selectedNodeIds
            };
        },
        selectNodes(ids = [], checked = false) {
            var nodeSelection = {};
            if (ids.length) {
                nodeSelection = this.state.selectedNodeIds;
                _.each(ids, (id) => {
                    if (checked) {
                        nodeSelection[id] = true;
                    } else {
                        delete nodeSelection[id];
                    }
                });
            }
            this.setState({selectedNodeIds: nodeSelection});
        },
        updateUISettings(name, value) {
            var uiSettings = this.props.fuelSettings.get('ui_settings');
            uiSettings[name] = value;
            this.props.fuelSettings.save(null, {patch: true, wait: true, validate: false});
        },
        updateSearch(value) {
            this.setState({search: value});
            this.updateUISettings('search', _.trim(value));
        },
        changeViewMode(value) {
            this.setState({viewMode: value});
            this.updateUISettings('view_mode', value);
        },
        updateSorting(sorters, updateLabelsOnly) {
            //console.log(_.pluck(sorters, 'name'));
            this.setState({activeSorters: sorters});
            var groupedSorters = _.groupBy(sorters, 'isLabel');
            if (!updateLabelsOnly) {
                this.updateUISettings('sort', _.map(groupedSorters.false, objects.Sorter.toObject));
            }
            this.updateUISettings('sort_by_labels', _.map(groupedSorters.true, objects.Sorter.toObject));
        },
        updateFilters(filters, updateLabelsOnly) {
            this.setState({activeFilters: filters});
            var groupedFilters = _.groupBy(filters, 'isLabel');
            if (!updateLabelsOnly) {
                this.updateUISettings('filter', objects.Filter.toObject(groupedFilters.false));
            }
            this.updateUISettings('filter_by_labels', objects.Filter.toObject(groupedFilters.true));
        },
        getRoles() {
            var roles = new models.Roles();
            this.props.clusters.each((cluster) => {
                roles.add(
                    cluster.get('roles').filter((role) => !roles.any({name: role.get('name')}))
                );
            });
            return roles;
        },
        render() {
            var {nodes} = this.props;
            return (
                <div className='nodes-page'>
                    <div className='page-title'>
                        <h1 className='title'>{i18n('nodes_page.title')}</h1>
                    </div>
                    <div className='content-box'>
                        <NodeListScreen
                            ref='screen'
                            {...this.props}
                            {...this.state}
                            {... _.pick(this,
                                'selectNodes',
                                'updateSearch',
                                'changeViewMode',
                                'updateSorting',
                                'updateFilters'
                            )}
                            roles={this.getRoles()}
                            availableSorters={
                                models.Nodes.prototype.sorters.map((name) => new objects.Sorter(name, 'asc', false))
                            }
                            defaultSorting={[{status: 'asc'}]}
                            availableFilters={models.Nodes.prototype.filters.map((name) => {
                                var filter = new objects.Filter(name, [], false);
                                filter.updateLimits(nodes, true);
                                return filter;
                            })}
                            statusesToFilter={models.Node.prototype.statuses}
                        />
                    </div>
                </div>
            );
        }
    });

    return NodesPage;
});
