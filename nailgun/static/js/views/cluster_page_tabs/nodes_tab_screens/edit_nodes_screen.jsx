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
    'utils',
    'jsx!views/cluster_page_tabs/nodes_tab_screens/node_list_screen'
],
function(_, React, models, utils, NodeListScreen) {
    'use strict';

    var EditNodesScreen = React.createClass({
        getInitialState: function() {
            var ids = utils.deserializeTabOptions(this.props.screenOptions[0]).nodes.split(',').map(function(id) {return parseInt(id, 10);});
            return {nodes: new models.Nodes(this.props.model.get('nodes').filter(function(node) {return _.contains(ids, node.id);}))};
        },
        render: function() {
            return <NodeListScreen
                ref='screen'
                mode='edit'
                cluster={this.props.model}
                nodes={this.state.nodes}
            />;
        }
    });

    return EditNodesScreen;
});
