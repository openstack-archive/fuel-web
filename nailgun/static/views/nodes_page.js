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
    'views/cluster_page_tabs/nodes_tab_screens/node_list_screen'
],
function($, _, i18n, React, models, componentMixins, NodeListScreen) {
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
                    releases = app.releases,
                    nodeNetworkGroups = app.nodeNetworkGroups;
                return $.when(
                    nodes.fetch(),
                    clusters.fetch(),
                    releases.fetch({cache: true}),
                    nodeNetworkGroups.fetch({cache: true})
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
                }).then(() => ({nodes, clusters, nodeNetworkGroups}));
            }
        },
        getInitialState() {
            return {
                selectedNodeIds: []
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
        render() {
            var roles = new models.Roles();
            this.props.clusters.each((cluster) => {
                roles.add(
                    cluster.get('roles').filter((role) => !roles.findWhere({name: role.get('name')}))
                );
            });
            return (
                <div className='nodes-page'>
                    <div className='page-title'>
                        <h1 className='title'>{i18n('nodes_page.title')}</h1>
                    </div>
                    <div className='content-box'>
                        <NodeListScreen {...this.props}
                            ref='screen'
                            selectedNodeIds={this.state.selectedNodeIds}
                            selectNodes={this.selectNodes}
                            roles={roles}
                            sorters={models.Nodes.prototype.sorters}
                            defaultSorting={[{status: 'asc'}]}
                            filters={models.Nodes.prototype.filters}
                            statusesToFilter={models.Node.prototype.statuses}
                            defaultFilters={{status: []}}
                        />
                    </div>
                </div>
            );
        }
    });

    return NodesPage;
});
