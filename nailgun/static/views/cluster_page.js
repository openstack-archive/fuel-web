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
import componentMixins from 'component_mixins';
import DashboardTab from 'views/cluster_page_tabs/dashboard_tab';
import NodesTab from 'views/cluster_page_tabs/nodes_tab';
import NetworkTab from 'views/cluster_page_tabs/network_tab';
import SettingsTab from 'views/cluster_page_tabs/settings_tab';
import LogsTab from 'views/cluster_page_tabs/logs_tab';
import HealthCheckTab from 'views/cluster_page_tabs/healthcheck_tab';
import {VmWareTab, VmWareModels} from 'plugins/vmware/vmware';

    var ClusterPage = React.createClass({
        mixins: [
            componentMixins.pollingMixin(5),
            componentMixins.backboneMixin('cluster', 'change:name change:is_customized change:release'),
            componentMixins.backboneMixin({
                modelOrCollection(props) {return props.cluster.get('nodes');}
            }),
            componentMixins.backboneMixin({
                modelOrCollection(props) {return props.cluster.get('tasks');},
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
            breadcrumbsPath(pageOptions) {
                var cluster = pageOptions.cluster,
                    subtab = pageOptions.tabOptions[0],
                    breadcrumbs = [
                        ['home', '#'],
                        ['environments', '#clusters'],
                        [cluster.get('name'), '#cluster/' + cluster.get('id'), {skipTranslation: true}],
                        [i18n('cluster_page.tabs.' + pageOptions.activeTab), '#cluster/' + cluster.get('id') + '/' + pageOptions.activeTab, {active: !subtab}]
                    ];
                if (subtab) {
                    var translationKey = {
                            settings: 'cluster_page.settings_tab.groups.',
                            network: 'cluster_page.network_tab.tabs.'
                        }[pageOptions.activeTab] || 'cluster_page.nodes_tab.breadcrumbs.';
                    breadcrumbs.push([i18n(translationKey + subtab, {defaultValue: subtab}), null, {active: true}]);
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
                return promise.then((data) => {
                    return {
                        cluster: cluster,
                        nodeNetworkGroups: nodeNetworkGroups,
                        activeTab: activeTab,
                        tabOptions: tabOptions,
                        tabData: data
                    };
                });
            }
        },
        getDefaultProps() {
            return {
                defaultLogLevel: 'INFO'
            };
        },
        getInitialState() {
            return {
                activeSettingsSectionName: this.props.activeTab == 'settings' && this.props.tabOptions[0] || _.first(this.props.cluster.get('settings').getGroupList()),
                activeNetworkSectionName: this.props.activeTab == 'network' && this.props.tabOptions[0] || this.props.nodeNetworkGroups.find({is_default: true}).get('name'),
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
            _.each(tasks, function(task) {
                if (task.match({active: false})) {
                    this.props.cluster.get('tasks').remove(task);
                    requests.push(task.destroy({silent: true}));
                }
            }, this);
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
            this.checkSubtab(this.props);

            this.props.cluster.on('change:release_id', function() {
                var release = new models.Release({id: this.props.cluster.get('release_id')});
                release.fetch().done(() => {
                    this.props.cluster.set({release: release});
                });
            }, this);
            this.updateLogSettings();
        },
        checkSubtab(props) {
            var networkSettingSections = [];
            if (this.props.cluster.get('net_provider') == 'nova_network') {
                networkSettingSections.push('nova_configuration');
            } else {
                networkSettingSections = networkSettingSections.concat(['neutron_l2', 'neutron_l3']);
            }
            networkSettingSections.push('network_settings');

            var subtabs = {
                    settings: props.cluster.get('settings').getGroupList(),
                    network: _.union(props.nodeNetworkGroups.pluck('name'), networkSettingSections, ['network_verification'])
                },
            subtab = props.tabOptions[0];
            if (subtabs[props.activeTab] && (!subtab || !_.contains(subtabs[props.activeTab], subtab))) {
                var defaultSubtab = {
                        settings: subtabs.settings[0],
                        network: props.nodeNetworkGroups.find({is_default: true}).get('name')
                    }[props.activeTab];
                app.navigate('cluster/' + props.cluster.id + '/' + props.activeTab + '/' + defaultSubtab, {trigger: true, replace: true});
            }
        },
        componentWillReceiveProps(newProps) {
            this.updateLogSettings(newProps);
            if (newProps.activeTab == 'settings') {
                this.checkSubtab(newProps);
                this.setState({activeSettingsSectionName: newProps.tabOptions[0]});
            }
            if (newProps.activeTab == 'network') {
                this.checkSubtab(newProps);
                this.setState({activeNetworkSectionName: newProps.tabOptions[0]});
            }
        },
        updateLogSettings(props) {
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
            var cluster = this.props.cluster,
                availableTabs = this.getAvailableTabs(cluster),
                tabUrls = _.pluck(availableTabs, 'url'),
                subtabs = {
                    settings: this.state.activeSettingsSectionName,
                    network: this.state.activeNetworkSectionName
                },
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
                            {tabUrls.map(
                                (url) => <a
                                    key={url}
                                    className={url + ' ' + utils.classNames({'cluster-tab': true, active: this.props.activeTab == url})}
                                    href={'#cluster/' + cluster.id + '/' + url + (subtabs[url] ? '/' + subtabs[url] : '')}
                                >
                                    <div className='icon'></div>
                                    <div className='label'>{i18n('cluster_page.tabs.' + url)}</div>
                                </a>
                            )}
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
