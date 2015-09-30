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
            fetchData: function() {
                var nodes = new models.Nodes(),
                    clusters = new models.Clusters();
                return $.when(
                    nodes.fetch(),
                    clusters.fetch(),
                    app.nodeNetworkGroups.fetch()
                ).then(function() {
                    return $.when.apply($, clusters.map(function(cluster) {
                        var roles = new models.Roles();
                        roles.url = _.result(cluster, 'url') + '/roles';
                        cluster.set({roles: roles});
                        return roles.fetch();
                    }));
                }).then(function() {
                    return $.when.apply($, clusters.map(function(cluster) {
                        var release = new models.Release({id: cluster.get('release_id')});
                        cluster.set({release: release});
                        return release.fetch();
                    }));
                }).then(function() {
                    return {
                        nodes: nodes,
                        clusters: clusters
                    };
                });
            }
        },
        getInitialState: function() {
            return {
                selectedNodeIds: []
            };
        },
        selectNodes: function(ids, checked) {
            var nodeSelection = {};
            if (ids && ids.length) {
                nodeSelection = this.state.selectedNodeIds;
                _.each(ids, function(id) {
                    if (checked) {
                        nodeSelection[id] = true;
                    } else {
                        delete nodeSelection[id];
                    }
                });
            }
            this.setState({selectedNodeIds: nodeSelection});
        },
        render: function() {
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
                            sorters={this.props.nodes.sorters}
                            defaultSorting={[{status: 'asc'}]}
                            filters={this.props.nodes.filters}
                            statusesToFilter={(this.props.nodes.at(0) || {}).statuses}
                            defaultFilters={{status: []}}
                        />
                    </div>
                </div>
            );
        }
    });

    return NodesPage;
});
