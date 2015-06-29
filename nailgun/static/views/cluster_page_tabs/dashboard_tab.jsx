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
define(
[
    'underscore',
    'i18n',
    'react',
    'utils',
    'models',
    'dispatcher',
    'react-d3-components',
    'jsx!views/dialogs',
    'jsx!component_mixins',
    'jsx!views/controls'
],
function(_, i18n, React, utils, models, dispatcher, ReactD3, dialogs, componentMixins, controls) {
    'use strict';

    var releases = new models.Releases();

    var DashboardTab = React.createClass({
        mixins: [
            // this is needed to somehow handle the case when verification is in progress and user pressed Deploy
            componentMixins.backboneMixin({
                modelOrCollection: function(props) {
                    return props.cluster.get('tasks');
                },
                renderOn: 'update change:status'
            })
        ],
        getInitialState: function() {
            return {
                actionInProgress: false,
                hasDeployBlockers: false
            };
        },
        refreshCluster: function() {
            return $.when(this.props.cluster.fetch(), this.props.cluster.fetchRelated('nodes'), this.props.cluster.fetchRelated('tasks'));
        },
        isNew: function() {
            var cluster = this.props.cluster,
                task = cluster.task({group: 'deployment', status: 'running'});
            return cluster.get('status') == 'new' || !!task;
        },
        render: function() {
            var cluster = this.props.cluster,
                nodes = cluster.get('nodes'),
                hasNodes = !!nodes.length,
                isNew = this.isNew(),
                title,
                task = cluster.task({group: 'deployment', status: 'running'}),
                taskName = task ? task.get('name') : '',
                taskProgress = task && task.get('progress') || 0,
                infiniteTask = _.contains(['stop_deployment', 'reset_environment'], taskName),
                stoppableTask = !_.contains(['stop_deployment', 'reset_environment', 'update'], taskName);

            if (isNew) {
                if (hasNodes) {
                    title = 'title_ready';
                } else {
                    title = 'title_new';
                }
            } else {
                if (task) {
                    title = 'deploy_progress';
                }
            }
            return (
                <div className='row'>
                    {!hasNodes &&
                        <DeployChangesBlock cluster={cluster} hasDeployBlockers={this.state.hasDeployBlockers} />
                    }
                    {!_.isUndefined(title) &&
                        <div className='title'>
                            {i18n('cluster_page.dashboard_tab.' + title)}
                        </div>
                    }
                    <div>
                        {hasNodes &&
                            <div className='col-xs-12'>
                                {task ?
                                    <div className='row'>
                                        <DeploymentInProgressControl
                                            cluster={this.props.cluster}
                                            taskName={taskName}
                                            taskProgress={taskProgress}
                                            infiniteTask={infiniteTask}
                                            stoppableTask={stoppableTask}
                                        />
                                    </div>
                                :
                                    <div className='row'>
                                        {!_.isUndefined(title) &&
                                            <WarningsBlock cluster={cluster} screen={this}/>
                                        }
                                        <DeployChangesBlock cluster={cluster} hasDeployBlockers={this.state.hasDeployBlockers} />
                                    </div>
                                }
                            </div>
                        }
                        <ClusterInfo
                            cluster={cluster}
                            isNew={isNew}
                        />
                        <DocumentationLinks />
                        <PluginsBlock cluster={cluster}/>
                    </div>
                </div>
            );
        }
    });

    var DeploymentInProgressControl = React.createClass({
        showDialog: function(Dialog) {
            Dialog.show({cluster: this.props.cluster});
        },
        render: function() {
            var taskName = this.props.taskName,
                infiniteTask = this.props.infiniteTask,
                taskProgress = this.props.taskProgress,
                stoppableTask = this.props.stoppableTask;
            return (
                <div className='col-xs-12 deploy-block'>
                    <div className={'deploy-process ' + this.props.taskName}>
                        <div>
                            <span>
                                <strong>
                                    {i18n('cluster_page.dashboard_tab.current_task') + ' '}
                                </strong>
                                {_.capitalize(taskName) + '...'}
                            </span>
                        </div>
                        <div className='progress'>
                            <div
                                className={utils.classNames({
                                            'progress-bar progress-bar-striped active': true,
                                            'progress-bar-warning': infiniteTask,
                                            'progress-bar-success': !infiniteTask
                                        })}
                                style={{width: (taskProgress > 3 ? taskProgress : 3) + '%'}}
                                >
                            </div>
                            <div className='deploy-status'>{i18n('cluster_page.' + taskName, {defaultValue: ''})}</div>
                        </div>
                        {stoppableTask &&
                            <button
                                className='btn btn-danger btn-xs pull-right stop-deployment-btn'
                                title={i18n('cluster_page.stop_deployment_button')}
                                onClick={_.partial(this.showDialog, dialogs.StopDeploymentDialog)}
                            >
                               {i18n('cluster_page.dashboard_tab.stop')}
                            </button>
                        }
                        {!infiniteTask &&
                            <div className='deploy-percents pull-right'>{taskProgress + '%'}</div>
                        }
                    </div>
                </div>
            );
        }
    });

    var WarningsBlock = React.createClass({
        mixins: [
            // this is needed to somehow handle the case when verification is in progress and user pressed Deploy
            componentMixins.backboneMixin({
                modelOrCollection: function(props) {
                    return props.cluster.get('tasks');
                },
                renderOn: 'update change:status'
            })
        ],
        getConfigModels: function() {
            var cluster = this.props.cluster,
                settings = cluster.get('settings');
            return {
                cluster: cluster,
                settings: settings,
                version: app.version,
                release: cluster.get('release'),
                default: settings,
                networking_parameters: cluster.get('networkConfiguration').get('networking_parameters')
            };
        },
        ns: 'dialog.display_changes.',
        getInitialState: function() {
            var alerts = this.validate(this.props.cluster),
                state = {
                    alerts: alerts,
                    isInvalid: !_.isEmpty(alerts.blocker),
                    hasErrors: !_.isEmpty(alerts.error)
                };
            this.props.screen.setState({hasDeployBlockers: state.isInvalid});
            return state;
        },
        render: function() {
            var cluster = this.props.cluster,
                nodes = cluster.get('nodes');
            return (
                <div className='display-changes-dialog'>
                    {(this.state.isInvalid || cluster.needsRedeployment()) ?
                        <div>
                            <div className='text-danger'>
                                <i className='glyphicon glyphicon-warning-sign' />
                                <span>{i18n(this.ns + (this.state.isInvalid ? 'warnings.no_deployment' : 'redeployment_needed'))}</span>
                            </div>
                            <hr />
                        </div>
                    : _.contains(['new', 'stopped'], cluster.get('status')) &&
                        <div>
                            <div className='text-warning'>
                                <i className='glyphicon glyphicon-warning-sign' />
                                <span>{i18n(this.ns + 'locked_settings_alert')}</span>
                            </div>
                            <hr />
                            <div className='text-warning'>
                                <i className='glyphicon glyphicon-warning-sign' />
                                <span dangerouslySetInnerHTML={{__html: utils.linebreaks(_.escape(i18n(this.ns + 'warnings.connectivity_alert')))}} />
                            </div>
                            <hr />
                        </div>
                    }
                    {this.showVerificationMessages()}
                </div>
            );
        },
        validations: [
            // VCenter
            function(cluster) {
                if (cluster.get('settings').get('common.use_vcenter.value')) {
                    var vcenter = cluster.get('vcenter');
                    vcenter.setModels(this.getConfigModels()).parseRestrictions();
                    return !vcenter.isValid() &&
                        {blocker: [
                            (<span>{i18n('vmware.has_errors') + ' '}
                                <a href={'/#cluster/' + cluster.id + '/vmware'}>
                                    {i18n('vmware.tab_name')}
                                </a>
                            </span>)
                        ]
                        };
                }
            },
            // Invalid settings
            function(cluster) {
                var configModels = this.getConfigModels(),
                    areSettingsInvalid = !cluster.get('settings').isValid({models: configModels});
                return areSettingsInvalid &&
                    {blocker: [
                        (<span>
                            {i18n(this.ns + 'invalid_settings')}
                            {' ' + i18n(this.ns + 'get_more_info') + ' '}
                            <a href={'#cluster/' + cluster.id + '/settings'}>
                                {i18n(this.ns + 'settings_link')}
                            </a>.
                        </span>)
                    ]};
            },
            // Amount restrictions
            function(cluster) {
                var configModels = this.getConfigModels(),
                    roleModels = cluster.get('release').get('role_models'),
                    validRoleModels = roleModels.filter(function(role) {
                        return !role.checkRestrictions(configModels).result;
                    }),
                    limitValidations = _.zipObject(validRoleModels.map(function(role) {
                        return [role.get('name'), role.checkLimits(configModels)];
                    })),
                    limitRecommendations = _.zipObject(validRoleModels.map(function(role) {
                        return [role.get('name'), role.checkLimits(configModels, true, ['recommended'])];
                    }));
                return {
                    blocker: roleModels.map(_.bind(
                        function(role) {
                            var name = role.get('name'),
                                limits = limitValidations[name];
                            return limits && !limits.valid && limits.message;
                        }, this)),
                    warning: roleModels.map(_.bind(
                        function(role) {
                            var name = role.get('name'),
                                recommendation = limitRecommendations[name];

                            return recommendation && !recommendation.valid && recommendation.message;
                        }, this))
                };
            },
            // Network
            function(cluster) {
                var networkVerificationTask = cluster.task({group: 'network'}),
                    makeComponent = _.bind(function(text, isError) {
                        var span = (
                            <span>
                                {text}
                                {' ' + i18n(this.ns + 'get_more_info') + ' '}
                                <a href={'#cluster/' + this.props.cluster.id + '/network'}>
                                    {i18n(this.ns + 'networks_link')}
                                </a>.
                            </span>
                        );
                        return isError ? {error: [span]} : {warning: [span]};
                    }, this);

                if (_.isUndefined(networkVerificationTask)) {
                    return makeComponent(i18n(this.ns + 'verification_not_performed'));
                } else if (networkVerificationTask.match({status: 'error'})) {
                    return makeComponent(i18n(this.ns + 'verification_failed'), true);
                } else if (networkVerificationTask.match({status: 'running'})) {
                    return makeComponent(i18n(this.ns + 'verification_in_progress'));
                }
            }
        ],
        validate: function(cluster) {
            return _.reduce(
                this.validations,
                function(accumulator, validator) {
                    return _.merge(accumulator, validator.call(this, cluster), function(a, b) {
                        return a.concat(_.compact(b));
                    });
                },
                {blocker: [], error: [], warning: []},
                this
            );
        },
        showVerificationMessages: function() {
            var result = {
                    danger: _.union(this.state.alerts.blocker, this.state.alerts.error),
                    warning: this.state.alerts.warning
                },
                blockers = this.state.alerts.blocker.length;
            return (
                <div className='validation-result'>
                    {
                        ['danger', 'warning'].map(function(severity) {
                            if (_.isEmpty(result[severity])) return null;
                            return (
                                <ul key={severity} className={'alert alert-' + severity}>
                                    {result[severity].map(function(line, index) {
                                        return (<li key={severity + index}>
                                            {severity == 'danger' && index < blockers && <i className='glyphicon glyphicon-exclamation-sign' />}
                                            {line}
                                        </li>);
                                    })}
                                </ul>
                            );
                        }, [])
                    }
                </div>
            );
        }
    });

    var DeploymentControl = React.createClass({
        mixins: [
            componentMixins.backboneMixin({
                modelOrCollection: function(props) {return props.cluster.get('nodes');},
                renderOn: 'change:pending_addition change:pending_deletion'
            })
        ],
        showDialog: function(Dialog) {
            Dialog.show({cluster: this.props.cluster});
        },
        onDeployRequest: function() {
            if (this.props.hasChanges()) {
                dialogs.DiscardSettingsChangesDialog.show({cb: _.bind(function() {
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
                stoppableTask = !_.contains(['stop_deployment', 'reset_environment', 'update'], taskName),
                isDeploymentImpossible = cluster.get('release').get('state') == 'unavailable' || (!cluster.get('nodes').hasChanges() && !cluster.needsRedeployment());
            return (
                <div className='col-xs-6 col-md-3'>
                    <div className='deploy-box pull-right'>
                        {task ? (
                            <div className={'deploy-process ' + taskName}>
                                <span>{'Current task: ' + taskName}</span>
                                <div className='progress'>
                                    <div
                                        className={utils.classNames({
                                            'progress-bar progress-bar-striped active': true,
                                            'progress-bar-warning': infiniteTask,
                                            'progress-bar-success': !infiniteTask
                                        })}
                                        style={{width: (taskProgress > 3 ? taskProgress : 3) + '%'}}
                                        >
                                    </div>
                                    <div className='deploy-status'>{i18n('cluster_page.' + taskName, {defaultValue: ''})}</div>
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
                            <button
                                key='deploy-changes'
                                className='btn btn-primary deploy-btn'
                                disabled={isDeploymentImpossible}
                                onClick={this.onDeployRequest}
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

    var DeploymentResult = React.createClass({
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
                    alert: true,
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

    var DeployChangesBlock = React.createClass({
        getInitialState: function() {
            return {
                actionInProgress: false
            };
        },
        showDialog: function(Dialog) {
            Dialog.show({cluster: this.props.cluster});
        },
        renderChangedNodesAmount: function(nodes, dictKey) {
            var areNodesPresent = !!nodes.length;
            return (areNodesPresent &&
                <div className='changes-item' key={dictKey}>
                    {++this.counter + '. ' + i18n('dialog.display_changes.' + dictKey, {count: nodes.length})}
                </div>
            );
        },
        showError: function(response, message) {
            var props = {error: true};
            props.message = utils.getResponseText(response) || message;
            this.setProps(props);
        },
        onDeployRequest: function() {
            this.setState({actionInProgress: true});
            dispatcher.trigger('deploymentTasksUpdated');
            var task = new models.Task();
            task.save({}, {url: _.result(this.props.cluster, 'url') + '/changes', type: 'PUT'})
                .done(function() {
                    dispatcher.trigger('deploymentTaskStarted');
                }.bind(this))
                .fail(this.showError);
        },
        render: function() {
            var cluster = this.props.cluster,
                nodes = cluster.get('nodes'),
                isDeploymentImpossible = cluster.get('release').get('state') == 'unavailable' ||
                    (!cluster.get('nodes').hasChanges() && !cluster.needsRedeployment()) || this.props.hasDeployBlockers,
                namespace = 'cluster_page.dashboard_tab.';
            this.counter = 0;
            return (
                <div className='col-xs-12 deploy-block'>
                    {!isDeploymentImpossible ?
                        <div className='row'>
                            <div className='col-xs-6 changes-list'>
                                {!!nodes.length &&
                                    <div className='col-xs-12'>
                                        <p className='changes-header'>
                                                {i18n(namespace + 'changes_header') + ':'}
                                        </p>
                                            {this.renderChangedNodesAmount(nodes.where({pending_addition: true}), 'added_node')}
                                            {this.renderChangedNodesAmount(nodes.where({pending_deletion: true}), 'deleted_node')}
                                    </div>
                                }

                                <button
                                    key='deploy-changes'
                                    className='btn btn-primary deploy-btn'
                                    disabled={isDeploymentImpossible}
                                    onClick={this.onDeployRequest}
                                >
                                    <div className='deploy-icon'></div>
                                    {i18n('cluster_page.deploy_changes')}
                                </button>
                                {nodes.hasChanges() &&
                                    <a
                                        key='discard-changes'
                                        onClick={_.partial(this.showDialog, dialogs.DiscardNodeChangesDialog)}
                                    >
                                        {i18n('cluster_page.discard_changes')}
                                    </a>
                                }
                            </div>
                            <div className='col-xs-6 deploy-readiness'>
                                <span className='section-title'>{i18n(namespace + 'all_right')}</span>
                                <br />
                                <span>{i18n(namespace + 'environment_ready')}</span>
                            </div>
                        </div>
                    :
                        <div className='row'>
                            <div className='col-xs-2'>
                                <button
                                    key='deploy-changes'
                                    className='btn btn-primary deploy-btn'
                                    disabled={isDeploymentImpossible}
                                    onClick={this.onDeployRequest}
                                >
                                    <div className='deploy-icon'></div>
                                    {i18n('cluster_page.deploy_changes')}
                                </button>
                            </div>
                            <div className='col-xs-10 deploy-readiness'>
                                <DeploymentResult cluster={cluster} />
                                <span>{i18n(namespace + 'can_not_start_deploy')}</span>
                                <br />
                                {!nodes.length &&
                                    <span>{i18n(namespace + 'add_nodes')}</span>
                                }
                            </div>
                        </div>
                    }
                </div>
            );
        }
    });

    var DocumentationLinks = React.createClass({
        renderDocumentationLinks: function(link, labelKey) {
            var ns = 'cluster_page.dashboard_tab.';
            return (
                <div className='col-xs-12 documentation-link'>
                    <span>
                        <i className='glyphicon glyphicon-list-alt' />
                        <a href={link} >
                            {i18n(ns + labelKey)}
                        </a>
                    </span>
                </div>
            );
        },
        render: function() {
            return (
                <div className='col-xs-12'>
                    <div className='row'>
                        <div className='col-xs-12'>
                            {i18n('cluster_page.dashboard_tab.documentation_description')}
                        </div>
                    </div>
                    <div className='documentation'>
                        <div className='row'>
                            {this.renderDocumentationLinks('https://www.mirantis.com/openstack-documentation/', 'mos_documentation')}
                            {this.renderDocumentationLinks('https://wiki.openstack.org/wiki/Fuel/Plugins', 'plugin_documentation')}
                            {this.renderDocumentationLinks('https://software.mirantis.com/mirantis-openstack-technical-bulletins/', 'technical_bulletins')}
                        </div>
                    </div>
                </div>
            );
        }
    });

    var ClusterInfo = React.createClass({
        getInitialState: function() {
            return {isRenaming: false};
        },
        getDefaultProps: function() {
            return {namespace: 'cluster_page.dashboard_tab.cluster_info_fields.'};
        },
        getClusterValue: function(fieldName) {
            var cluster = this.props.cluster,
                release = cluster.get('release'),
                settings = cluster.get('settings');
            switch (fieldName) {
                case 'openstack_release':
                    return release.get('name');
                case 'operating_system':
                    return release.get(fieldName);
                case 'compute':
                    var compute = settings.get('common').libvirt_type.value;
                    compute += (settings.get('common').use_vcenter.value ? ' and VCenter' : '');
                    return compute;
                case 'network':
                    var network,
                        networkingParams = cluster.get('networkConfiguration').get('networking_parameters'),
                        networkManager = networkingParams.get('net_manager');
                    if (cluster.get('net_provider') == 'nova_network') {
                        return 'Nova Network with ' + networkManager + ' manager';
                    } else {
                        return 'Neutron with ' + networkingParams.get('segmentation_type').toUpperCase();
                    }
                    break;
                case 'storage_backends':
                    var volumesLVM = settings.get('storage').volumes_lvm,
                        volumesCeph = settings.get('storage').volumes_ceph;
                    return volumesLVM.value && volumesLVM.label || volumesCeph.value && volumesCeph.label;
                case 'healthcheck_status':
                    //@todo
                    //debugger;
                    var ostfStatus =  'Unavailable ';
                    return ostfStatus;
                default:
                    return cluster.get(fieldName);
            }
        },
        renderClusterInfoFields: function() {
            var namespace = this.props.namespace,
                fields = ['openstack_release', 'operating_system', 'compute', 'network', 'storage_backends',
                    'healthcheck_status'],
                isOSTFAvailable = !_.isEmpty(this.props.cluster.get('ostf')) && !this.props.isNew;
            return (
                <div className='col-xs-12'>
                    {_.map(fields, function(field) {
                        return (
                            <div className='row' key={field}>
                                <div className='col-xs-6'>
                                    <div className='cluster-info-title'>
                                        {i18n(namespace + field)}
                                    </div>
                                </div>
                                <div className='col-xs-6'>
                                    <div className='cluster-info-value'>
                                        {this.getClusterValue(field)}
                                        {field == 'healthcheck_status' && isOSTFAvailable &&
                                            <a href='#cluster/1/healthcheck'>
                                                Run NOW
                                            </a>
                                        }
                                    </div>

                                </div>
                            </div>
                        );
                    }, this)}
                </div>
            );
        },
        renderClusterCapacity: function() {
            var cores = 0,
                hdds = 0,
                rams = 0,
                namespace = this.props.namespace;
                this.props.cluster.get('nodes').each(function(node) {
                    cores += node.resource('ht_cores');
                    hdds += node.resource('hdd');
                    rams += node.resource('ram');
            }, this);

            return (
                <div className='row capacity-block'>
                    <div className='title'>{i18n(namespace + 'capacity')}</div>
                    <div className='col-xs-4 cpu capacity-item'>
                        <span>{i18n(namespace + 'cpu_cores')}</span>
                        <span className='capacity-value'>{cores}</span>
                    </div>
                    <div className='col-xs-4 hdd capacity-item'>
                        <span>{i18n(namespace + 'hdd')}</span>
                        <span className='capacity-value'>{utils.showDiskSize(hdds)}</span>
                    </div>
                    <div className='col-xs-4 ram capacity-item'>
                        <span>{i18n(namespace + 'ram')}</span>
                        <span className='capacity-value'>{utils.showDiskSize(rams)}</span>
                    </div>
                </div>
            );
        },
        getNumberOfNodesWithRole: function(field) {
            var nodes = this.props.cluster.get('nodes');
            if (!nodes.length) return 0;
            switch (field) {
                case 'compute':
                case 'controller':
                case 'cinder':
                case 'ceph-osd':
                case 'mongo':
                case 'base-os':
                    return _.filter(nodes.invoke('hasRole', field)).length;
                case 'total':
                    return nodes.length;
                case 'offline':
                    return nodes.where({online: false}).length;
                case 'error':
                    return _.filter(nodes.pluck('error_type')).length;
            }
        },
        renderStatistics: function() {
            //@todo: verify colors
            var rolesToColors = {
                    compute: '#f5c118',
                    controller: '#5318f5',
                    cinder: '#ea1ae1',
                    'ceph-osd': '#eaaaed',
                    mongo: '#28c7c7',
                    'base-os': '#faffff',
                    offline: '#ccc',
                    error: '#eb1c1c'
                },
                chartWidth = 300,
                chartHeight = 400;

            var namespace = this.props.namespace,
                fields = ['total', 'compute', 'controller', 'cinder',
                    'ceph-osd', 'mongo', 'base-os', 'offline', 'error'];

            var color = d3.scale.ordinal()
                .domain(_.keys(rolesToColors))
                .range(_.values(rolesToColors));
            var data = {
                values: _.filter(_.map(_.without(fields, 'total'), function(field) {
                    if (this.getNumberOfNodesWithRole(field)) {
                        return {
                            x: field,
                            y: this.getNumberOfNodesWithRole(field)
                        };
                    }
                }, this))
            };

            if (!data.values.length) {
                data.values = [{x: '', y: 1}];
                color = d3.scale.ordinal()
                    .domain([0, 1])
                    .range(['#ccc', '#ccc111']);
            }

            return (
                <div className='row statistics-block'>
                    <div className='title'>{i18n(namespace + 'statistics')}</div>
                    {!!this.props.cluster.get('nodes').length ?
                        <div className='col-xs-6'>
                            {_.map(fields, function(field) {
                                var numberOfNodesWithRole = this.getNumberOfNodesWithRole(field);
                                return numberOfNodesWithRole ?
                                        <div className='row'>
                                            <div className='col-xs-6'>
                                                <div className='cluster-info-title'>
                                                    {i18n(namespace + field)}
                                                </div>
                                            </div>
                                            <div className='col-xs-6'>
                                                <div className='cluster-info-value' style={{color: rolesToColors[field]}} >
                                                    {numberOfNodesWithRole}
                                                </div>
                                            </div>
                                        </div>
                                :
                                    null;
                            }, this)}
                        </div>
                    :
                        <div className='col-xs-6 no-nodes-block'>
                            <p>
                                {i18n('cluster_page.dashboard_tab.no_nodes_warning_add_them')}
                            </p>
                            <button
                                className='btn btn-success btn-add-nodes'
                                onClick={_.bind(function() {app.navigate('#cluster/' + this.props.cluster.get('id') + '/nodes/add', {trigger: true, replace: true})}, this)}
                            >
                                <i className='glyphicon glyphicon-plus' />
                                {i18n('cluster_page.nodes_tab.node_management_panel.add_nodes_button')}
                            </button>
                        </div>
                    }
                    <div className='col-xs-6 chart'>
                        <ReactD3.PieChart
                            data={data}
                            width={chartWidth}
                            height={chartHeight}
                            colorScale={color}
                        />
                        <span className='chart-title' style={{top: (chartHeight / 2) - 10 + 'px', left: (chartWidth / 2) + 10 + 'px'}}>
                            {this.props.cluster.get('nodes').length}
                        </span>
                    </div>
                </div>
            );
        },
        renameCluster: function() {
            this.setState({isRenaming: true});
        },
        render: function() {
            var cluster = this.props.cluster,
                namespace = 'cluster_page.dashboard_tab.',
                isNew = this.props.isNew,
                isExperimental = _.contains(app.version.get('feature_groups'), 'experimental'),
                task = cluster.task({group: 'deployment', status: 'running'});

            return (
                <div className='col-xs-12 section-wrapper cluster-information'>
                    <div className='row'>
                        <div className='col-xs-6'>
                            <div className='row'>
                                <div className='title'>{i18n(namespace + 'summary')}</div>
                                <div className='col-xs-12'>
                                    <div className='row'>
                                        <div className='col-xs-6'>
                                            <div className='cluster-info-title'>
                                                {i18n(namespace + 'cluster_info_fields.name')}
                                            </div>
                                        </div>
                                        <div className='col-xs-6'>
                                            {this.state.isRenaming ?
                                                <RenameEnvironmentAction
                                                    cluster={cluster}
                                                    parent={this}
                                                />
                                            :
                                                <div className='cluster-info-value name' onClick={this.renameCluster}>
                                                    <a>
                                                        {cluster.get('name')}
                                                    </a>
                                                    <i className='glyphicon glyphicon-pencil'></i>
                                                </div>
                                            }
                                        </div>
                                    </div>
                                </div>
                                {this.renderClusterInfoFields()}
                            </div>
                        </div>
                        <div className='col-xs-6 '>
                            {this.renderClusterCapacity()}
                            {this.renderStatistics()}
                        </div>
                    </div>
                    <div className='row'>
                        <ResetEnvironmentAction cluster={cluster} task={task} disabled={isNew} />
                        <DeleteEnvironmentAction cluster={cluster} />
                    </div>
                </div>
            );
        }
    });

    var Action = React.createClass({
        getDefaultProps: function() {
            return {className: 'col-xs-12 col-md-3'};
        },
        render: function() {
            return (
                <div className={'action-item ' + this.props.className}>
                    {this.props.children}
                </div>
            );
        }
    });

    var RenameEnvironmentAction = React.createClass({
        applyAction: function(e) {
            e.preventDefault();
            var cluster = this.props.cluster,
                name = this.state.name;
            if (name != cluster.get('name')) {
                var deferred = cluster.save({name: name}, {patch: true, wait: true});
                if (deferred) {
                    this.setState({disabled: true});
                    deferred
                        .fail(_.bind(function(response) {
                            if (response.status == 409) {
                                this.setState({error: utils.getResponseText(response)});
                            } else {
                                utils.showErrorDialog({
                                    title: i18n('cluster_page.dashboard_tab.rename_error.title'),
                                    response: response
                                });
                            }
                        }, this))
                        .done(function() {
                            dispatcher.trigger('updatePageLayout');
                        })
                        .always(_.bind(function() {
                            this.props.parent.setState({isRenaming: false});
                            this.setState({disabled: false});
                        }, this));
                } else {
                    if (cluster.validationError) {
                        this.setState({error: cluster.validationError.name});
                    }
                }
            } else {
                this.props.parent.setState({isRenaming: false});
            }
        },
        getInitialState: function() {
            return {
                name: this.props.cluster.get('name'),
                disabled: false,
                error: ''
            };
        },
        handleChange: function(newValue) {
            this.setState({
                name: newValue,
                error: ''
            });
        },
        render: function() {
            var valueLink = {
                value: this.state.name,
                requestChange: this.handleChange
            };
            return (
                <div className='rename-block'>
                    <div className='action-body'>
                        <input type='text'
                            disabled={this.state.disabled}
                            className={utils.classNames({'form-control': true, error: this.state.error})}
                            maxLength='50'
                            valueLink={valueLink}
                        />
                        {this.state.error &&
                        <div className='text-danger'>
                            {this.state.error}
                        </div>
                        }
                    </div>
                    <button
                        className='btn btn-success rename-environment-btn'
                        onClick={this.applyAction}
                        disabled={this.state.disabled}
                    >
                        {i18n('cluster_page.dashboard_tab.rename_environment')}
                    </button>
                </div>
            );
        }
    });

    var ResetEnvironmentAction = React.createClass({
        mixins: [
            componentMixins.backboneMixin('cluster'),
            componentMixins.backboneMixin('task')
        ],
        getInitialState: function() {
            return {};
        },
        togglePopover: function(popoverName) {
            debugger;
            return _.memoize(_.bind(function(visible) {
                this.setState(function(previousState) {
                    var nextState = {};
                    var key = popoverName + 'PopoverVisible';
                    nextState[key] = _.isBoolean(visible) ? visible : !previousState[key];
                    return nextState;
                });
            }, this));
        },
        getDescriptionKey: function() {
            var task = this.props.task;
            if (task) {
                if (_.contains(task.get('name'), 'reset')) {return 'repeated_reset_disabled';}
                return 'reset_disabled_for_deploying_cluster';
            }
            if (this.props.cluster.get('status') == 'new') {return 'reset_disabled_for_new_cluster';}
            return 'reset_environment_description';
        },
        applyAction: function(e) {
            e.preventDefault();
            dialogs.ResetEnvironmentDialog.show({cluster: this.props.cluster});
        },
        render: function() {
            var isLocked = this.props.disabled,
                ns = 'cluster_page.dashboard_tab.';
            debugger;
            return (
                <Action>
                    <button
                        className='btn btn-danger reset-environment-btn'
                        onClick={this.applyAction}
                        disabled={isLocked}
                    >
                        {i18n('cluster_page.dashboard_tab.reset_environment')}
                    </button>
                    <i
                        key='language-icon'
                        className='glyphicon glyphicon-question-sign'
                        onClick={this.togglePopover('reset')}
                    >
                    </i>
                    {this.state.resetPopoverVisible &&
                        <ActionsPopover
                            key='reset-popover'
                            description={!isLocked ? i18n(ns + 'reset_environment_warning') : i18n(ns + this.getDescriptionKey())}
                            toggle={this.togglePopover('reset')}
                            className='reset'
                        />
                    }
                </Action>
            );
        }
    });

    var ActionsPopover = React.createClass({
        render: function() {
            return (
                <controls.Popover {...this.props}>
                    {this.props.description}
                </controls.Popover>
            );
        }
    });

    var DeleteEnvironmentAction = React.createClass({
        getInitialState: function() {
            return {};
        },
        togglePopover: function(popoverName) {
            return _.memoize(_.bind(function(visible) {
                this.setState(function(previousState) {
                    var nextState = {};
                    var key = popoverName + 'PopoverVisible';
                    nextState[key] = _.isBoolean(visible) ? visible : !previousState[key];
                    return nextState;
                });
            }, this));
        },
        applyAction: function(e) {
            e.preventDefault();
            dialogs.RemoveClusterDialog.show({cluster: this.props.cluster});
        },
        render: function() {
            return (
                <Action>
                    <button
                        className='btn btn-danger delete-environment-btn'
                        onClick={this.applyAction}
                    >
                        {i18n('cluster_page.dashboard_tab.delete_environment')}
                    </button>
                    <i
                        key='language-icon'
                        className='glyphicon glyphicon-question-sign'
                        onClick={this.togglePopover('delete')}
                    >
                    </i>
                    {this.state.deletePopoverVisible &&
                        <ActionsPopover
                            key='delete-popover'
                            description={i18n('cluster_page.dashboard_tab.alert_delete')}
                            toggle={this.togglePopover('delete')}
                            className='delete'
                        />
                    }
                </Action>
            );
        }
    });

    var PluginsBlock = React.createClass({
        render: function() {
            //@todo: fix when backend done
            var demoData = [
                {
                    title: 'Zabbix',
                    description: 'Zabbix is software that monitors numerous' +
                        ' parameters of a network and the health and integrity' +
                        ' of servers',
                    url: 'http://www.zabbix.com/',
                    id: 1
                },
                {
                    title: 'Murano',
                    url: 'https://wiki.openstack.org/wiki/Murano',
                    id: 2
                },
                {
                    title: 'My plugin',
                    description: 'My awesome plugin',
                    url: '/my_plugin',
                    id: 3
                }
            ];

            return (
                <div className='plugins-block col-xs-12'>
                    {_.map(demoData, function(dashboardEntry) {
                        return (
                            <div className='col-xs-6 plugin-entry' key={dashboardEntry.id}>
                                <div className='title'>{dashboardEntry.title}</div>
                                <div className='description'>{dashboardEntry.description}</div>
                                <a className='link' href={dashboardEntry.url}>{dashboardEntry.url}</a>
                            </div>
                        );
                    }, this)}
                </div>
            );
        }
    });

    return DashboardTab;
});
