/*
 * Copyright 2015 Mirantis, Inc.
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

import $ from 'jquery';
import _ from 'underscore';
import i18n from 'i18n';
import React from 'react';
import models from 'models';
import {backboneMixin} from 'component_mixins';
import NodeListScreen from 'views/cluster_page_tabs/nodes_tab_screens/node_list_screen';

var EquipmentPage, PluginLinks;

EquipmentPage = React.createClass({
  mixins: [backboneMixin('nodes')],
  statics: {
    title: i18n('equipment_page.title'),
    navbarActiveElement: 'equipment',
    breadcrumbsPath: [['home', '#'], 'equipment'],
    fetchData() {
      var nodes = new models.Nodes();
      var clusters = new models.Clusters();
      var plugins = new models.Plugins();
      var nodeNetworkGroups = new models.NodeNetworkGroups();
      var {releases, fuelSettings} = app;
      return $.when(
        nodes.fetch(),
        clusters.fetch(),
        nodeNetworkGroups.fetch(),
        releases.fetch({cache: true}),
        fuelSettings.fetch({cache: true}),
        plugins.fetch()
      ).then(() => {
        clusters.each(
          (cluster) => cluster.set({
            release: releases.get(cluster.get('release_id'))
          })
        );
        var requests = clusters.map((cluster) => {
          var roles = new models.Roles();
          roles.url = _.result(cluster, 'url') + '/roles';
          cluster.set({roles: roles});
          return roles.fetch();
        });
        requests = requests.concat(
          plugins
            .filter((plugin) => _.contains(plugin.get('groups'), 'equipment'))
            .map((plugin) => {
              var pluginLinks = new models.PluginLinks();
              pluginLinks.url = _.result(plugin, 'url') + '/links';
              plugin.set({links: pluginLinks});
              return pluginLinks.fetch();
            })
        );
        return $.when(...requests);
      })
      .then(() => {
        var links = new models.PluginLinks();
        plugins.each(
          (plugin) => links.add(plugin.get('links') && plugin.get('links').models)
        );

        return {nodes, clusters, nodeNetworkGroups, fuelSettings, links};
      });
    }
  },
  getInitialState() {
    return {
      selectedNodeIds: []
    };
  },
  selectNodes(ids = [], checked = false) {
    var nodeSelection = {};
    if (ids.length) {
      nodeSelection = this.state.selectedNodeIds;
      _.each(ids, (id) => {
        if (checked) {
          nodeSelection[id] = true;
        } else {
          delete nodeSelection[id];
        }
      });
    }
    this.setState({selectedNodeIds: nodeSelection});
  },
  render() {
    var roles = new models.Roles();
    this.props.clusters.each((cluster) => {
      roles.add(
        cluster.get('roles').filter((role) => !roles.findWhere({name: role.get('name')}))
      );
    });
    return (
      <div className='equipment-page'>
        <div className='page-title'>
          <h1 className='title'>{i18n('equipment_page.title')}</h1>
        </div>
        <div className='content-box'>
          <PluginLinks links={this.props.links} />
          <NodeListScreen {...this.props}
            ref='screen'
            selectedNodeIds={this.state.selectedNodeIds}
            selectNodes={this.selectNodes}
            roles={roles}
            sorters={models.Nodes.prototype.sorters}
            defaultSorting={[{status: 'asc'}]}
            filters={models.Nodes.prototype.filters}
            statusesToFilter={models.Node.prototype.statuses}
            defaultFilters={{status: []}}
            showBatchActionButtons={false}
          />
        </div>
      </div>
    );
  }
});

PluginLinks = React.createClass({
  render() {
    if (!this.props.links.length) return null;
    return (
      <div className='row'>
        <div className='plugin-links-block clearfix'>
          {this.props.links.map((link, index) =>
            <div className='link-block col-xs-12' key={index}>
              <div className='title'>
                <a href={link.get('url')} target='_blank'>{link.get('title')}</a>
              </div>
              <div className='description'>{link.get('description')}</div>
            </div>
          )}
        </div>
      </div>
    );
  }
});

export default EquipmentPage;
