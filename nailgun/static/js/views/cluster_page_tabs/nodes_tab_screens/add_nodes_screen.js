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
    var AddNodesScreen;

    AddNodesScreen = NodeListScreen.extend({
        constructorName: 'AddNodesScreen',
        removeRoles: function(node, checked, options) {
            if (!checked) {
                node.set({pending_roles: []}, {assign: true});
            }
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.nodes = new models.Nodes();
            this.nodes.fetch = function(options) {
                return this.constructor.__super__.fetch.call(this, _.extend({data: {cluster_id: ''}}, options));
            };
            this.constructor.__super__.initialize.apply(this, arguments);
            this.nodes.on('change:checked', this.removeRoles, this);
            this.nodes.deferred = this.nodes.fetch().done(_.bind(this.render, this));
        }
    });

    return AddNodesScreen;
});
