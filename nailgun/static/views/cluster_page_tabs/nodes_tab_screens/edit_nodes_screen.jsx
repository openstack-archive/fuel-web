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
    'jsx!component_mixins',
    'jsx!views/cluster_page_tabs/nodes_tab_screens/node_list_screen'
],
function($, _, React, models, utils, ComponentMixins, NodeListScreen) {
    'use strict';

    var EditNodesScreen = React.createClass({
        statics: {
            fetchData: function(options) {
                var cluster = options.cluster,
                    nodes = ComponentMixins.nodeConfigurationScreenMixin.getNodeList(options);

                if (!nodes) {
                    return $.Deferred().reject();
                }

                nodes.fetch = function(options) {
                    return this.constructor.__super__.fetch.call(this, _.extend({data: {cluster_id: cluster.id}}, options));
                };
                nodes.parse = function() {
                    return this.getByIds(nodes.pluck('id'));
                };
                return $.when(options.cluster.get('roles').fetch(), cluster.get('settings').fetch({cache: true})).then(function() {
                    return {nodes: nodes};
                });
            }
        },
        render: function() {
            return <NodeListScreen {... _.omit(this.props, 'screenOptions')} ref='screen' mode='edit' />;
        }
    });

    return EditNodesScreen;
});
