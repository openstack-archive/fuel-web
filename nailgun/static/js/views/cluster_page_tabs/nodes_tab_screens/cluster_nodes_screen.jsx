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
    'jsx!views/cluster_page_tabs/nodes_tab_screens/node_list_screen'
],
function(_, React, NodeListScreen) {
    'use strict';

    var ClusterNodesScreen = React.createClass({
        hasChanges: false,
        componentWillMount: function() {
            var cluster = this.props.cluster;
            cluster.get('nodes').fetch = function(options) {
                return this.constructor.__super__.fetch.call(this, _.extend({data: {cluster_id: cluster.id}}, options));
            };
        },
        render: function() {
            return <NodeListScreen
                ref='screen'
                mode='list'
                cluster={this.props.cluster}
                nodes={this.props.cluster.get('nodes')}
            />;
        }
    });

    return ClusterNodesScreen;
});
