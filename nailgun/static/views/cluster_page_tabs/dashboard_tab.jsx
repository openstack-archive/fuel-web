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
                renderOn: 'update change'
            }),
            componentMixins.backboneMixin({
                modelOrCollection: function(props) {return props.cluster.get('nodes');},
                renderOn: 'update change'
            }),
            componentMixins.backboneMixin('cluster', 'change'),
            componentMixins.pollingMixin(20, true)
        ],
        fetchData: function() {
            return this.props.cluster.get('nodes').fetch();
        },
        getTitle: function() {
            var title = 'title_new',
                cluster = this.props.cluster;
            if (cluster.get('nodes').length) {
                title = 'title_ready';
            }
            if (cluster.get('status') != 'new') {
                title = null;
            }
            if (cluster.task({group: 'deployment', status: 'running'})) {
                title = 'deploy_progress';
            }
            if (cluster.task({group: 'deployment', status: 'error'})) {
                title = 'title_error';
            }
            return title;
        },
        renderTitle: function(title) {
            return (
                <div className='title'>
                    {i18n(namespace + title)}
                </div>
            );
        },
        render: function() {
            var cluster = this.props.cluster,
                release = cluster.get('release'),
                nodes = cluster.get('nodes'),
                clusterStatus = cluster.get('status'),
                hasNodes = !!nodes.length,
                isNew = clusterStatus == 'new',
                isOperational = clusterStatus == 'operational',
                title = this.getTitle(),
                runningDeploymentTask = cluster.task({group: 'deployment', status: 'running'}),
                failedDeploymentTask = cluster.task({group: 'deployment', status: 'error'}),
                stopDeploymentTask = cluster.task({name: 'stop_deployment'}),
                hasOfflineNodes = nodes.any({online: false}),
                resetDeploymentTask = cluster.task({name: 'reset_environment'}),
                isDeploymentPossible = cluster.isDeploymentPossible();

            return (
                <div>
                    {failedDeploymentTask && !!title &&
                        <div className='row'>
                            {this.renderTitle(title)}
                        </div>
                    }
                    {!runningDeploymentTask &&
                        [
                            (failedDeploymentTask || stopDeploymentTask || hasOfflineNodes || resetDeploymentTask || isOperational) &&
                                <DeploymentResult cluster={cluster} />,
                            isOperational && <HorizonBlock cluster={cluster} />
                        ]
                    }
                    {release.get('state') == 'unavailable' &&
                        <div className='alert alert-warning'>
                            {i18n('cluster_page.unavailable_release', {name: release.get('name')})}
                        </div>
                    }
                    {cluster.get('is_customized') &&
                        <div className='alert alert-warning'>
                            {i18n('cluster_page.cluster_was_modified_from_cli')}
                        </div>
                    }
                    {/* @FIXME (morale): !hasNodes condition is not clear here
                     * - it requires decoupling DeployReadinessBlock component */}
                    {(isDeploymentPossible || !hasNodes) &&
                        <div className='row'>
                            {!!title && !failedDeploymentTask && hasNodes &&
                                this.renderTitle(title)
                            }
                            <DeployReadinessBlock
                                cluster={cluster}
                                deploymentErrorTask={failedDeploymentTask}
                                selectNodes={this.props.selectNodes}
                            />
                        </div>
                    }
                    {runningDeploymentTask &&
                        <DeploymentInProgressControl
                            cluster={cluster}
                            task={runningDeploymentTask}
                        />
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

    var HorizonBlock = React.createClass({
        render: function() {
            var cluster = this.props.cluster,
                horizonLinkProtocol = cluster.get('settings').get('public_ssl.horizon.value') ? 'https://' : 'http://';
            return (
                <div className='row plugins-block'>
                    <div className='col-xs-12 plugin-entry horizon'>
                        <div className='title'>{i18n(namespace + 'horizon')}</div>
                        <div className='description'>{i18n(namespace + 'horizon_description')}</div>
                        <a
                            className='btn btn-success'
                            target='_blank'
                            href={horizonLinkProtocol + cluster.get('networkConfiguration').get('public_vip')}
                        >
                            {i18n(namespace + 'go_to_horizon')}
                        </a>
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
            var task = this.props.task,
                taskName = task.get('name'),
                isInfiniteTask = task.isInfinite(),
                taskProgress = task.get('progress'),
                stoppableTask = task.isStoppableTask();
            return (
                <div className='row'>
                    <div className='col-xs-12'>
                        <div className='deploy-block'>
                            <div className={'deploy-process ' + this.props.taskName}>
                                <div className='task-title'>
                                    <strong>
                                        {i18n(namespace + 'current_task') + ' '}
                                    </strong>
                                    {i18n('cluster_page.' + taskName) + '...'}
                                </div>
                                <controls.ProgressBar
                                    progress={!isInfiniteTask && taskProgress}
                                    wrapperClassName={isInfiniteTask ? '' : 'has-progress'}
                                />
                                {stoppableTask &&
                                    <controls.Tooltip text={i18n('cluster_page.stop_deployment_button')}>
                                        <button
                                            className='btn btn-danger btn-xs pull-right stop-deployment-btn'
                                            onClick={_.partial(this.showDialog, dialogs.StopDeploymentDialog)}
                                        >
                                            {i18n(namespace + 'stop')}
                                        </button>
                                    </controls.Tooltip>
                                }
                            </div>
                        </div>
                    </div>
                </div>
            );
        }
    });

    var WarningsBlock = React.createClass({
        ns: 'dialog.display_changes.',
        render: function() {
            var result = {
                    danger: _.union(this.props.alerts.blocker, this.props.alerts.error),
                    warning: this.props.alerts.warning
                };
            return (
                <div className='warnings-block'>
                    <div className='validation-result'>
                        {
                            _.map(['danger', 'warning'], function(severity) {
                                if (_.isEmpty(result[severity]) || (!this.props.cluster.get('nodes').length && severity == 'warning')) return null;
                                return (
                                    <ul key={severity} className={severity}>
                                        {result[severity].map(function(line, index) {
                                            return (<li key={severity + index}>
                                                {line}
                                            </li>);
                                        })}
                                    </ul>
                                );
                            }, this)
                        }
                    </div>
                </div>
            );
        }
    });

    var DeploymentResult = React.createClass({
        dismissTaskResult: function() {
            var task = this.props.cluster.task({group: 'deployment'});
            if (task) task.destroy();
        },
        render: function() {
            var task = this.props.cluster.task({group: 'deployment', status: ['ready', 'error']});
            if (!task) return null;
            var error = task.match({status: 'error'}),
                delimited = task.escape('message').split('\n\n'),
                summary = delimited.shift(),
                details = delimited.join('\n\n'),
                warning = _.contains(['reset_environment', 'stop_deployment'], task.get('name')),
                classes = {
                    alert: true,
                    'alert-warning': warning,
                    'alert-danger': !warning && error,
                    'alert-success': !warning && !error
                };

            return (
                <div className={utils.classNames(classes)}>
                    <button className='close' onClick={this.dismissTaskResult}>&times;</button>
                    <strong>{i18n('common.' + (error ? 'error' : 'success'))}</strong>
                    <br />
                    <span dangerouslySetInnerHTML={{__html: utils.urlify(summary)}} />
                    {details &&
                        <div className='task-result-details'>
                            <pre dangerouslySetInnerHTML={{__html: utils.urlify(details)}} />
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
                        <a href={link} target='_blank'>
                            {i18n(namespace + labelKey)}
                        </a>
                    </span>
                </div>
            );
        },
        render: function() {
            var isMirantisIso = _.contains(app.version.get('feature_groups'), 'mirantis');
            return (
                <div className='row content-elements'>
                    <div className='title'>{i18n(namespace + 'documentation')}</div>
                    <div className='col-xs-12'>
                        <p>
                            {i18n(namespace + 'documentation_description')}
                        </p>
                    </div>
                    <div className='documentation col-xs-12'>
                        {isMirantisIso ?
                            [
                                this.renderDocumentationLinks('https://www.mirantis.com/openstack-documentation/', 'mos_documentation'),
                                this.renderDocumentationLinks(utils.composeDocumentationLink('plugin-dev.html#plugin-dev'), 'plugin_documentation'),
                                this.renderDocumentationLinks('https://software.mirantis.com/mirantis-openstack-technical-bulletins/', 'technical_bulletins')
                            ]
                        :
                            [
                                this.renderDocumentationLinks('http://docs.openstack.org/', 'openstack_documentation'),
                                this.renderDocumentationLinks('https://wiki.openstack.org/wiki/Fuel/Plugins', 'plugin_documentation')
                            ]
                        }
                    </div>
                </div>
            );
        }
    });

    // @FIXME (morale): this component is written in a bad pattern of 'monolith' component
    // it should be refactored to provide proper logics separation and decoupling
    var DeployReadinessBlock = React.createClass({
        mixins: [
            // this is needed to somehow handle the case when verification is in progress and user pressed Deploy
            componentMixins.backboneMixin({
                modelOrCollection: function(props) {
                    return props.cluster.get('tasks');
                },
                renderOn: 'update change'
            }),
            componentMixins.backboneMixin('cluster', 'change')
        ],
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
                    return !vcenter.isValid() && {
                        blocker: [
                            (<span key='vcenter'>{i18n('vmware.has_errors') + ' '}
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
                        (<span key='invalid_settings'>
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
                        return [role.get('name'), role.checkLimits(configModels, cluster.get('nodes'))];
                    })),
                    limitRecommendations = _.zipObject(validRoleModels.map(function(role) {
                        return [role.get('name'), role.checkLimits(configModels, cluster.get('nodes'), true, ['recommended'])];
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
            Dialog.show({cluster: this.props.cluster})
                .done(this.props.selectNodes);
        },
        renderChangedNodesAmount: function(nodes, dictKey) {
            var areNodesPresent = !!nodes.length;
            return (areNodesPresent &&
                <li className='changes-item' key={dictKey}>
                    {i18n('dialog.display_changes.' + dictKey, {count: nodes.length})}
                </li>
            );
        },
        render: function() {
            var cluster = this.props.cluster,
                nodes = cluster.get('nodes'),
                hasNodes = !!nodes.length,
                alerts = this.validate(cluster),
                isDeploymentPossible = cluster.isDeploymentPossible() && !alerts.blocker.length,
                isVMsProvisioningAvailable = cluster.get('nodes').any(function(node) {
                    return node.get('pending_addition') && node.hasRole('virt');
                });

            return (
                <div className='col-xs-12 deploy-readiness'>
                    <div className='deploy-block'>
                        <div className='row'>
                            {hasNodes &&
                                <div className='col-xs-12 changes-list'>
                                    <h4>
                                        {i18n(namespace + 'changes_header') + ':'}
                                    </h4>
                                    <ul>
                                        {this.renderChangedNodesAmount(nodes.where({pending_addition: true}), 'added_node')}
                                        {this.renderChangedNodesAmount(nodes.where({pending_deletion: true}), 'deleted_node')}
                                    </ul>
                                    {isVMsProvisioningAvailable ?
                                        (
                                            <button
                                                key='provision-vms'
                                                className='btn btn-primary deploy-btn'
                                                onClick={_.partial(this.showDialog, dialogs.ProvisionVMsDialog)}
                                            >
                                                <div className='deploy-icon'></div>
                                                {i18n('cluster_page.provision_vms')}
                                            </button>
                                        )
                                    :
                                        isDeploymentPossible &&
                                            (
                                                <button
                                                    key='deploy-changes'
                                                    className='btn btn-primary deploy-btn'
                                                    onClick={_.partial(this.showDialog, dialogs.DeployChangesDialog)}
                                                >
                                                    <div className='deploy-icon'></div>
                                                    {i18n('cluster_page.deploy_changes')}
                                                </button>
                                            )
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
                                {!isDeploymentPossible &&
                                    <div className='informational-block'>
                                        {!!this.props.deploymentErrorTask &&
                                            <InstructionElement
                                                description='unsuccessful_deploy'
                                                explanation='for_more_information_roles'
                                                link='operations.html#troubleshooting'
                                                linkTitle='user_guide'
                                            />
                                        }
                                        {!hasNodes &&
                                            [
                                                <h4 key='welcome'>{i18n(namespace + 'new_environment_welcome')}</h4>,
                                                <InstructionElement
                                                    key='no_nodes_instruction'
                                                    description='no_nodes_instruction'
                                                    explanation='for_more_information_roles'
                                                    link='user-guide.html#add-nodes-ug'
                                                    linkTitle='user_guide'
                                                />
                                            ]
                                        }
                                    </div>
                                }
                                {hasNodes &&
                                    [
                                        cluster.needsRedeployment() &&
                                            <div className='invalid'>
                                                {i18n('dialog.display_changes.redeployment_needed')}
                                            </div>,
                                        !_.isEmpty(alerts.blocker) &&
                                            [
                                                <InstructionElement
                                                    key='deployment_cannot_be_started'
                                                    description='deployment_cannot_be_started'
                                                    explanation='for_more_information_roles'
                                                    link='user-guide.html#add-nodes-ug'
                                                    linkTitle='user_guide'
                                                    wrapperClass='invalid'
                                                />,
                                                <WarningsBlock
                                                    key='blocker'
                                                    cluster={cluster}
                                                    alerts={_.pick(alerts, 'blocker')}
                                                />
                                            ],
                                        !_.isEmpty(alerts.error) &&
                                            <WarningsBlock
                                                key='error'
                                                cluster={cluster}
                                                alerts={_.pick(alerts, 'error')}
                                            />,
                                        !_.isEmpty(alerts.warning) &&
                                            [
                                                <p>{i18n(namespace + 'note_recommendations')}</p>,
                                                <WarningsBlock
                                                    key='warning'
                                                    cluster={cluster}
                                                    alerts={_.pick(alerts, 'warning')}
                                                />
                                            ]
                                    ]
                                }
                                {!hasNodes &&
                                    <AddNodesButton cluster={cluster}/>
                                }
                            </div>
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
                    computeLabel += (settings.get('common').use_vcenter.value ? ' ' + i18n(namespace + 'and_vcenter') : '');
                    return computeLabel;
                case 'network':
                    var networkingParam = cluster.get('networkConfiguration').get('networking_parameters'),
                        networkManager = networkingParam.get('net_manager');
                    if (cluster.get('net_provider') == 'nova_network') {
                        return i18n(namespace + 'nova_with') + ' ' + networkManager + ' ' + i18n(namespace + 'manager');
                    }
                    return (i18n('common.network.neutron_' + networkingParam.get('segmentation_type')));
                case 'storage_backends':
                    return _.map(_.where(settings.get('storage'), {value: true}), 'label').join('\n') ||
                        i18n(namespace + 'no_storage_enabled');
                default:
                    return cluster.get(fieldName);
            }
        },
        renderClusterInfoFields: function() {
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
                                <div className={'cluster-info-value ' + field}>
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
                ram = 0,
                ns = namespace + 'cluster_info_fields.';

            this.props.cluster.get('nodes').each(function(node) {
                cores += node.resource('ht_cores');
                hdds += node.resource('hdd');
                ram += node.resource('ram');
            }, this);

            return (
                <div className='row capacity-block content-elements'>
                    <div className='title'>{i18n(ns + 'capacity')}</div>
                    <div className='col-xs-12 capacity-items'>
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
                            <span className='capacity-value pull-right'>{utils.showDiskSize(ram)}</span>
                        </div>
                    </div>
                </div>
            );
        },
        getNumberOfNodesWithRole: function(field) {
            var nodes = this.props.cluster.get('nodes');
            if (!nodes.length) return 0;
            if (field == 'total') return nodes.length;
            return _.filter(nodes.invoke('hasRole', field)).length;
        },
        getNumberOfNodesWithStatus: function(field) {
            var nodes = this.props.cluster.get('nodes');
            if (!nodes.length) return 0;
            switch (field) {
                case 'offline':
                    return nodes.where({online: false}).length;
                case 'error':
                    return nodes.where({status: 'error'}).length;
                case 'pending_addition':
                case 'pending_deletion':
                    var searchObject = {};
                    searchObject[field] = true;
                    return nodes.where(searchObject).length;
                default:
                    return nodes.where({status: field}).length;
            }
        },
        renderLegend: function(fieldsData, isRole) {
            var result = _.map(fieldsData, function(field) {
                var numberOfNodes = isRole ? this.getNumberOfNodesWithRole(field) : this.getNumberOfNodesWithStatus(field);
                    return numberOfNodes ?
                        <div key={field}>
                            <div className='col-xs-10'>
                                <div className='cluster-info-title'>
                                    {isRole && field != 'total' ?
                                        this.props.cluster.get('roles').find({name: field}).get('label')
                                    :
                                        field == 'total' ?
                                            i18n(namespace + 'cluster_info_fields.total')
                                        :
                                            i18n('cluster_page.nodes_tab.node.status.' + field,
                                                {os: this.props.cluster.get('release').get('operating_system') || 'OS'})
                                    }
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
                fieldRoles = _.union(['total'], this.props.cluster.get('roles').pluck('name')),
                fieldStatuses = ['offline', 'error', 'pending_addition', 'pending_deletion', 'ready', 'provisioned',
                    'provisioning', 'deploying', 'removing'];
            return (
                <div className='row statistics-block'>
                    <div className='title'>{i18n(namespace + 'cluster_info_fields.statistics')}</div>
                    {hasNodes ?
                        [
                            <div className='col-xs-6' key='roles'>
                                <div className='row'>
                                    {this.renderLegend(fieldRoles, true)}
                                </div>
                                <AddNodesButton
                                    cluster={this.props.cluster}
                                />
                            </div>,
                            <div className='col-xs-6' key='statuses'>
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
        startClusterRenaming: function() {
            this.setState({isRenaming: true});
        },
        endClusterRenaming: function() {
            this.setState({isRenaming: false});
        },
        render: function() {
            var cluster = this.props.cluster,
                isNew = this.props.isNew,
                task = cluster.task({group: 'deployment', status: 'running'}),
                runningDeploymentTask = cluster.task({group: 'deployment', status: 'running'});
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
                                            startRenaming={this.startClusterRenaming}
                                            endRenaming={this.endClusterRenaming}
                                        />
                                    :
                                        <div className='cluster-info-value name' onClick={this.startClusterRenaming}>
                                            <a>
                                                {cluster.get('name')}
                                            </a>
                                            <i className='glyphicon glyphicon-pencil'></i>
                                        </div>
                                    }
                                </div>
                                {this.renderClusterInfoFields()}
                                {!isNew &&
                                    <div className='col-xs-12 go-to-healthcheck'>
                                        {i18n(namespace + 'healthcheck')}
                                        <a href={'#cluster/' + cluster.id + '/healthcheck'}>
                                            {i18n(namespace + 'healthcheck_tab')}
                                        </a>
                                    </div>
                                }
                                <div className='col-xs-12 dashboard-actions-wrapper'>
                                    <DeleteEnvironmentAction cluster={cluster} disabled={runningDeploymentTask} />
                                    {!isNew &&
                                        <ResetEnvironmentAction cluster={cluster} task={task} disabled={runningDeploymentTask} />
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
            var disabled = !!this.props.cluster.task({group: 'deployment', status: 'running'});
            return (
                    <a
                        className='btn btn-success btn-add-nodes'
                        href={'#cluster/' + this.props.cluster.id + '/nodes/add'}
                        disabled={disabled}
                    >
                        <i className='glyphicon glyphicon-plus' />
                        {i18n(namespace + 'go_to_nodes')}
                    </a>
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
                            this.setState({disabled: false});
                            this.props.endRenaming();
                        }, this));
                } else if (cluster.validationError) {
                    this.setState({error: cluster.validationError.name});
                }
            } else {
                this.props.endRenaming();
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
                this.props.endRenaming();
            }
        },
        render: function() {
            var valueLink = {
                value: this.state.name,
                requestChange: this.handleChange
            };
            return (
                <div className='rename-block'>
                    <div className='action-body' onKeyDown={this.handleKeyDown}>
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
                        className='btn reset-environment-btn btn-default'
                        onClick={this.applyAction}
                        disabled={isLocked}
                    >
                        {i18n(namespace + 'reset_environment')}
                    </button>
                    <controls.Tooltip
                        key='reset-tooltip'
                        placement='right'
                        text={!isLocked ? i18n(namespace + 'reset_environment_warning') : i18n(namespace + this.getDescriptionKey())}
                    >
                        <i className='glyphicon glyphicon-info-sign' />
                    </controls.Tooltip>
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
                        className='btn delete-environment-btn btn-default'
                        onClick={this.applyAction}
                        disabled={this.props.isLocked}
                    >
                        {i18n(namespace + 'delete_environment')}
                    </button>
                    <controls.Tooltip
                        key='delete-tooltip'
                        placement='right'
                        text={i18n(namespace + 'alert_delete')}
                    >
                        <i className='glyphicon glyphicon-info-sign' />
                    </controls.Tooltip>
                </div>
            );
        }
    });

    var InstructionElement = React.createClass({
        render: function() {
            var link = utils.composeDocumentationLink(this.props.link),
                classes = {
                    instruction: true
                };
            classes[this.props.wrapperClass] = !!this.props.wrapperClass;
            return (
                <div className={utils.classNames(classes)}>
                    {i18n(namespace + this.props.description) + ' '}
                    <a href={link} target='_blank'>{i18n(namespace + this.props.linkTitle)}</a>
                    {this.props.explanation && ' ' + i18n(namespace + this.props.explanation)}
                </div>
            );
        }
    });

    return DashboardTab;
});
