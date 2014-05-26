/*
 * Copyright 2013 Mirantis, Inc.
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
    'utils',
    'models',
    'views/cluster_page_tabs/nodes_tab_screens/node_list_screen'
],
function(utils, models, NodeListScreen) {
    'use strict';
    var EditNodesScreen;

    EditNodesScreen = NodeListScreen.extend({
        constructorName: 'EditNodesScreen',
        initialize: function(options) {
            _.defaults(this, options);
            var nodeIds = utils.deserializeTabOptions(this.screenOptions[0]).nodes.split(',').map(function(id) {return parseInt(id, 10);});
            this.nodes = new models.Nodes(this.model.get('nodes').getByIds(nodeIds));
            this.nodes.cluster = this.model;
            this.nodes.fetch = function(options) {
                return this.constructor.__super__.fetch.call(this, _.extend({data: {cluster_id: this.cluster.id}}, options));
            };
            this.nodes.parse = function(response) {
                return _.filter(response, function(node) {return _.contains(nodeIds, node.id);});
            };
            this.constructor.__super__.initialize.apply(this, arguments);
        }
    });

    return EditNodesScreen;
});
