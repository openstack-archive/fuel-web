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
    'jsx!views/cluster_page_tabs/nodes_tab',
    'jsx!views/cluster_page_tabs/network_tab',
    'jsx!views/cluster_page_tabs/settings_tab',
    'jsx!views/cluster_page_tabs/logs_tab',
    'jsx!views/cluster_page_tabs/actions_tab',
    'jsx!views/cluster_page_tabs/healthcheck_tab',
    'plugins/vmware/vmware'
],
function($, _, i18n, Backbone, React, utils, models, dispatcher, componentMixins, dialogs, NodesTab, NetworkTab, SettingsTab, LogsTab, ActionsTab, HealthCheckTab, vmWare) {
    'use strict';

    var ClusterPage, ClusterInfo, DeploymentResult, DeploymentControl,
        cs = React.addons.classSet;

    ClusterPage = React.createClass({
        mixins: [
            componentMixins.pollingMixin(5),
            componentMixins.backboneMixin('cluster', 'change:is_customized change:release'),
            componentMixins.backboneMixin({
                modelOrCollection: function(props) {return props.cluster.get('nodes');}
            }),
            componentMixins.backboneMixin({
                modelOrCollection: function(props) {return props.cluster.get('tasks');},
                renderOn: 'add remove change'
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
                    breadcrumbs = [
                        ['home', '#'],
                        ['environments', '#clusters'],
                        [cluster.get('name'), '#cluster/' + cluster.get('id') + '/nodes'],
                        [i18n('cluster_page.tabs.' + pageOptions.activeTab), '#cluster/' + cluster.get('id') + '/' + pageOptions.activeTab, !pageOptions.tabOptions[0]]
                    ];
                if (pageOptions.tabOptions[0]) breadcrumbs.push([i18n('cluster_page.nodes_tab.breadcrumbs.' + pageOptions.tabOptions[0]), null, true]);
                return breadcrumbs;
            },
            title: function(pageOptions) {
                return pageOptions.cluster.get('name');
            },
            fetchData: function(id, activeTab) {
                var cluster, promise, currentClusterId;
                var tabOptions = _.toArray(arguments).slice(2);
                try {
                    currentClusterId = app.page.props.cluster.id;
                } catch (ignore) {}

                if (currentClusterId == id) {
                    // just another tab has been chosen, do not load cluster again
                    cluster = app.page.props.cluster;
                    promise = $.Deferred().resolve();
                } else {
                    cluster = new models.Cluster({id: id});
                    var settings = new models.Settings();
                    settings.url = _.result(cluster, 'url') + '/attributes';
                    cluster.set({settings: settings});
                    promise = $.when(cluster.fetch(), cluster.get('settings').fetch(), cluster.fetchRelated('nodes'), cluster.fetchRelated('tasks'))
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
                        });
                }
                return promise.then(function() {
                    return {
                        cluster: cluster,
                        activeTab: activeTab,
                        tabOptions: tabOptions
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
                utils.showDialog(dialogs.DiscardSettingsChangesDialog, {
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
        getAvailableTabs: function() {
            var tabs = [
                {url: 'nodes', tab: NodesTab},
                {url: 'network', tab: NetworkTab},
                {url: 'settings', tab: SettingsTab},
                {url: 'logs', tab: LogsTab},
                {url: 'healthcheck', tab: HealthCheckTab},
                {url: 'actions', tab: ActionsTab}
            ];
            var settings = this.props.cluster.get('settings'),
                useVCenter = settings.get('common.use_vcenter').value,
                index = _.findIndex(tabs, {url: 'settings'});
            if (useVCenter) {
                tabs.splice(index + 1, 0, {url: 'vmware', tab: vmWare.VmWareTab});
            }
            return tabs;
        },
        checkTab: function(props) {
            props = props || this.props;
            var availableTabs = this.getAvailableTabs();
            if (!_.find(availableTabs, {url: props.activeTab})) {
                app.navigate('cluster/' + props.cluster.id + '/' + availableTabs[0].url, {trigger: true, replace: true});
                return;
            }
        },
        componentWillUpdate: function(nextProps) {
            this.checkTab(nextProps);
        },
        componentWillMount: function() {
            this.checkTab();
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
        render: function() {
            var cluster = this.props.cluster,
                release = cluster.get('release'),
                availableTabs = this.getAvailableTabs(),
                tabs = _.pluck(availableTabs, 'url'),
                tabObject = _.find(availableTabs, {url: this.props.activeTab});
            if (!tabObject) return null;
            var TabConstructor = tabObject.tab,
                tab = <TabConstructor ref='tab' cluster={cluster} tabOptions={this.props.tabOptions} />;
            return (
                <div>
                    <ClusterInfo cluster={cluster} />
                    <DeploymentResult cluster={cluster} />
                    {release.get('state') == 'unavailable' &&
                        <div className='alert alert-block globalalert'>
                            <p className='enable-selection'>{i18n('cluster_page.unavailable_release', {name: release.get('name')})}</p>
                        </div>
                    }
                    {cluster.get('is_customized') &&
                        <div className='alert alert-block globalalert'>
                            <p className='enable-selection'>{i18n('cluster_page.cluster_was_modified_from_cli')}</p>
                        </div>
                    }
                    <div className='whitebox'>
                        <ul className='nav nav-tabs cluster-tabs'>
                            {tabs.map(function(url) {
                                return <li key={url} className={cs({active: this.props.activeTab == url})}>
                                    <a href={'#cluster/' + cluster.id + '/' + url}>
                                        <b className={'tab-' + url + '-normal'} />
                                        <div className='tab-title'>{i18n('cluster_page.tabs.' + url)}</div>
                                    </a>
                                </li>;
                            }, this)}
                            <DeploymentControl
                                cluster={cluster}
                                hasChanges={this.hasChanges}
                                revertChanges={this.revertChanges}
                                activeTab={this.props.activeTab}
                            />
                        </ul>
                        <div className='tab-content'>
                            {tabs.map(function(url) {
                                return <div key={url} className={cs({'tab-pane': true, active: this.props.activeTab == url})} id={'tab-' + url}>
                                    {this.props.activeTab == url && tab}
                                </div>;
                            }, this)}
                        </div>
                    </div>
                </div>
            );
        }
    });

    ClusterInfo = React.createClass({
        mixins: [
            componentMixins.backboneMixin('cluster', 'change:name change:status')
        ],
        render: function() {
            var cluster = this.props.cluster;
            return (
                <div className='container'>
                    <div className='cluster-name-box'>
                        <div className='cluster-name-placeholder'>
                            <div className='name-box'>
                                <h3 className='name page-title'>{cluster.get('name')}</h3>
                                <div className='node-list-name-count'>({i18n('common.node', {count: cluster.get('nodes').length})})</div>
                                <div className='clearfix'/>
                            </div>
                        </div>
                        <div className='cluster-summary-placeholder'>
                            <div>
                                <span>{i18n('cluster_page.openstack_release')}: </span>
                                {cluster.get('release').get('name')} ({cluster.get('release').get('version')})
                            </div>
                            <div>
                                <span>{i18n('cluster_page.deployment_mode')}: </span>
                                {i18n('cluster.mode.' + cluster.get('mode'))}
                            </div>
                            <div className={_.contains(['error', 'update_error'], cluster.get('status')) ? 'error' : ''}>
                                <span>{i18n('cluster_page.environment_status')}: </span>
                                {i18n('cluster.status.' + cluster.get('status'))}
                            </div>
                        </div>
                    </div>
                </div>
            );
        }
    });

    DeploymentResult = React.createClass({
        getInitialState: function() {
            return {collapsed: true};
        },
        dismissTaskResult: function() {
            var task = this.props.cluster.task({group: 'deployment'});
            if (task) task.destroy();
        },
        toggleCollapsed: function() {
            this.setState({collapsed: !this.state.collapsed});
        },
        render: function() {
            var task = this.props.cluster.task({group: 'deployment', status: ['ready', 'error']});
            if (!task) return null;
            var error = task.match({status: 'error'}),
                deploymentOrUpdate = task.match({name: ['deploy', 'update']}),
                delimited = task.escape('message').split('\n\n'),
                summary = delimited.shift(),
                details = delimited.join('\n\n'),
                classes = {
                    'alert alert-block': true,
                    'alert-error global-error': error,
                    'alert-success': !error,
                    'global-success': !error && deploymentOrUpdate,
                    globalalert: !deploymentOrUpdate
                };
            return (
                <div className='deployment-result'>
                    {task &&
                        <div className={cs(classes)}>
                            <button className='close' onClick={this.dismissTaskResult}>&times;</button>
                            <h4>{i18n('common.' + (error ? 'error' : 'success'))}</h4>
                            <span className='enable-selection' dangerouslySetInnerHTML={{__html: utils.urlify(summary)}} />
                            {details &&
                                <span>
                                    {!this.state.collapsed &&
                                        <pre className='enable-selection' dangerouslySetInnerHTML={{__html: utils.urlify(details)}} />
                                    }
                                    <button className='btn-link' onClick={this.toggleCollapsed}>
                                        {i18n('cluster_page.' + (this.state.collapsed ? 'show' : 'hide') + '_details_button')}
                                    </button>
                                </span>
                            }
                        </div>
                    }
                </div>
            );
        }
    });

    DeploymentControl = React.createClass({
        mixins: [
            componentMixins.backboneMixin({
                modelOrCollection: function(props) {return props.cluster.get('nodes');},
                renderOn: 'change:pending_addition change:pending_deletion'
            })
        ],
        showDialog: function(Dialog) {
            utils.showDialog(Dialog, {cluster: this.props.cluster});
        },
        onDeployRequest: function() {
            if (this.props.hasChanges()) {
                utils.showDialog(dialogs.DiscardSettingsChangesDialog, {cb: _.bind(function() {
                    this.props.revertChanges();
                    if (this.props.activeTab == 'nodes') app.navigate('cluster/' + this.props.cluster.id + '/nodes', {trigger: true, replace: true});
                    this.showDialog(dialogs.DeployChangesDialog);
                }, this)});
            } else {
                this.showDialog(dialogs.DeployChangesDialog);
            }
        },
        render: function() {
            var cluster = this.props.cluster,
                nodes = cluster.get('nodes'),
                task = cluster.task({group: 'deployment', status: 'running'}),
                taskName = task ? task.get('name') : '',
                taskProgress = task && task.get('progress') || 0,
                infiniteTask = _.contains(['stop_deployment', 'reset_environment'], taskName),
                itemClass = 'deployment-control-item-box',
                isDeploymentImpossible = cluster.get('release').get('state') == 'unavailable' || (!cluster.get('nodes').hasChanges() && !cluster.needsRedeployment());
            return (
                <div className='cluster-deploy-placeholder'>
                    {task ? (
                        <div className={'pull-right deployment-progress-box ' + taskName}>
                            {!infiniteTask &&
                                <div>
                                    {taskName != 'update' &&
                                        <div className={itemClass}>
                                            <button
                                                className='btn btn-danger stop-deployment-btn'
                                                title={i18n('cluster_page.stop_deployment_button')}
                                                onClick={_.bind(this.showDialog, this, dialogs.StopDeploymentDialog)}
                                            >
                                                <i className='icon-cancel-circle' />
                                            </button>
                                        </div>
                                    }
                                    <div className={itemClass}>
                                        <div className='deploying-progress-text-box percentage'>{taskProgress + '%'}</div>
                                    </div>
                                </div>
                            }
                            <div className={itemClass}>
                                <div className={'progress progress-striped active progress-' + (infiniteTask ? 'warning' : 'success')}>
                                    <div className='bar' style={{width: (taskProgress > 3 ? taskProgress : 3) + '%'}} />
                                </div>
                            </div>
                            <div className='progress-bar-description'>{i18n('cluster_page.' + taskName, {defaultValue: ''})}</div>
                        </div>
                    ) : (
                        <div className='pull-right deployment-control-box'>
                            <div className={itemClass}>
                                <button
                                    className='deploy-btn'
                                    disabled={isDeploymentImpossible}
                                    onClick={this.onDeployRequest}
                                >
                                    <i className='icon-upload-cloud' />
                                    {i18n('cluster_page.deploy_changes')}
                                </button>
                            </div>
                            {nodes.hasChanges() &&
                                <div className={itemClass}>
                                    <button
                                        className='btn rollback'
                                        title={i18n('cluster_page.discard_changes')}
                                        onClick={_.bind(this.showDialog, this, dialogs.DiscardNodeChangesDialog)}
                                    >
                                        <i className='icon-back-in-time' />
                                    </button>
                                </div>
                            }
                        </div>
                    )}
                </div>
            );
        }
    });

    return ClusterPage;
});
