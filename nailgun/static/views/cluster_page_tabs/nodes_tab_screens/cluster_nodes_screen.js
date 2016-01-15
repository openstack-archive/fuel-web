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
import _ from 'underscore';
import React from 'react';
import models from 'models';
import NodeListScreen from 'views/cluster_page_tabs/nodes_tab_screens/node_list_screen';

var ClusterNodesScreen = React.createClass({
  render() {
    return <NodeListScreen {... _.omit(this.props, 'screenOptions')}
      ref='screen'
      mode='list'
      nodes={this.props.cluster.get('nodes')}
      roles={this.props.cluster.get('roles')}
      sorters={_.without(models.Nodes.prototype.sorters, 'cluster')}
      defaultSorting={[{roles: 'asc'}]}
      filters={_.without(models.Nodes.prototype.filters, 'cluster')}
      statusesToFilter={_.without(models.Node.prototype.statuses, 'discover')}
      defaultFilters={{roles: [], status: []}}
    />;
  }
});

export default ClusterNodesScreen;
