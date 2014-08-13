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
    'utils',
    'models',
    'jsx!component_mixins',
    'jsx!views/dialogs',
    'views/cluster_page_tabs/nodes_tab',
    'views/cluster_page_tabs/network_tab',
    'views/cluster_page_tabs/settings_tab',
    'views/cluster_page_tabs/logs_tab',
    'views/cluster_page_tabs/actions_tab',
    'views/cluster_page_tabs/healthcheck_tab'
],
function(React, utils, models, componentMixins, dialogs, NodesTab, NetworkTab, SettingsTab, LogsTab, ActionsTab, HealthCheckTab) {
    'use strict';

    var ClusterPage = React.createClass({
        mixins: [
            React.BackboneMixin('cluster'),
            componentMixins.pollingMixin(5)
        ],
        navbarActiveElement: 'clusters',
        breadcrumbsPath: function() {
            return [['home', '#'], ['environments', '#clusters'], [this.props.cluster.get('name'), null, true]];
        },
        title: function() {
            return this.props.cluster.get('name');
        },
        tabs: ['nodes', 'network', 'settings', 'logs', 'healthcheck', 'actions'],
        removeFinishedNetworkTasks: function(removeSilently) {
            return this.removeFinishedTasks(this.props.cluster.tasks({group: 'network'}), removeSilently);
        },
        removeFinishedDeploymentTasks: function(removeSilently) {
            return this.removeFinishedTasks(this.props.cluster.tasks({group: 'deployment'}), removeSilently);
        },
        removeFinishedTasks: function(tasks, removeSilently) {
            var requests = [];
            _.each(tasks, function(task) {
                if (!task.match({status: 'running'})) {
                    if (!removeSilently) {
                        this.props.cluster.get('tasks').remove(task);
                    }
                    requests.push(task.destroy({silent: true}));
                }
            }, this);
            return $.when.apply($, requests);
        },
        discardSettingsChanges: function(options) {
            (new dialogs.DiscardSettingsChangesDialog(options)).render();
        },
        shouldDataBeFetched: function() {
            return this.props.cluster.task({group: ['deployment', 'network'], status: 'running'});
        },
        fetchData: function() {
            var cluster = this.props.cluster;
            var task = cluster.task({group: 'deployment', status: 'running'});
            if (task) {
                var deferred = task.fetch();
                deferred.done(_.bind(function() {
                    if (!task.match({status: 'running'})) {
                        this.deploymentTaskFinished();
                    }
                }, this));
                return $.when(deferred, cluster.get('nodes').fetch({data: {cluster_id: cluster.id}}));
            }
            return cluster.task('verify_networks').fetch();
        },
        deploymentTaskFinished: function() {
            var cluster = this.props.cluster;
            $.when(cluster.fetch(), cluster.fetchRelated('nodes'), cluster.fetchRelated('tasks')).always(app.navbar.refresh);
        },
        startDeployment: function() {
            var cluster = this.props.cluster;
            $.when(cluster.fetch(), cluster.fetchRelated('nodes'), cluster.fetchRelated('tasks')).always(_.bind(function() {
                // FIXME: hack to prevent "Deploy" button flashing after deployment is finished
                cluster.set({changes: []}, {silent: true});
                this.startPolling();
            }, this));
        },
        componentDidMount: function() {
            var cluster = this.props.cluster;
            cluster.on('change:release_id', function() {
                var release = new models.Release({id: cluster.get('release_id')});
                release.fetch().done(function(){
                    cluster.set({release: release});
                });
            });
            this.eventNamespace = 'unsavedchanges' + this.activeTab;
            $(window).on('beforeunload.' + this.eventNamespace, _.bind(this.onBeforeunloadEvent, this));
            $('body').on('click.' + this.eventNamespace, 'a[href^=#]:not(.no-leave-check)', _.bind(this.onTabLeave, this));
        },
        onTabLeave: function(e) {
            var href = $(e.currentTarget).attr('href');
            if (Backbone.history.getHash() != href.substr(1) && _.result(this.tab, 'hasChanges')) {
                e.preventDefault();
                this.discardSettingsChanges({
                    verification: !!this.props.cluster.task({group: 'network', status: 'running'}),
                    cb: function() {
                        app.navigate(href, {trigger: true});
                    }
                });
            }
        },
        onBeforeunloadEvent: function() {
            if (_.result(this.tab, 'hasChanges')) {
                return dialogs.DiscardSettingsChangesDialog.prototype.defaultMessage;
            }
        },
        componentWillUnmount: function() {
            $(window).off('beforeunload.' + this.eventNamespace);
            $('body').off('click.' + this.eventNamespace);
        },
        render: function() {
            var cluster = this.props.cluster,
                deploymentTask = this.props.cluster.task({group: 'deployment'});
            var tabs = {
                nodes: NodesTab,
                network: NetworkTab,
                settings: SettingsTab,
                actions: ActionsTab,
                logs: LogsTab,
                healthcheck: HealthCheckTab
            };
            return (
                <div>
                    <ClusterInfo cluster={cluster} />
                    {deploymentTask &&
                        <DeploymentResult task={deploymentTask} />
                    }
                    {cluster.get('is_customized') &&
                        <div className='customization-message'>
                            <div className='alert alert-block globalalert'>
                                <p className='enable-selection'>{$.t('cluster_page.cluster_was_modified_from_cli')}</p>
                            </div>
                        </div>
                    }
                    <div className='whitebox'>
                        <ul className='nav nav-tabs cluster-tabs'>
                            {_.map(tabs, function(tab) {
                                return <li key={tab} className={this.activeTab == tab && 'active'}>
                                    <a href={'#cluster/' + cluster.id + '/' + tab}>
                                        <b className={'tab-' + tab + '-normal'} />
                                        <div className='tab-title'>{$.t('cluster_page.tabs.' + tab)}</div>
                                    </a>
                                </li>
                            }, this)}
                            <DeploymentControl cluster={this.props.cluster} tab={this.tab} />
                        </ul>
                        <div className='tab-content'>
                            {_.map(tabs, function(tab) {
                                return <div key={tab + '-pane'} className={'tab-pane ' + (this.activeTab == tab && 'active')} id={'tab-' + tab}>
                                    {this.tab = utils.universalMount(new tabs[this.activeTab]({model: cluster, tabOptions: this.tabOptions, page: this}), this.$('#tab-' + this.activeTab), this)}
                                </div>
                            })}
                        </div>
                    </div>
                </div>
            );
        }
    });

    var ClusterInfo = React.createClass({
        mixins: [
            React.BackboneMixin('cluster'),
            React.BackboneMixin({modelOrCollection: function(props) {
                return props.cluster.get('nodes');
            }}),
            React.BackboneMixin({modelOrCollection: function(props) {
                return props.cluster.get('release');
            }})
        ],
        render: function() {
            var cluster = this.props.cluster;
            return (
                <div className='cluster-info'>
                    <div className='cluster-name-box'>
                      <div className='cluster-name-placeholder'>
                        <div className='name-box'>
                          <h3 className='page-title'>{cluster.get('name')}</h3>
                          <div className='node-list-name-count'>({$.t('common.node', {count: cluster.get('nodes').length})})</div>
                          <div className='clearfix' />
                        </div>
                        <div className='cluster-summary-placeholder'>
                          <div>
                            <strong>{$.t('release_page.release_name')}: </strong>
                            <span>{cluster.get('release').get('name') + ' (' + cluster.get('release').get('version')  + ')'}</span>
                          </div>
                          <div>
                            <strong>{$.t('dialog.create_cluster_wizard.mode.title')}: </strong>
                            <span>{$.t('cluster.mode.' + cluster.get('mode'))}</span>
                          </div>
                          <div className={'status' + _.contains(['error', 'update_error'], cluster.get('status')) ? 'error' : ''}>
                            <strong>{$.t('cluster_page.environment_status')}: </strong>
                            <span>{cluster.get('status')}</span>
                          </div>
                        </div>
                     </div>
                    </div>
                </div>
            );
        }
    });

    var DeploymentResult = React.createClass({
        mixins: [
            React.BackboneMixin('task')
        ],
        dismissTaskResult: function() {
            this.props.task.destroy();
        },
        render: function() {
            var status = this.props.task.match({status: 'ready'}) ? 'success' : 'error';
            return (
                <div className='deployment-result'>
                    <div className={'alert alert-block global-' + status + ' alert-' + status}>
                      <button type='button' className='close' onClick={this.dismissTaskResult}>×</button>
                      <h4>{$.t('common.' + status)}</h4>
                      <p className='enable-selection' dangerouslySetInnerHTML={{__html: utils.urlify(task.escape('message'))}}></p>
                    </div>
                </div>
            );
        }
    });

    var DeploymentControl = React.createClass({
        mixins: [
            React.BackboneMixin('cluster'),
            React.BackboneMixin({modelOrCollection: function(props) {
                return props.cluster.get('nodes');
            }}),
            React.BackboneMixin({modelOrCollection: function(props) {
                return props.cluster.get('tasks');
            }}),
            React.BackboneMixin({modelOrCollection: function(props) {
                return props.cluster.get('release');
            }})
        ],
        discardChanges: function() {
            (new dialogs.DiscardChangesDialog({model: this.props.cluster})).render();
        },
        stopDeployment: function() {
            (new dialogs.StopDeploymentDialog({model: this.props.cluster})).render();
        },
        displayChanges: function() {
            (new dialogs.DisplayChangesDialog({model: this.props.cluster})).render();
        },
        onDeployRequest: function() {
            var tab = this.props.tab;
            if (_.result(tab, 'hasChanges')) {
                tab.page.discardSettingsChanges({cb: _.bind(function() {
                    tab.revertChanges();
                    this.displayChanges();
                }, this)});
            } else {
                this.displayChanges();
            }
        },
        render: function() {
            var cluster = this.props.cluster,
                task = cluster.task({group: 'deployment', status: 'running'}),
                showProgress = !_.contains(['stop_deployment', 'reset_environment'], task.get('name')),
                canDeploy = cluster.get('release').get('state') == 'available' && (cluster.hasChanges() || cluster.needsRedeployment());
            return (
                <div className='cluster-deploy-placeholder'>
                    {task ?
                        <div className='pull-right deployment-progress-box'>
                            {showProgress && !task.match({name: 'update'}) &&
                                <button className='btn btn-danger stop-deployment-btn' title={$.t('cluster_page.stop_deployment_button')} onClick={this.stopDeployment}>
                                    <i className='icon-cancel-circle'></i>
                                </button>
                            }
                            {showProgress &&
                                <div className='deploying-progress-text-box percentage'>{task.get('progress')}%</div>
                            }
                            <div className={'progress progress-striped active progress-' + showProgress ? 'success' : 'warning'}>
                                <div className='bar' style={'width: ' + task.get('progress') + '%'}></div>
                            </div>
                            <div className='progress-bar-description'>{$.t('cluster_page.' + task.get('name'))}</div>
                        </div>
                    :
                        <div className='pull-right deployment-control-box'>
                            <div>
                                <button className='deploy-btn' disabled={canDeploy} onClick={this.onDeployRequest}>
                                    <i className='icon-upload-cloud'></i>
                                    {$.t('cluster_page.deploy_changes')}
                                </button>
                            </div>
                            {cluster.get('nodes').hasChanges() &&
                                <div>
                                    <button className='btn rollback' role='button' title={$.t('cluster_page.discard_changes')} onClick={this.discardChanges}>
                                        <i className='icon-back-in-time'></i>
                                    </button>
                                </div>
                            }
                        </div>
                    }
                </div>
            );
        }
    });

    return ClusterPage;
});
