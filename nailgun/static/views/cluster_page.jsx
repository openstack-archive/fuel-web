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

    var ClusterPage, ClusterInfo, DeploymentResult, DeploymentControl;

    ClusterPage = React.createClass({
        mixins: [
            componentMixins.pollingMixin(5),
            componentMixins.backboneMixin('cluster', 'change:is_customized change:release'),
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
                        [cluster.get('name'), '#cluster/' + cluster.get('id') + '/nodes'],
                        [i18n('cluster_page.tabs.' + pageOptions.activeTab), '#cluster/' + cluster.get('id') + '/' + pageOptions.activeTab, !addScreenBreadcrumb]
                    ];
                if (addScreenBreadcrumb) {
                    breadcrumbs.push([i18n('cluster_page.nodes_tab.breadcrumbs.' + tabOptions), null, true]);
                }
                return breadcrumbs;
            },
            title: function(pageOptions) {
                return pageOptions.cluster.get('name');
            },
            getTabs: function() {
                return [
                    {url: 'nodes', tab: NodesTab},
                    {url: 'network', tab: NetworkTab},
                    {url: 'settings', tab: SettingsTab},
                    {url: 'vmware', tab: vmWare.VmWareTab},
                    {url: 'logs', tab: LogsTab},
                    {url: 'healthcheck', tab: HealthCheckTab},
                    {url: 'actions', tab: ActionsTab}
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
                            cluster.get('roles').each(function(role) {
                                role.expandRestrictions(role.get('restrictions'));
                                role.expandLimits(role.get('limits'));
                            });
                            cluster.get('roles').processConflicts();

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
                release = cluster.get('release'),
                availableTabs = this.getAvailableTabs(cluster),
                tabUrls = _.pluck(availableTabs, 'url'),
                tab = _.find(availableTabs, {url: this.props.activeTab});
            if (!tab) return null;
            var Tab = tab.tab;

            return (
                <div className='cluster-page' key={cluster.id}>
                    <div className='row'>
                        <ClusterInfo cluster={cluster} />
                        <DeploymentControl
                            cluster={cluster}
                            hasChanges={this.hasChanges}
                            revertChanges={this.revertChanges}
                            activeTab={this.props.activeTab}
                        />
                    </div>
                    <DeploymentResult cluster={cluster} />
                    {release.get('state') == 'unavailable' &&
                        <div className='alert global-alert alert-warning'>
                            {i18n('cluster_page.unavailable_release', {name: release.get('name')})}
                        </div>
                    }
                    {cluster.get('is_customized') &&
                        <div className='alert global-alert alert-warning'>
                            {i18n('cluster_page.cluster_was_modified_from_cli')}
                        </div>
                    }
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

    ClusterInfo = React.createClass({
        mixins: [
            componentMixins.backboneMixin('cluster', 'change:name change:status')
        ],
        render: function() {
            var cluster = this.props.cluster;
            return (
                <div className='col-xs-12 col-md-9'>
                    <div className='page-title'>
                        <h1 className='title'>
                            {cluster.get('name')}
                            <div className='title-node-count'>({i18n('common.node', {count: cluster.get('nodes').length})})</div>
                        </h1>
                        <div className='cluster-info'>
                            <ul>
                                <li>
                                    <b>{i18n('cluster_page.openstack_release')}: </b>
                                    {cluster.get('release').get('name')} ({cluster.get('release').get('version')})
                                </li>
                                <li>
                                    <b>{i18n('cluster_page.deployment_mode')}: </b>
                                    {i18n('cluster.mode.' + cluster.get('mode'))}
                                </li>
                                <li>
                                    <b>{i18n('cluster_page.environment_status')}: </b>
                                    <span className={_.contains(['error', 'update_error'], cluster.get('status')) ? 'text-danger' : ''}>
                                        {i18n('cluster.status.' + cluster.get('status'))}
                                    </span>
                                </li>
                            </ul>
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
                delimited = task.escape('message').split('\n\n'),
                summary = delimited.shift(),
                details = delimited.join('\n\n'),
                classes = {
                    'alert global-alert': true,
                    'alert-danger': error,
                    'alert-success': !error
                };
            return (
                <div className={utils.classNames(classes)}>
                    <button className='close' onClick={this.dismissTaskResult}>&times;</button>
                    <strong>{i18n('common.' + (error ? 'error' : 'success'))}</strong>
                    <br />
                    <span dangerouslySetInnerHTML={{__html: utils.urlify(summary)}} />
                    {details &&
                        <div className='task-result-details'>
                            {!this.state.collapsed &&
                                <pre dangerouslySetInnerHTML={{__html: utils.urlify(details)}} />
                            }
                            <button className='btn btn-link' onClick={this.toggleCollapsed}>
                                {i18n('cluster_page.' + (this.state.collapsed ? 'show' : 'hide') + '_details_button')}
                            </button>
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
            Dialog.show({cluster: this.props.cluster});
        },
        onActionRequest: function(Dialog) {
            if (this.props.hasChanges()) {
                dialogs.DiscardSettingsChangesDialog.show({cb: _.bind(function() {
                    this.props.revertChanges();
                    if (this.props.activeTab == 'nodes') app.navigate('cluster/' + this.props.cluster.id + '/nodes', {trigger: true, replace: true});
                    this.showDialog(Dialog);
                }, this)});
            } else {
                this.showDialog(Dialog);
            }
        },
        render: function() {
            var cluster = this.props.cluster,
                nodes = cluster.get('nodes'),
                task = cluster.task({group: 'deployment', status: 'running'}),
                taskName = task ? task.get('name') : '',
                taskProgress = task && task.get('progress') || 0,
                infiniteTask = _.contains(['stop_deployment', 'reset_environment'], taskName),
                stoppableTask = !_.contains(['stop_deployment', 'reset_environment', 'update', 'spawn_vms'], taskName),
                isDeploymentImpossible = cluster.get('release').get('state') == 'unavailable' || (!cluster.get('nodes').hasChanges() && !cluster.needsRedeployment()),
                isVMsProvisioningAvailable = cluster.get('nodes').any(function(node) {
                    return node.get('pending_addition') && node.hasRole('virt');
                });
            return (
                <div className='col-xs-6 col-md-3'>
                    <div className='deploy-box pull-right'>
                        {task ? (
                            <div className={'deploy-process ' + taskName} key={taskName}>
                                <div className='progress'>
                                    <div
                                        className={utils.classNames({
                                            'progress-bar progress-bar-striped active': true,
                                            'progress-bar-warning': infiniteTask,
                                            'progress-bar-success': !infiniteTask
                                        })}
                                        style={{width: (infiniteTask ? 100 : taskProgress > 3 ? taskProgress : 3) + '%'}}
                                    >
                                        {i18n('cluster_page.' + taskName, {defaultValue: ''})}
                                    </div>
                                </div>
                                {stoppableTask &&
                                    <button
                                        className='btn btn-danger btn-xs pull-right stop-deployment-btn'
                                        title={i18n('cluster_page.stop_deployment_button')}
                                        onClick={_.partial(this.showDialog, dialogs.StopDeploymentDialog)}
                                    ><i className='glyphicon glyphicon-remove'></i></button>
                                }
                                {!infiniteTask &&
                                    <div className='deploy-percents pull-right'>{taskProgress + '%'}</div>
                                }
                            </div>
                        ) : [
                            nodes.hasChanges() && (
                                <button
                                    key='discard-changes'
                                    className='btn btn-transparent'
                                    title={i18n('cluster_page.discard_changes')}
                                    onClick={_.partial(this.showDialog, dialogs.DiscardNodeChangesDialog)}
                                >
                                    <div className='discard-changes-icon'></div>
                                </button>
                            ),
                            isVMsProvisioningAvailable ?
                                <button
                                    key='provision-vms'
                                    className='btn btn-primary deploy-btn'
                                    onClick={_.partial(this.onActionRequest, dialogs.ProvisionVMsDialog)}
                                >
                                    <div className='deploy-icon'></div>
                                    {i18n('cluster_page.provision_vms')}
                                </button>
                            :
                                <button
                                    key='deploy-changes'
                                    className='btn btn-primary deploy-btn'
                                    disabled={isDeploymentImpossible}
                                    onClick={_.partial(this.onActionRequest, dialogs.DeployChangesDialog)}
                                >
                                    <div className='deploy-icon'></div>
                                    {i18n('cluster_page.deploy_changes')}
                                </button>
                        ]}
                    </div>
                </div>
            );
        }
    });

    return ClusterPage;
});
