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
    'views/cluster_page_tabs/nodes_tab_screens/node_list_screen'
],
function($, _, React, models, NodeListScreen) {
    'use strict';

    var AddNodesScreen = React.createClass({
        statics: {
            fetchData(options) {
                var nodes = new models.Nodes();
                nodes.fetch = function(options) {
                    return this.constructor.__super__.fetch.call(this, _.extend({data: {cluster_id: ''}}, options));
                };
                return $.when(nodes.fetch(), options.cluster.get('roles').fetch(), options.cluster.get('settings').fetch({cache: true})).then(function() {
                    return {nodes: nodes};
                });
            }
        },
        render() {
            return <NodeListScreen {... _.omit(this.props, 'screenOptions')}
                ref='screen'
                mode='add'
                roles={this.props.cluster.get('roles')}
                sorters={_.without(models.Nodes.prototype.sorters, 'cluster', 'roles', 'group_id')}
                defaultSorting={[{status: 'asc'}]}
                filters={_.without(models.Nodes.prototype.filters, 'cluster', 'roles', 'group_id')}
                statusesToFilter={_.without(models.Node.prototype.statuses,
                    'ready',
                    'pending_addition',
                    'pending_deletion',
                    'provisioned',
                    'provisioning',
                    'deploying'
                )}
                defaultFilters={{status: []}}
            />;
        }
    });

    return AddNodesScreen;
});
