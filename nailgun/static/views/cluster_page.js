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
define(
[
    'jquery',
    'underscore',
    'i18n',
    'backbone',
    'react',
    'utils',
    'models',
    'dispatcher',
    'component_mixins',
    'views/dialogs',
    'views/cluster_page_tabs/dashboard_tab',
    'views/cluster_page_tabs/nodes_tab',
    'views/cluster_page_tabs/network_tab',
    'views/cluster_page_tabs/settings_tab',
    'views/cluster_page_tabs/logs_tab',
    'views/cluster_page_tabs/healthcheck_tab',
    'plugins/vmware/vmware'
],
($, _, i18n, Backbone, React, utils, models, dispatcher, componentMixins, dialogs, DashboardTab, NodesTab, NetworkTab, SettingsTab, LogsTab, HealthCheckTab, vmWare) => {
    'use strict';

    var ClusterPage = React.createClass({
        mixins: [
            componentMixins.pollingMixin(5),
            componentMixins.backboneMixin('cluster', 'change:name change:is_customized change:release'),
            componentMixins.backboneMixin({
                modelOrCollection: function(props) {return props.cluster.get('nodes');}
            }),
            componentMixins.backboneMixin({
                modelOrCollection: function(props) {return props.cluster.get('tasks');},
                renderOn: 'update change'
            }),
            componentMixins.dispatcherMixin('networkConfigurationUpdated', 'removeFinishedNetworkTasks'),
            componentMixins.dispatcherMixin('deploymentTasksUpdated', 'removeFinishedDeploymentTasks'),
            componentMixins.dispatcherMixin('deploymentTaskStarted', function() {
                this.refreshCluster().always(this.startPolling);
            }),
            componentMixins.dispatcherMixin('networkVerificationTaskStarted', function() {
                this.startPolling();
            }),
            componentMixins.dispatcherMixin('deploymentTaskFinished', function() {
                this.refreshCluster().always(() => dispatcher.trigger('updateNotifications'));
            })
        ],
        statics: {
            navbarActiveElement: 'clusters',
            breadcrumbsPath: function(pageOptions) {
                var cluster = pageOptions.cluster,
                    tabOptions = pageOptions.tabOptions[0],
                    addScreenBreadcrumb = tabOptions && tabOptions.match(/^(?!list$)\w+$/),
                    breadcrumbs = [
                        ['home', '#'],
                        ['environments', '#clusters'],
                        [cluster.get('name'), '#cluster/' + cluster.get('id'), {skipTranslation: true}],
                        [i18n('cluster_page.tabs.' + pageOptions.activeTab), '#cluster/' + cluster.get('id') + '/' + pageOptions.activeTab, {active: !addScreenBreadcrumb}]
                    ];
                if (addScreenBreadcrumb) {
                    breadcrumbs.push([i18n('cluster_page.nodes_tab.breadcrumbs.' + tabOptions), null, {active: true}]);
                }
                return breadcrumbs;
            },
            title: function(pageOptions) {
                return pageOptions.cluster.get('name');
            },
            getTabs: function() {
                return [
                    {url: 'dashboard', tab: DashboardTab},
                    {url: 'nodes', tab: NodesTab},
                    {url: 'network', tab: NetworkTab},
                    {url: 'settings', tab: SettingsTab},
                    {url: 'vmware', tab: vmWare.VmWareTab},
                    {url: 'logs', tab: LogsTab},
                    {url: 'healthcheck', tab: HealthCheckTab}
                ];
            },
            fetchData: function(id, activeTab, ...tabOptions) {
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
                            var vcenter = new vmWare.vmWareModels.VCenter({id: id});
                            cluster.set({vcenter: vcenter});
                            return vcenter.fetch();
                        })
                        .then(() => {
                            return tab.fetchData ? tab.fetchData({cluster: cluster, tabOptions: tabOptions}) : $.Deferred().resolve();
                        });
                }
                return promise.then((data) =>
                    ({
                        cluster: cluster,
                        nodeNetworkGroups: nodeNetworkGroups,
                        activeTab: activeTab,
                        tabOptions: tabOptions,
                        tabData: data
                    })
                );
            }
        },
        getDefaultProps: function() {
            return {
                defaultLogLevel: 'INFO'
            };
        },
        getInitialState: function() {
            return {
                activeSettingsSectionName: this.pickDefaultSettingGroup(),
                activeNetworkSectionName: this.props.nodeNetworkGroups.find({is_default: true}).get('name'),
                selectedNodeIds: {},
                selectedLogs: {type: 'local', node: null, source: 'app', level: this.props.defaultLogLevel}
            };
        },
        removeFinishedNetworkTasks: function(callback) {
            var request = this.removeFinishedTasks(this.props.cluster.tasks({group: 'network'}));
            if (callback) request.always(callback);
            return request;
        },
        removeFinishedDeploymentTasks: function() {
            return this.removeFinishedTasks(this.props.cluster.tasks({group: 'deployment'}));
        },
        removeFinishedTasks: function(tasks) {
            var requests = [];
            _.each(tasks, function(task) {
                if (task.match({active: false})) {
                    this.props.cluster.get('tasks').remove(task);
                    requests.push(task.destroy({silent: true}));
                }
            }, this);
            return $.when(...requests);
        },
        shouldDataBeFetched: function() {
            return this.props.cluster.task({group: ['deployment', 'network'], active: true});
        },
        fetchData: function() {
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
        refreshCluster: function() {
            return $.when(
                this.props.cluster.fetch(),
                this.props.cluster.fetchRelated('nodes'),
                this.props.cluster.fetchRelated('tasks'),
                this.props.cluster.get('pluginLinks').fetch()
            );
        },
        componentWillMount: function() {
            this.props.cluster.on('change:release_id', function() {
                var release = new models.Release({id: this.props.cluster.get('release_id')});
                release.fetch().done(() => {
                    this.props.cluster.set({release: release});
                });
            }, this);
            this.updateLogSettings();
        },
        componentWillReceiveProps: function(newProps) {
            this.updateLogSettings(newProps);
        },
        updateLogSettings: function(props) {
            props = props || this.props;
            // FIXME: the following logs-related logic should be moved to Logs tab code
            // to keep parent component tightly coupled to its children
            if (props.activeTab == 'logs') {
                var selectedLogs;
                if (props.tabOptions[0]) {
                    selectedLogs = utils.deserializeTabOptions(_.compact(props.tabOptions).join('/'));
                    selectedLogs.level = selectedLogs.level ? selectedLogs.level.toUpperCase() : props.defaultLogLevel;
                    this.setState({selectedLogs: selectedLogs});
                }
            }
        },
        changeLogSelection: function(selectedLogs) {
            this.setState({selectedLogs: selectedLogs});
        },
        getAvailableTabs: function(cluster) {
            return _.filter(this.constructor.getTabs(), (tabData) =>
                !tabData.tab.isVisible || tabData.tab.isVisible(cluster)
            );
        },
        pickDefaultSettingGroup: function() {
            return _.first(this.props.cluster.get('settings').getGroupList());
        },
        setActiveSettingsGroupName: function(value) {
            if (_.isUndefined(value)) value = this.pickDefaultSettingGroup();
            this.setState({activeSettingsSectionName: value});
        },

        setActiveNetworkSectionName: function(name) {
            this.setState({activeNetworkSectionName: name});
        },
        selectNodes: function(ids, checked) {
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
        render: function() {
            var cluster = this.props.cluster,
                availableTabs = this.getAvailableTabs(cluster),
                tabUrls = _.pluck(availableTabs, 'url'),
                tab = _.find(availableTabs, {url: this.props.activeTab});
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
                            {tabUrls.map(function(url) {
                                return (
                                    <a
                                        key={url}
                                        className={url + ' ' + utils.classNames({'cluster-tab': true, active: this.props.activeTab == url})}
                                        href={'#cluster/' + cluster.id + '/' + url}
                                    >
                                        <div className='icon'></div>
                                        <div className='label'>{i18n('cluster_page.tabs.' + url)}</div>
                                    </a>
                                );
                            }, this)}
                        </div>
                    </div>
                    <div key={tab.url + cluster.id} className={'content-box tab-content ' + tab.url + '-tab'}>
                        <Tab
                            ref='tab'
                            cluster={cluster}
                            nodeNetworkGroups={this.props.nodeNetworkGroups}
                            tabOptions={this.props.tabOptions}
                            setActiveSettingsGroupName={this.setActiveSettingsGroupName}
                            setActiveNetworkSectionName={this.setActiveNetworkSectionName}
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

    return ClusterPage;
});
