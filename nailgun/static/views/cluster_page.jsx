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
    'jsx!component_mixins',
    'jsx!views/dialogs',
    'jsx!views/cluster_page_tabs/dashboard_tab',
    'jsx!views/cluster_page_tabs/nodes_tab',
    'jsx!views/cluster_page_tabs/network_tab',
    'jsx!views/cluster_page_tabs/settings_tab',
    'jsx!views/cluster_page_tabs/logs_tab',
    'jsx!views/cluster_page_tabs/healthcheck_tab',
    'plugins/vmware/vmware'
],
function($, _, i18n, Backbone, React, utils, models, dispatcher, componentMixins, dialogs, DashboardTab, NodesTab, NetworkTab, SettingsTab, LogsTab, HealthCheckTab, vmWare) {
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
            componentMixins.dispatcherMixin('deploymentTaskStarted', function() {this.refreshCluster().always(_.bind(this.startPolling, this))}),
            componentMixins.dispatcherMixin('deploymentTaskFinished', function() {this.refreshCluster().always(_.bind(dispatcher.trigger, dispatcher, 'updateNotifications'))})
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
            fetchData: function(id, activeTab) {
                var cluster, promise, currentClusterId;
                var tab = _.find(this.getTabs(), {url: activeTab}).tab,
                    tabOptions = _.toArray(arguments).slice(2);
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

                    cluster.get('nodes').fetch = function(options) {
                        return this.constructor.__super__.fetch.call(this, _.extend({data: {cluster_id: id}}, options));
                    };
                    promise = $.when(cluster.fetch(), cluster.get('settings').fetch(), cluster.get('roles').fetch(), cluster.fetchRelated('nodes'), cluster.fetchRelated('tasks'))
                        .then(function() {
                            var networkConfiguration = new models.NetworkConfiguration();
                            networkConfiguration.url = _.result(cluster, 'url') + '/network_configuration/' + cluster.get('net_provider');
                            cluster.set({
                                networkConfiguration: networkConfiguration,
                                release: new models.Release({id: cluster.get('release_id')})
                            });
                            return $.when(cluster.get('networkConfiguration').fetch(), cluster.get('release').fetch());
                        })
                        .then(function() {
                            var useVcenter = cluster.get('settings').get('common.use_vcenter.value');
                            if (!useVcenter) {
                                return true;
                            }
                            var vcenter = new vmWare.vmWareModels.VCenter({id: id});
                            cluster.set({vcenter: vcenter});
                            return vcenter.fetch();
                        })
                        .then(function() {
                            return tab.fetchData ? tab.fetchData({cluster: cluster, tabOptions: tabOptions}) : $.Deferred().resolve();
                        });
                }
                return promise.then(function(data) {
                    return {
                        cluster: cluster,
                        activeTab: activeTab,
                        tabOptions: tabOptions,
                        tabData: data
                    };
                });
            }
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
                if (!task.match({status: 'running'})) {
                    this.props.cluster.get('tasks').remove(task);
                    requests.push(task.destroy({silent: true}));
                }
            }, this);
            return $.when.apply($, requests);
        },
        onTabLeave: function(e) {
            var href = $(e.currentTarget).attr('href');
            if (Backbone.history.getHash() != href.substr(1) && this.hasChanges()) {
                e.preventDefault();
                dialogs.DiscardSettingsChangesDialog.show({
                    verification: this.props.cluster.tasks({group: 'network', status: 'running'}).length,
                    cb: _.bind(function() {
                        this.revertChanges();
                        app.navigate(href, {trigger: true});
                    }, this)
                });
            }
        },
        shouldDataBeFetched: function() {
            return this.props.cluster.task({group: ['deployment', 'network'], status: 'running'});
        },
        fetchData: function() {
            var task = this.props.cluster.task({group: 'deployment', status: 'running'});
            if (task) {
                return task.fetch()
                    .done(_.bind(function() {
                        if (!task.match({status: 'running'})) dispatcher.trigger('deploymentTaskFinished');
                    }, this))
                    .then(_.bind(function() {
                        return this.props.cluster.fetchRelated('nodes');
                    }, this));
            } else {
                task = this.props.cluster.task('verify_networks', 'running');
                return task ? task.fetch() : $.Deferred().resolve();
            }
        },
        refreshCluster: function() {
            return $.when(this.props.cluster.fetch(), this.props.cluster.fetchRelated('nodes'), this.props.cluster.fetchRelated('tasks'));
        },
        componentWillUnmount: function() {
            $(window).off('beforeunload.' + this.eventNamespace);
            $('body').off('click.' + this.eventNamespace);
        },
        revertChanges: function() {
            this.refs.tab.revertChanges();
        },
        hasChanges: function() {
            return _.result(this.refs.tab, 'hasChanges');
        },
        onBeforeunloadEvent: function() {
            if (this.hasChanges()) return i18n('dialog.dismiss_settings.default_message');
        },
        componentWillMount: function() {
            this.props.cluster.on('change:release_id', function() {
                var release = new models.Release({id: this.props.cluster.get('release_id')});
                release.fetch().done(_.bind(function() {
                    this.props.cluster.set({release: release});
                }, this));
            }, this);
            this.eventNamespace = 'unsavedchanges' + this.props.activeTab;
            $(window).on('beforeunload.' + this.eventNamespace, _.bind(this.onBeforeunloadEvent, this));
            $('body').on('click.' + this.eventNamespace, 'a[href^=#]:not(.no-leave-check)', _.bind(this.onTabLeave, this));
        },
        getAvailableTabs: function(cluster) {
            return _.filter(this.constructor.getTabs(), function(tabData) {
                return !tabData.tab.isVisible || tabData.tab.isVisible(cluster);
            });
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
                        <Tab ref='tab' cluster={cluster} tabOptions={this.props.tabOptions} {...this.props.tabData} />
                    </div>
                </div>
            );
        }
    });

    return ClusterPage;
});
