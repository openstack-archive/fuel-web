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
    'jsx!views/cluster_page_tabs/nodes_tab_screens/node_list_screen'
],
function($, _, React, models, NodeListScreen) {
    'use strict';

    var AddNodesScreen = React.createClass({
        statics: {
            fetchData: function(options) {
                var nodes = new models.Nodes();
                nodes.fetch = function(options) {
                    return this.constructor.__super__.fetch.call(this, _.extend({data: {cluster_id: ''}}, options));
                };
                return $.when(nodes.fetch(), options.cluster.get('settings').fetch({cache: true})).then(function() {
                    return {nodes: nodes};
                });
            }
        },
        hasChanges: function() {
            return _.result(this.refs.screen, 'hasChanges');
        },
        revertChanges: function() {
            return this.refs.screen.revertChanges();
        },
        render: function() {
            return <NodeListScreen {... _.omit(this.props, 'screenOptions')}
                ref='screen'
                mode='add'
                sorters={[
                    'status',
                    'name',
                    'mac',
                    'ip',
                    'manufacturer',
                    'cores',
                    'ht_cores',
                    'hdd',
                    'disks',
                    'ram',
                    'interfaces'
                ]}
                defaultSorting={[{status: 'asc'}]}
                filters={[
                    'status',
                    'manufacturer',
                    'cores',
                    'ht_cores',
                    'hdd',
                    'disks_amount',
                    'ram',
                    'interfaces'
                ]}
                statusesToFilter={[
                    'discover',
                    'error',
                    'offline'
                ]}
                defaultFilters={['status']}
            />;
        }
    });

    return AddNodesScreen;
});
