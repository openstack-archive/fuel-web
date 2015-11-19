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
    'utils',
    'views/cluster_page_tabs/nodes_tab_screens/node_list_screen',
    'views/cluster_page_tabs/nodes_tab_screens/node_list_screen_objects'
],
function($, _, React, models, utils, NodeListScreen, objects) {
    'use strict';

    var EditNodesScreen = React.createClass({
        statics: {
            fetchData(options) {
                var cluster = options.cluster,
                    nodes = utils.getNodeListFromTabOptions(options);

                if (!nodes) return $.Deferred().reject();

                nodes.fetch = function(options) {
                    return this.constructor.__super__.fetch.call(this, _.extend({data: {cluster_id: cluster.id}}, options));
                };
                nodes.parse = function() {
                    return this.getByIds(nodes.pluck('id'));
                };
                return $.when(
                    options.cluster.get('roles').fetch(),
                    cluster.get('settings').fetch({cache: true})
                ).then(() => ({nodes: nodes}));
            }
        },
        getInitialState() {
            var defaultSorting = [{roles: 'asc'}];
            return {
                viewMode: this.props.cluster.get('ui_settings').view_mode,
                defaultSorting: defaultSorting,
                activeSorters: _.map(defaultSorting, _.partial(objects.Sorter.fromObject, _, false)),
                configModels: {
                    cluster: this.props.cluster,
                    settings: this.props.cluster.get('settings'),
                    version: app.version,
                    default: this.props.cluster.get('settings')
                }
            };
        },
        changeViewMode(value) {
            this.setState({viewMode: value});
            this.props.updateUISettings('view_mode', value);
        },
        render() {
            return (
                <NodeListScreen
                    {... _.omit(this.props, 'screenOptions')}
                    {... this.state}
                    ref='screen'
                    mode='edit'
                    roles={this.props.cluster.get('roles')}
                    showRolePanel
                    defaultSorting={[{roles: 'asc'}]}
                    changeViewMode={this.changeViewMode}
                />
            );
        }
    });

    return EditNodesScreen;
});
