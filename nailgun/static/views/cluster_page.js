/*
 * Copyright 2015 Mirantis, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the 'License'); you may
 * not use this file except in compliance with the License. You may obtain
 * a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an 'AS IS' BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations
 * under the License.
**/
import $ from 'jquery';
import _ from 'underscore';
import i18n from 'i18n';
import React from 'react';
import utils from 'utils';
import models from 'models';
import dispatcher from 'dispatcher';
import {backboneMixin, pollingMixin, dispatcherMixin} from 'component_mixins';
import DashboardTab from 'views/cluster_page_tabs/dashboard_tab';
import NodesTab from 'views/cluster_page_tabs/nodes_tab';
import NetworkTab from 'views/cluster_page_tabs/network_tab';
import SettingsTab from 'views/cluster_page_tabs/settings_tab';
import LogsTab from 'views/cluster_page_tabs/logs_tab';
import HealthCheckTab from 'views/cluster_page_tabs/healthcheck_tab';
import {VmWareTab, VmWareModels} from 'plugins/vmware/vmware';

var ClusterPage = React.createClass({
  mixins: [
    pollingMixin(5),
    backboneMixin('cluster', 'change:name change:is_customized change:release'),
    backboneMixin({
      modelOrCollection: (props) => props.cluster.get('nodes')
    }),
    backboneMixin({
      modelOrCollection: (props) => props.cluster.get('tasks'),
      renderOn: 'update change'
    }),
    dispatcherMixin('networkConfigurationUpdated', 'removeFinishedNetworkTasks'),
    dispatcherMixin('deploymentTasksUpdated', 'removeFinishedDeploymentTasks'),
    dispatcherMixin('deploymentTaskStarted', function() {
      this.refreshCluster().always(this.startPolling);
    }),
    dispatcherMixin('networkVerificationTaskStarted', function() {
      this.startPolling();
    }),
    dispatcherMixin('deploymentTaskFinished', function() {
      this.refreshCluster().always(() => dispatcher.trigger('updateNotifications'));
    })
  ],
  statics: {
    navbarActiveElement: 'clusters',
    breadcrumbsPath(pageOptions) {
      // FIXME: tab breadcrumbs' data should be composed in the tab code
      var {activeTab, cluster, nodeNetworkGroups} = pageOptions;
      var subtab = pageOptions.tabOptions[0];
      var breadcrumbs = [
        ['home', '#'],
        ['environments', '#clusters'],
        [cluster.get('name'), '#cluster/' + cluster.get('id'), {skipTranslation: true}],
        [i18n('cluster_page.tabs.' + activeTab), '#cluster/' + cluster.get('id') + '/' + activeTab, {active: !subtab}]
      ];
      if (subtab) {
        var translationKey = {
          settings: 'cluster_page.settings_tab.groups.',
          network: 'cluster_page.network_tab.tabs.'
        }[activeTab] || 'cluster_page.nodes_tab.breadcrumbs.';
        var translation = i18n(translationKey + subtab, {defaultValue: subtab});
        if (activeTab === 'network' && nodeNetworkGroups.get(subtab)) {
          translation = nodeNetworkGroups.get(subtab).get('name');
        }
        breadcrumbs.push([translation, null, {active: true}]);
      }
      return breadcrumbs;
    },
    title(pageOptions) {
      return pageOptions.cluster.get('name');
    },
    getTabs() {
      return [
        {url: 'dashboard', tab: DashboardTab},
        {url: 'nodes', tab: NodesTab},
        {url: 'network', tab: NetworkTab},
        {url: 'settings', tab: SettingsTab},
        {url: 'vmware', tab: VmWareTab},
        {url: 'logs', tab: LogsTab},
        {url: 'healthcheck', tab: HealthCheckTab}
      ];
    },
    fetchData(id, activeTab, ...tabOptions) {
      var cluster, promise, currentClusterId;
      var nodeNetworkGroups = app.nodeNetworkGroups;
      var tab = _.find(this.getTabs(), {url: activeTab}).tab;
      try {
        currentClusterId = app.page.props.cluster.id;
      } catch (ignore) {}

      if (currentClusterId == id) {
        // just another tab has been chosen, do not load cluster again
        cluster = app.page.props.cluster;
        promise = tab.fetchData ? tab.fetchData({cluster: cluster, tabOptions: tabOptions}) : $.Deferred().resolve();
      } else {
        cluster = new models.Cluster({id: id});

        var settings = new models.Settings();
        settings.url = _.result(cluster, 'url') + '/attributes';
        cluster.set({settings: settings});

        var roles = new models.Roles();
        roles.url = _.result(cluster, 'url') + '/roles';
        cluster.set({roles: roles});

        var pluginLinks = new models.PluginLinks();
        pluginLinks.url = _.result(cluster, 'url') + '/plugin_links';
        cluster.set({pluginLinks: pluginLinks});

        cluster.get('nodes').fetch = function(options) {
          return this.constructor.__super__.fetch.call(this, _.extend({data: {cluster_id: id}}, options));
        };
        promise = $.when(
            cluster.fetch(),
            cluster.get('settings').fetch(),
            cluster.get('roles').fetch(),
            cluster.get('pluginLinks').fetch({cache: true}),
            cluster.fetchRelated('nodes'),
            cluster.fetchRelated('tasks'),
            nodeNetworkGroups.fetch({cache: true})
          )
          .then(() => {
            var networkConfiguration = new models.NetworkConfiguration();
            networkConfiguration.url = _.result(cluster, 'url') + '/network_configuration/' + cluster.get('net_provider');
            cluster.set({
              networkConfiguration: networkConfiguration,
              release: new models.Release({id: cluster.get('release_id')})
            });
            return $.when(cluster.get('networkConfiguration').fetch(), cluster.get('release').fetch());
          })
          .then(() => {
            var useVcenter = cluster.get('settings').get('common.use_vcenter.value');
            if (!useVcenter) {
              return true;
            }
            var vcenter = new VmWareModels.VCenter({id: id});
            cluster.set({vcenter: vcenter});
            return vcenter.fetch();
          })
          .then(() => {
            return tab.fetchData ? tab.fetchData({cluster: cluster, tabOptions: tabOptions}) : $.Deferred().resolve();
          });
      }
      return promise.then((tabData) => ({cluster, nodeNetworkGroups, activeTab, tabOptions, tabData}));
    }
  },
  getDefaultProps() {
    return {
      defaultLogLevel: 'INFO'
    };
  },
  getInitialState() {
    var tabs = this.constructor.getTabs();
    var activeSectionName = this.props.tabOptions[0];
    var subtabOptions = _.pick(this.props, 'cluster', 'nodeNetworkGroups');
    return {
      activeSettingsSectionName: this.props.activeTab === 'settings' && activeSectionName ||
        _.first(_.find(tabs, {url: 'settings'}).tab.getSubtabs(subtabOptions)),
      activeNetworkSectionName: this.props.activeTab === 'network' && activeSectionName ||
        _.first(_.find(tabs, {url: 'network'}).tab.getSubtabs(subtabOptions)),
      selectedNodeIds: {},
      selectedLogs: {type: 'local', node: null, source: 'app', level: this.props.defaultLogLevel}
    };
  },
  removeFinishedNetworkTasks(callback) {
    var request = this.removeFinishedTasks(this.props.cluster.tasks({group: 'network'}));
    if (callback) request.always(callback);
    return request;
  },
  removeFinishedDeploymentTasks() {
    return this.removeFinishedTasks(this.props.cluster.tasks({group: 'deployment'}));
  },
  removeFinishedTasks(tasks) {
    var requests = [];
    _.each(tasks, (task) => {
      if (task.match({active: false})) {
        this.props.cluster.get('tasks').remove(task);
        requests.push(task.destroy({silent: true}));
      }
    });
    return $.when(...requests);
  },
  shouldDataBeFetched() {
    return this.props.cluster.task({group: ['deployment', 'network'], active: true});
  },
  fetchData() {
    var task = this.props.cluster.task({group: 'deployment', active: true});
    if (task) {
      return task.fetch()
        .done(() => {
          if (task.match({active: false})) dispatcher.trigger('deploymentTaskFinished');
        })
        .then(() =>
          this.props.cluster.fetchRelated('nodes')
        );
    } else {
      task = this.props.cluster.task({name: 'verify_networks', active: true});
      return task ? task.fetch() : $.Deferred().resolve();
    }
  },
  refreshCluster() {
    return $.when(
      this.props.cluster.fetch(),
      this.props.cluster.fetchRelated('nodes'),
      this.props.cluster.fetchRelated('tasks'),
      this.props.cluster.get('pluginLinks').fetch()
    );
  },
  componentWillMount() {
    this.checkTabSubroute(this.props);
    this.props.cluster.on('change:release_id', () => {
      var release = new models.Release({id: this.props.cluster.get('release_id')});
      release.fetch().done(() => {
        this.props.cluster.set({release: release});
      });
    });
  },
  componentWillReceiveProps(newProps) {
    this.checkTabSubroute(newProps);
  },
  checkTabSubroute(props = {}) {
    var tab = _.find(this.constructor.getTabs(), {url: props.activeTab}).tab;
    if (tab.checkSubroute) {
      this.setState(
        tab.checkSubroute(props.tabOptions, _.pick(props, 'cluster', 'nodeNetworkGroups', 'defaultLogLevel'))
      );
    }
  },
  changeLogSelection(selectedLogs) {
    this.setState({selectedLogs: selectedLogs});
  },
  getAvailableTabs(cluster) {
    return _.filter(this.constructor.getTabs(),
      (tabData) => !tabData.tab.isVisible || tabData.tab.isVisible(cluster));
  },
  selectNodes(ids, checked) {
    if (ids && ids.length) {
      var nodeSelection = this.state.selectedNodeIds;
      _.each(ids, (id) => {
        if (checked) {
          nodeSelection[id] = true;
        } else {
          delete nodeSelection[id];
        }
      });
      this.setState({selectedNodeIds: nodeSelection});
    } else {
      this.setState({selectedNodeIds: {}});
    }
  },
  render() {
    var cluster = this.props.cluster;
    var availableTabs = this.getAvailableTabs(cluster);
    var tabUrls = _.pluck(availableTabs, 'url');
    var activeSectionNames = {
      settings: this.state.activeSettingsSectionName,
      network: this.state.activeNetworkSectionName
    };
    var tab = _.find(availableTabs, {url: this.props.activeTab});
    if (!tab) return null;
    var Tab = tab.tab;

    return (
      <div className='cluster-page' key={cluster.id}>
        <div className='page-title'>
          <h1 className='title'>
            {cluster.get('name')}
            <div className='title-node-count'>({i18n('common.node', {count: cluster.get('nodes').length})})</div>
          </h1>
        </div>
        <div className='tabs-box'>
          <div className='tabs'>
            {tabUrls.map((tabUrl) => {
              var subtabUrl = activeSectionNames[tabUrl];
              return (
                <a
                  key={tabUrl}
                  className={tabUrl + ' ' + utils.classNames({'cluster-tab': true, active: this.props.activeTab == tabUrl})}
                  href={'#cluster/' + cluster.id + '/' + tabUrl + (subtabUrl ? '/' + subtabUrl : '')}
                >
                  <div className='icon'></div>
                  <div className='label'>{i18n('cluster_page.tabs.' + tabUrl)}</div>
                </a>
              );
            })}
          </div>
        </div>
        <div key={tab.url + cluster.id} className={'content-box tab-content ' + tab.url + '-tab'}>
          <Tab
            ref='tab'
            cluster={cluster}
            nodeNetworkGroups={this.props.nodeNetworkGroups}
            tabOptions={this.props.tabOptions}
            selectNodes={this.selectNodes}
            changeLogSelection={this.changeLogSelection}
            {...this.state}
            {...this.props.tabData}
          />
        </div>
      </div>
    );
  }
});

export default ClusterPage;
