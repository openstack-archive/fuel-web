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
    'jquery',
    'react',
    'utils',
    'models',
    'dispatcher',
    'jsx!views/dialogs',
    'jsx!component_mixins',
    'jsx!views/controls'
],
function(_, i18n, $, React, utils, models, dispatcher, dialogs, componentMixins, controls) {
    'use strict';

    var namespace = 'cluster_page.dashboard_tab.';

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
        statics: {
            fetchData: function(options) {
                return $.when(options.cluster.fetch(), options.cluster.fetchRelated('nodes'),
                    options.cluster.fetchRelated('tasks'));
            }
        },
        getInitialState: function() {
            return {
                actionInProgress: false,
                hasDeployBlockers: false
            };
        },
        isNew: function() {
            var cluster = this.props.cluster,
                runningDeploymentTask = cluster.task({group: 'deployment', status: 'running'});
            return cluster.get('status') == 'new' || !!runningDeploymentTask;
        },
        render: function() {
            var cluster = this.props.cluster,
                nodes = cluster.get('nodes'),
                hasNodes = !!nodes.length,
                hasChanges = nodes.hasChanges(),
                isNew = this.isNew(),
                title = 'title_new',
                deployRunningTask = cluster.task({group: 'deployment', status: 'running'}),
                taskName = deployRunningTask ? deployRunningTask.get('name') : '',
                taskProgress = deployRunningTask && deployRunningTask.get('progress') || 0,
                infiniteTask = _.contains(['stop_deployment', 'reset_environment'], taskName),
                stoppableTask = !_.contains(['stop_deployment', 'reset_environment', 'update', 'spawn_vms'], taskName),
                deployErrorTask = cluster.task({group: 'deployment', status: 'error'}),
                stopDeploymentTask = cluster.task({group: 'deployment', name: 'stop_deployment'});

            if (hasNodes) {
                title = 'title_ready';
            }
            if (!isNew) {
                title = null;
            }
            if (deployRunningTask) {
                title = 'deploy_progress';
            }
            if (deployErrorTask) {
                title = 'title_error';
            }

            return (
                <div>
                    {deployErrorTask &&
                        <div className='row'>
                            <DashboardTitle title={title} />
                        </div>
                    }
                    {(deployErrorTask || !isNew || stopDeploymentTask) &&
                        <DeploymentResult cluster={this.props.cluster} />
                    }
                    {!isNew && !deployErrorTask && !stopDeploymentTask &&
                        <PluginsBlock cluster={cluster} />
                    }
                    {(!deployErrorTask && isNew || hasChanges) &&
                        <div className='row'>
                            {!!title && !deployErrorTask && hasNodes &&
                                <DashboardTitle title={title} />
                            }
                            {hasNodes && deployRunningTask ?
                                <DeploymentInProgressControl
                                    cluster={this.props.cluster}
                                    taskName={taskName}
                                    taskProgress={taskProgress}
                                    infiniteTask={infiniteTask}
                                    stoppableTask={stoppableTask}
                                />
                            :
                                !!((isNew && !deployErrorTask) || stopDeploymentTask || hasChanges) &&
                                    <div className='col-xs-12'>
                                        <DeployReadinessBlock
                                            cluster={cluster}
                                            deploymentErrorTask={deployErrorTask}
                                        />
                                    </div>
                            }
                        </div>
                    }
                    <ClusterInfo
                        cluster={cluster}
                        isNew={isNew}
                    />
                    <DocumentationLinks />
                </div>
            );
        }
    });

    var DashboardTitle = React.createClass({
        render: function() {
            return (
                <div className='title'>
                    {i18n(namespace + this.props.title)}
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
                                    {i18n(namespace + 'current_task') + ' '}
                                </strong>
                                {_.capitalize(taskName) + '...'}
                            </span>
                        </div>
                        <div className='progress'>
                            <div className='progress-bar' role='progressbar' style={{width: _.max([taskProgress, 3]) + '%'}}>
                                {taskProgress + '%'}
                            </div>
                        </div>
                        {stoppableTask &&
                            <button
                                className='btn btn-danger btn-xs pull-right stop-deployment-btn'
                                title={i18n('cluster_page.stop_deployment_button')}
                                onClick={_.partial(this.showDialog, dialogs.StopDeploymentDialog)}
                            >
                                {i18n(namespace + 'stop')}
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
        ns: 'dialog.display_changes.',
        render: function() {
            return (
                <div className='warnings-block'>
                    {this.showVerificationMessages()}
                </div>
            );
        },
        showVerificationMessages: function() {
            var result = {
                    danger: _.union(this.props.alerts.blocker, this.props.alerts.error),
                    warning: this.props.alerts.warning
                },
                blockers = this.props.alerts.blocker && this.props.alerts.blocker.length;
            return (
                <div className='validation-result'>
                    {
                        _.map(['danger', 'warning'], function(severity) {
                            if (_.isEmpty(result[severity]) || (!this.props.cluster.get('nodes').length && severity == 'warning')) return null;
                            return (
                                <ol key={severity} className={severity}>
                                    {result[severity].map(function(line, index) {
                                        return (<li key={severity + index}>
                                            {line}
                                        </li>);
                                    })}
                                </ol>
                            );
                        }, this)
                    }
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

    var DocumentationLinks = React.createClass({
        renderDocumentationLinks: function(link, labelKey) {
            return (
                <div className='documentation-link'>
                    <span>
                        <i className='glyphicon glyphicon-list-alt' />
                        <a href={link} >
                            {i18n(namespace + labelKey)}
                        </a>
                    </span>
                </div>
            );
        },
        render: function() {
            return (
                <div className='row content-elements'>
                    <div className='title'>{i18n(namespace + 'documentation')}</div>
                    <div className='col-xs-12'>
                        <p>
                            {i18n(namespace + 'documentation_description')}
                        </p>
                    </div>
                    <div className='documentation col-xs-12'>
                        {this.renderDocumentationLinks('https://www.mirantis.com/openstack-documentation/', 'mos_documentation')}
                        {this.renderDocumentationLinks('https://wiki.openstack.org/wiki/Fuel/Plugins', 'plugin_documentation')}
                        {this.renderDocumentationLinks('https://software.mirantis.com/mirantis-openstack-technical-bulletins/', 'technical_bulletins')}
                    </div>
                </div>
            );
        }
    });

    var DeployReadinessBlock = React.createClass({
        ns: 'dialog.display_changes.',
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
        getInitialState: function() {
            var alerts = this.validate(this.props.cluster),
                state = {
                    alerts: alerts,
                    isInvalid: !_.isEmpty(alerts.blocker),
                    hasErrors: !_.isEmpty(alerts.error),
                    actionInProgress: false
                };
            return state;
        },
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
                    roleModels = cluster.get('roles'),
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
        showDialog: function(Dialog) {
            Dialog.show({cluster: this.props.cluster});
        },
        onActionRequest: function(Dialog) {
            this.showDialog(Dialog);
        },
        renderChangedNodesAmount: function(nodes, dictKey) {
            var areNodesPresent = !!nodes.length;
            return (areNodesPresent &&
            <li className='changes-item' key={dictKey}>
                {i18n('dialog.display_changes.' + dictKey, {count: nodes.length})}
            </li>
            );
        },
        showError: function(response, message) {
            var props = {error: true};
            props.message = utils.getResponseText(response) || message;
            this.setProps(props);
        },
        render: function() {
            var cluster = this.props.cluster,
                nodes = this.props.cluster.get('nodes'),
                isDeploymentImpossible = cluster.get('release').get('state') == 'unavailable' ||
                    (!cluster.get('nodes').hasChanges() && !cluster.needsRedeployment()) ||
                    !!this.state.alerts.blocker.length,
                hasNodes = !!nodes.length,
                isVMsProvisioningAvailable = cluster.get('nodes').any(function(node) {
                    return node.get('pending_addition') && node.hasRole('virt');
                });
            return (
                <div className='deploy-block'>
                    <div className='row'>
                        {hasNodes &&
                            <div className='col-xs-12 changes-list'>
                                <h4>
                                    {i18n(namespace + 'changes_header') + ':'}
                                </h4>
                                <ol>
                                    {this.renderChangedNodesAmount(nodes.where({pending_addition: true}), 'added_node')}
                                    {this.renderChangedNodesAmount(nodes.where({pending_deletion: true}), 'deleted_node')}
                                </ol>
                                {!isDeploymentImpossible &&
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
                                }
                                {nodes.hasChanges() &&
                                    <a
                                        key='discard-changes'
                                        onClick={_.partial(this.showDialog, dialogs.DiscardNodeChangesDialog)}
                                    >
                                        {i18n('cluster_page.discard_changes')}
                                    </a>
                                }
                            </div>
                        }
                        <div className='col-xs-12 deploy-readiness'>
                            {isDeploymentImpossible &&
                                <div className='informational-block'>
                                    {!!this.props.deploymentErrorTask &&
                                        <controls.InstructionElement
                                            description='unsuccessful_deploy'
                                            explanation='for_more_information_roles'
                                            link='operations.html#troubleshooting'
                                            linkTitle='user_guide'
                                        />
                                    }
                                    {this.state.hasErrors &&
                                        <WarningsBlock
                                            cluster={this.props.cluster}
                                            screen={this.props.parent}
                                            isInvalid={this.state.isInvalid}
                                            alerts={_.pick(this.state.alerts, 'error')}
                                        />
                                    }
                                    {!hasNodes ?
                                        [
                                            <h4>{i18n(namespace + 'new_environment_welcome')}</h4>,
                                            <controls.InstructionElement
                                                description='no_nodes_instruction'
                                                explanation='for_more_information_roles'
                                                link='user-guide.html#add-nodes-ug'
                                                linkTitle='user_guide'
                                            />
                                        ]
                                    :
                                        [
                                            <controls.InstructionElement
                                                description='deployment_cannot_be_started'
                                                explanation='for_more_information_roles'
                                                link='user-guide.html#add-nodes-ug'
                                                linkTitle='user_guide'
                                                wrapperClass='invalid-deploy'
                                            />,
                                            this.state.isInvalid &&
                                                <WarningsBlock
                                                    cluster={this.props.cluster}
                                                    screen={this.props.parent}
                                                    isInvalid={this.state.isInvalid}
                                                    alerts={_.pick(this.state.alerts, 'blocker')}
                                                />
                                        ]
                                    }
                                </div>
                            }
                            {hasNodes &&
                                [
                                    <p>{i18n(namespace + 'note_recommendations')}</p>,
                                    <WarningsBlock
                                        cluster={this.props.cluster}
                                        screen={this.props.parent}
                                        isInvalid={this.state.isInvalid}
                                        alerts={_.pick(this.state.alerts, 'warning')}
                                    />
                                ]
                            }
                            {!hasNodes &&
                                <AddNodesButton cluster={this.props.cluster}/>
                            }
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
        getClusterValue: function(fieldName) {
            var cluster = this.props.cluster,
                release = cluster.get('release'),
                settings = cluster.get('settings');
            switch (fieldName) {
                case 'status':
                    return i18n('cluster.status.' + cluster.get('status'));
                case 'openstack_release':
                    return release.get('name');
                case 'compute':
                    var libvirtSettings = settings.get('common').libvirt_type,
                        compute = libvirtSettings.value,
                        computeLabel = _.find(libvirtSettings.values, {data: compute}).label;
                    computeLabel += (settings.get('common').use_vcenter.value ? ' and VCenter' : '');
                    return computeLabel;
                case 'network':
                    var networkingParams = cluster.get('networkConfiguration').get('networking_parameters'),
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
                default:
                    return cluster.get(fieldName);
            }
        },
        renderClusterInfoFields: function() {
                //isOSTFAvailable = !_.isEmpty(this.props.cluster.get('ostf')) && !this.props.isNew,
                var fields = ['status', 'openstack_release', 'compute', 'network', 'storage_backends'];
            return (
                _.map(fields, function(field, index) {
                    return (
                        <div key={field + index}>
                            <div className='col-xs-6'>
                                <div className='cluster-info-title'>
                                    {i18n(namespace + 'cluster_info_fields.' + field)}
                                </div>
                            </div>
                            <div className='col-xs-6'>
                                <div className='cluster-info-value'>
                                    {this.getClusterValue(field)}
                                </div>
                            </div>
                        </div>
                    );
                }, this)
            );
        },
        renderClusterCapacity: function() {
            var cores = 0,
                hdds = 0,
                rams = 0,
                ns = namespace + 'cluster_info_fields.';
                this.props.cluster.get('nodes').each(function(node) {
                    cores += node.resource('ht_cores');
                    hdds += node.resource('hdd');
                    rams += node.resource('ram');
            }, this);

            return (
                <div className='row capacity-block content-elements'>
                    <div className='title'>{i18n(ns + 'capacity')}</div>
                    <div className='col-xs-12'>
                        <div className='col-xs-4 cpu capacity-item'>
                            <span>{i18n(ns + 'cpu_cores')}</span>
                            <span className='capacity-value pull-right'>{cores}</span>
                        </div>
                        <div className='col-xs-4 hdd capacity-item'>
                            <span>{i18n(ns + 'hdd')}</span>
                            <span className='capacity-value pull-right'>{utils.showDiskSize(hdds)}</span>
                        </div>
                        <div className='col-xs-4 ram capacity-item'>
                            <span>{i18n(ns + 'ram')}</span>
                            <span className='capacity-value pull-right'>{utils.showDiskSize(rams)}</span>
                        </div>
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
            }
        },
        getNumberOfNodesWithStatus: function(field) {
            var nodes = this.props.cluster.get('nodes');
            if (!nodes.length) return 0;
            switch (field) {
                case 'offline':
                    return nodes.where({online: false}).length;
                case 'error':
                    return _.filter(nodes.pluck('error_type')).length;
                case 'pending_addition':
                case 'pending_deletion':
                    return nodes.pluck(field).length;
                case 'operational':
                    return nodes.where({status: 'ready'}).length;
            }
        },
        renderLegend: function(fieldsData, isRole) {
            var result = _.map(fieldsData, function(field) {
                    var numberOfNodes = isRole ? this.getNumberOfNodesWithRole(field) : this.getNumberOfNodesWithStatus(field);
                    return numberOfNodes ?
                        <div key={field}>
                            <div className='col-xs-10'>
                                <div className='cluster-info-title'>
                                    {i18n(namespace + 'cluster_info_fields.' + field)}
                                </div>
                            </div>
                            <div className='col-xs-2'>
                                <div className='cluster-info-value pull-right'>
                                    {numberOfNodes}
                                </div>
                            </div>
                        </div>
                        :
                        null;
                }, this);

            return result;
        },
        renderStatistics: function() {
            var hasNodes = !!this.props.cluster.get('nodes').length,
                fieldRoles = ['total', 'compute', 'controller', 'cinder', 'ceph-osd', 'mongo', 'base-os'],
                fieldStatuses = ['offline', 'error', 'pending_addition', 'operational'];

            return (
                <div className='row statistics-block'>
                    <div className='title'>{i18n(namespace + 'cluster_info_fields.' + 'statistics')}</div>
                    {hasNodes ?
                        [
                        <div className='col-xs-6'>
                            <div className='row'>
                                {this.renderLegend(fieldRoles, true)}
                            </div>
                            <AddNodesButton cluster={this.props.cluster} />
                        </div>,
                        <div className='col-xs-6'>
                            <div clasName='row'>
                                {this.renderLegend(fieldStatuses)}
                            </div>
                        </div>
                    ]
                    :
                        <div className='col-xs-12 no-nodes-block'>
                            <p>
                                {i18n(namespace + 'no_nodes_warning_add_them')}
                            </p>
                        </div>
                    }
                </div>
            );
        },
        renameCluster: function() {
            this.setState({isRenaming: true});
        },
        render: function() {
            var cluster = this.props.cluster,
                isNew = this.props.isNew,
                task = cluster.task({group: 'deployment', status: 'running'});
            return (
                <div className='cluster-information'>
                    <div className='row'>
                        <div className='col-xs-6'>
                            <div className='row'>
                                <div className='title'>{i18n(namespace + 'summary')}</div>
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
                                {this.renderClusterInfoFields()}
                                {!isNew &&
                                    <div className='col-xs-12'>
                                        {i18n(namespace + 'healthcheck')}
                                        <a href={'#cluster/' + cluster.id + '/healthcheck'}>
                                            {i18n(namespace + 'healthcheck_tab')}
                                        </a>
                                    </div>
                                }
                                <div className='col-xs-12 dashboard-actions-wrapper'>
                                    <DeleteEnvironmentAction cluster={cluster} />
                                    {!isNew &&
                                        <ResetEnvironmentAction cluster={cluster} task={task} disabled={isNew} />
                                    }
                                </div>
                            </div>
                        </div>
                        <div className='col-xs-6'>
                            {this.renderClusterCapacity()}
                            {this.renderStatistics()}
                        </div>
                    </div>

                </div>
            );
        }
    });

    var AddNodesButton = React.createClass({
        render: function() {
            return (
                <button
                    className='btn btn-success btn-add-nodes'
                    onClick={_.bind(function() {app.navigate('#cluster/' + this.props.cluster.get('id') + '/nodes/add', {trigger: true, replace: true})}, this)}
                >
                    <i className='glyphicon glyphicon-plus' />
                    {i18n(namespace + 'go_to_nodes')}
                </button>
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
                                    title: i18n(namespace + 'rename_error.title'),
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
        handleKeyDown: function(e) {
            if (e.key == 'Enter') {
                e.preventDefault();
                this.applyAction(e);
            }
            if (e.key == 'Escape') {
                e.preventDefault();
                this.props.parent.setState({isRenaming: false});
            }
        },
        render: function() {
            var valueLink = {
                value: this.state.name,
                requestChange: this.handleChange
            };
            return (
                <div className='rename-block'>
                    <div className='action-body' onKeyDownp={this.handleKeyDown}>
                        <input type='text'
                            disabled={this.state.disabled}
                            className={utils.classNames({'form-control': true, error: this.state.error})}
                            maxLength='50'
                            valueLink={valueLink}
                            autoFocus
                        />
                        {this.state.error &&
                            <div className='text-danger'>
                                {this.state.error}
                            </div>
                        }
                    </div>
                </div>
            );
        }
    });

    var ResetEnvironmentAction = React.createClass({
        mixins: [
            componentMixins.backboneMixin('cluster'),
            componentMixins.backboneMixin('task')
        ],
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
            var isLocked = this.props.disabled;
            return (
                <div className='pull-right reset-environment'>
                    <button
                        className='btn reset-environment-btn'
                        onClick={this.applyAction}
                    >
                        {i18n(namespace + 'reset_environment')}
                    </button>
                    <ActionsPopover
                        key='reset-popover'
                        description={!isLocked ? i18n(namespace + 'reset_environment_warning') : i18n(namespace + this.getDescriptionKey())}
                        name='reset'
                        className='reset'
                    />
                </div>
            );
        }
    });

    var ActionsPopover = React.createClass({
        getInitialState: function() {
            return {};
        },
        togglePopover: function() {
            var popoverName = this.props.name;
            return _.memoize(_.bind(function(visible) {
                this.setState(function(previousState) {
                    var nextState = {};
                    var key = popoverName + 'PopoverVisible';
                    nextState[key] = _.isBoolean(visible) ? visible : !previousState[key];
                    return nextState;
                });
            }, this));
        },
        render: function() {
            return (
                <div className='popover-wrapper'>
                    <i
                        key='actions-icon'
                        className='glyphicon glyphicon-question-sign'
                        onClick={this.togglePopover(this.props.name)}
                        ref={this.props.name + 'actions-icon'}
                    >
                    </i>
                    {this.state[this.props.name + 'PopoverVisible'] &&
                        <controls.Popover
                            {...this.props}
                            toggle={this.togglePopover(this.props.name)}
                        >
                            {this.props.description}
                        </controls.Popover>
                    }
                </div>
            );
        }
    });

    var DeleteEnvironmentAction = React.createClass({
        applyAction: function(e) {
            e.preventDefault();
            dialogs.RemoveClusterDialog.show({cluster: this.props.cluster});
        },
        render: function() {
            return (
                <div className='delete-environment pull-left'>
                    <button
                        className='btn delete-environment-btn'
                        onClick={this.applyAction}
                    >
                        {i18n(namespace + 'delete_environment')}
                    </button>
                    <ActionsPopover
                        key='delete-popover'
                        description={i18n(namespace + 'alert_delete')}
                        name='delete'
                        className='delete'
                    />
                </div>
            );
        }
    });

    var PluginsBlock = React.createClass({
        renderRowEntry: function(data, index) {
            return (
                <div className='row'>
                    {this.renderEntry(data[index])}
                    {!_.isUndefined(data[index + 1]) ? this.renderEntry(data[index + 1]) : <div className='col-xs-6'></div>}
                </div>
            );
        },
        renderEntry: function(entry) {
            return (
                <div className='col-xs-6 plugin-entry' key={entry.title}>
                    <div className='title'>{entry.title}</div>
                    <div className='description'>{entry.description}</div>
                    <a className='link' href={entry.url}>{entry.url}</a>
                </div>
            );
        },
        getHorizonData: function() {
            var task = this.props.cluster.task({group: 'deployment', status: ['ready', 'error']});
            if (!task) return null;
            var delimited = task.get('message').split('\n\n'),
                summary = delimited.shift(),
                linkToHorizon = _.filter(summary.split(' '), function(entry) {return _.startsWith(entry, 'http')});
            return {
                title: 'Horizon',
                description: _.trimRight(summary, linkToHorizon),
                url: linkToHorizon
            };
        },
        render: function() {
            var pluginsData = [];
            pluginsData.push(this.getHorizonData());
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

            pluginsData = _.compact(_.union(pluginsData, demoData));

            return (
                <div>
                    {_.map(pluginsData, function(dashboardEntry, index) {
                        if (index % 2 == 0) return this.renderRowEntry(pluginsData, index);
                    }, this)}
                </div>
            );
        }
    });

    return DashboardTab;
});
