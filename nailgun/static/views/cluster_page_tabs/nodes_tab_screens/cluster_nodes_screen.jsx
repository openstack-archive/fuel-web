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
    'react',
    'jsx!views/cluster_page_tabs/nodes_tab_screens/node_list_screen'
],
function(React, NodeListScreen) {
    'use strict';

    var ClusterNodesScreen = React.createClass({
        render: function() {
            return <NodeListScreen
                ref='screen'
                mode='list'
                cluster={this.props.cluster}
                nodes={this.props.cluster.get('nodes')}
                sorters={[
                    'roles',
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
                defaultSorting={[{roles: 'asc'}]}
                filters={[
                    'roles',
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
                    'ready',
                    'pending_addition',
                    'pending_deletion',
                    'provisioned',
                    'provisioning',
                    'deploying',
                    'error',
                    'offline',
                    'removing'
                ]}
                defaultFilters={['roles', 'status']}
            />;
        }
    });

    return ClusterNodesScreen;
});
