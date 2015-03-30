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
    'd3',
    'jsx!views/dialogs',
    'jsx!component_mixins',
    'jsx!views/pie_chart'
],
function(_, i18n, React, utils, models, dispatcher, d3, dialogs, componentMixins, PieChart) {
    'use strict';

    var releases = new models.Releases();

    var DashboardTab = React.createClass({
        isNew: function() {
            return this.props.cluster.get('status') == 'new' || !!this.props.task;
        },
        render: function() {
            var cluster = this.props.cluster,
                nodes = cluster.get('nodes'),
                hasNodes = !!nodes.length;
            return (
                <div className='row'>
                    <div className='title'>
                        {i18n('cluster_page.dashboard_tab.title_new')}
                    </div>
                    <div>
                        {hasNodes ?
                            <div>
                                <ChangesBlock
                                    cluster={this.props.cluster}
                                />
                            </div>
                        :
                            <div className='col-xs-12'>
                                <div className='text-warning alert-warning section-wrapper no-nodes'>
                                    <p>
                                        <span>
                                            <i className='glyphicon glyphicon-warning-sign' />
                                            <span>{i18n('cluster_page.dashboard_tab.no_nodes_warning')}</span>
                                        </span>
                                        <a
                                            className='btn btn-success btn-add-nodes pull-right'
                                            href={'/#cluster/' + this.props.cluster.id + '/nodes/add'}
                                        >
                                            <i className='glyphicon glyphicon-plus' />
                                            {i18n('cluster_page.nodes_tab.node_management_panel.add_nodes_button')}
                                        </a>
                                    </p>
                                </div>
                            </div>
                        }
                        <DocumentationLinks />
                        <ClusterInfo
                            cluster={this.props.cluster}
                        />
                        <Actions
                            {...this.props}
                            isNew={this.isNew()}
                        />
                    </div>
                </div>
            );
        }
    });

    var ChangesBlock = React.createClass({
        renderChangedNodesAmount: function(nodes, dictKey) {
            var areNodesPresent = !!nodes.length;
            return (areNodesPresent &&
                <div>
                    {++this.counter + '. ' +i18n('dialog.display_changes.' + dictKey, {count: nodes.length})}
                </div>
            );
        },
        showDialog: function(Dialog) {
            Dialog.show({cluster: this.props.cluster});
        },
        onDeployRequest: function() {
            this.showDialog(dialogs.DeployChangesDialog);
        },
        render: function() {
            var cluster = this.props.cluster,
                nodes = cluster.get('nodes'),
                isDeploymentImpossible = cluster.get('release').get('state') == 'unavailable' ||
                    (!cluster.get('nodes').hasChanges() && !cluster.needsRedeployment());
            this.counter = 0;
            return (
                <div className='col-xs-12 changes-list'>
                    <div className='row'>
                        <div className='col-xs-12'>
                            <p className='changes-header'>
                                {i18n('cluster_page.dashboard_tab.changes_header') + ':'}
                            </p>
                            {this.renderChangedNodesAmount(nodes.where({pending_addition: true}), 'added_node')}
                            {this.renderChangedNodesAmount(nodes.where({pending_deletion: true}), 'deleted_node')}
                        </div>
                        <div className='col-xs-12 deploy-control'>
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
                                    href='#'
                                    key='discard-changes'
                                    onClick={_.partial(this.showDialog, dialogs.DiscardNodeChangesDialog)}
                                >
                                    {i18n('cluster_page.discard_changes')}
                                </a>
                            }
                        </div>
                    </div>
                </div>
            );
        }
    });

    var DocumentationLinks = React.createClass({
        renderDocumentationLink: function(link, labelKey) {
            var ns = 'cluster_page.dashboard_tab.';
            return (
                <div className='row'>
                    <div className='col-xs-12'>
                         <span>
                            <i className='glyphicon glyphicon-list-alt' />
                            <a href={link} >
                                {i18n(ns + labelKey)}
                            </a>
                        </span>
                    </div>
                </div>
            );
        },
        render: function() {
            return (
                <div className='col-xs-12'>
                    <div className='section-wrapper documentation'>
                        {this.renderDocumentationLink('https://www.mirantis.com/openstack-documentation/', 'mos_documentation')}
                        {this.renderDocumentationLink('https://wiki.openstack.org/wiki/Fuel/Plugins', 'plugin_documentation')}
                        {this.renderDocumentationLink('https://software.mirantis.com/mirantis-openstack-technical-bulletins/', 'technical_bulletins')}
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
                    }
                    else {
                        return 'Neutron with ' + networkingParams.get('segmentation_type').toUpperCase();
                    }
                case 'storage_backends':
                    var volumesLVM = settings.get('storage').volumes_lvm,
                        volumesCeph = settings.get('storage').volumes_ceph;
                    return volumesLVM.value && volumesLVM.label || volumesCeph.value && volumesCeph.label;
                case 'healthcheck_status':
                    //@todo
                    //debugger;
                    var ostfStatus = cluster.get('status') == 'new' && 'Unavailable';
                    return ostfStatus;
                default:
                    return cluster.get(fieldName)
            }
        },
        renderClusterInfoFields: function() {
            var namespace = this.props.namespace,
                fields = ['openstack_release', 'operating_system', 'compute', 'network', 'storage_backends',
                    'healthcheck_status'];
            return (
                <div className='col-xs-12'>
                    {_.map(fields, function(field) {
                        return (
                            <div className='row'>
                                <div className='col-xs-6'>
                                    <div className='cluster-info-title'>
                                        {i18n(namespace + field)}
                                    </div>
                                </div>
                                <div className='col-xs-6'>
                                    <div className='cluster-info-value'>
                                        {this.getClusterValue(field)}
                                    </div>
                                </div>
                            </div>
                        );
                    }, this)}
                </div>
            );
        },
        renderClusterCapacity : function() {
            var cores = 0,
                hdds = 0,
                rams = 0,
                namespace = this.props.namespace;
                this.props.cluster.get('nodes').each(function(node) {
                    cores += node.resource('ht_cores');
                    hdds += node.resource('hdd');
                    rams += node.resource('ram');
            }, this);

            this.props.cluster.get('nodes').first().resource('ht_cores');
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
            debugger;
            return field;
            switch (field) {
                case 'compute':
                case 'controller':
                case 'storage':
                    break;
                case 'total':
                    break;
                case 'offline':
                    break;
                case 'error':
                    break;
            }
        },
        renderStatistics: function() {
            var namespace = this.props.namespace,
                fields = ['total', 'compute', 'controller', 'storage', 'offline', 'error'];

            debugger;
            return (
                <div className='row statistics-block'>
                    <div className='title'>{i18n(namespace + 'statistics')}</div>
                    <div className='col-xs-6'>
                        {_.map(fields, function(field) {
                            return (
                                <div className='row'>
                                    <div className='col-xs-6'>
                                        <div className='cluster-info-title'>
                                            {i18n(namespace + field)}
                                        </div>
                                    </div>
                                    <div className='col-xs-6'>
                                        <div className='cluster-info-value'>
                                           {this.getNumberOfNodesWithRole(field)}
                                        </div>
                                    </div>
                                </div>
                            );
                        }, this)}
                    </div>
                    <div className='col-xs-6 chart'>
                    </div>
                </div>
            );
        },
        renameCluster: function() {
            this.setState({isRenaming: true});
        },
        render: function() {
            var namespace = 'cluster_page.dashboard_tab.';
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
                                                    cluster={this.props.cluster}
                                                    parent={this}
                                                />
                                            :
                                                <div className='cluster-info-value name' onClick={this.renameCluster}>
                                                    <a>
                                                        {this.props.cluster.get('name')}
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
                        <div className='row'>

                        </div>
                    </div>
                </div>
            );
        }
    });
    
    var Actions = React.createClass({
        mixins: [
            componentMixins.backboneMixin('cluster'),
            componentMixins.backboneMixin({modelOrCollection: function(props) {
                return props.cluster.get('tasks');
            }}),
            componentMixins.backboneMixin({modelOrCollection: function(props) {
                return props.cluster.task({group: 'deployment', status: 'running'});
            }})
        ],
        render: function() {
            var cluster = this.props.cluster,
                task = cluster.task({group: 'deployment', status: 'running'}),
                isExperimental = _.contains(app.version.get('feature_groups'), 'experimental'),
                isNew = this.props.isNew;
            return (
                <div className='col-xs-12'>
                    <div className='section-wrapper'>
                        <div className='title'>{i18n('cluster_page.dashboard_tab.actions_title')}</div>
                        <div className='row environment-actions'>

                            {!isNew &&
                                <ResetEnvironmentAction cluster={cluster} task={task} />
                            }
                            <DeleteEnvironmentAction cluster={cluster}/>
                            {isExperimental && !isNew &&
                                <UpdateEnvironmentAction cluster={cluster} releases={releases} task={task}/>
                            }
                        </div>
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
                    <div className='panel panel-default'>
                        <div className='panel-heading font-bold'>{this.props.title}</div>
                        <div className='panel-body'>
                            {this.props.children}
                        </div>
                    </div>
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
            }
            else {
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
                               valueLink={valueLink}/>
                        {this.state.error &&
                        <div className='text-danger'>
                            {this.state.error}
                        </div>
                        }
                    </div>
                    <button
                        className='btn btn-success rename-environment-btn'
                        onClick={this.applyAction}
                        disabled={this.state.disabled}>
                        {i18n('common.rename_button')}
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
        isLocked: function() {
            return this.props.cluster.get('status') == 'new' || !!this.props.task;
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
            var isLocked = this.isLocked();
            return (
                <Action title={i18n('cluster_page.dashboard_tab.reset_environment')}>
                    <div className='action-body'>
                        <div className='action-item-description'>
                            {i18n('cluster_page.dashboard_tab.' + this.getDescriptionKey())}
                        </div>
                        {!isLocked && <div className='text-danger action-item-description'>{i18n('cluster_page.dashboard_tab.reset_environment_warning')}</div>}
                    </div>
                    <button
                        className='btn btn-danger reset-environment-btn'
                        onClick={this.applyAction}
                        disabled={isLocked}>
                        {i18n('common.reset_button')}
                    </button>
                </Action>
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
                <Action title={i18n('cluster_page.dashboard_tab.delete_environment')}>
                    <div className='action-body'>
                        <div className='action-item-description text-danger'>
                            {i18n('cluster_page.dashboard_tab.alert_delete')}
                        </div>
                    </div>
                    <button
                        className='btn btn-danger delete-environment-btn'
                        onClick={this.applyAction}>
                        {i18n('common.delete_button')}
                    </button>
                </Action>
            );
        }
    });

    var UpdateEnvironmentAction = React.createClass({
        mixins: [
            React.addons.LinkedStateMixin,
            componentMixins.backboneMixin('cluster'),
            componentMixins.backboneMixin('releases'),
            componentMixins.backboneMixin('task')
        ],
        getInitialState: function() {
            return {pendingReleaseId: null};
        },
        getAction: function() {
            return this.props.cluster.get('status') == 'update_error' ? 'rollback' : 'update';
        },
        isLocked: function() {
            return !_.contains(['operational', 'update_error'], this.props.cluster.get('status')) || !!this.props.task;
        },
        componentWillReceiveProps: function() {
            this.setState({pendingReleaseId: this.getPendingReleaseId()});
        },
        componentDidMount: function() {
            var releases = this.props.releases;
            if (!releases.length) {
                releases.fetch().done(_.bind(function() {
                    this.setState({pendingReleaseId: this.getPendingReleaseId()});
                }, this));
            }
        },
        updateEnvironmentAction: function() {
            var cluster = this.props.cluster,
                isDowngrade = _.contains(cluster.get('release').get('can_update_from_versions'), this.props.releases.findWhere({id: parseInt(this.state.pendingReleaseId) || cluster.get('release_id')}).get('version'));
            dialogs.UpdateEnvironmentDialog.show({
                cluster: cluster,
                action: this.getAction(),
                isDowngrade: isDowngrade,
                pendingReleaseId: this.state.pendingReleaseId
            });
        },
        retryUpdateEnvironmentAction: function() {
            var cluster = this.props.cluster;
            dialogs.UpdateEnvironmentDialog.show({cluster: cluster, pendingReleaseId: cluster.get('pending_release_id'), action: 'retry'});
        },
        rollbackEnvironmentAction: function() {
            dialogs.UpdateEnvironmentDialog.show({cluster: this.props.cluster, action: 'rollback'});
        },
        getPendingReleaseId: function() {
            var release = _.find(releases.models, this.isAvailableForUpdate, this);
            if (release) {return release.id;}
            return null;
        },
        isAvailableForUpdate: function(release) {
            var cluster = this.props.cluster,
                currentRelease = cluster.get('release');
            return (_.contains(currentRelease.get('can_update_from_versions'), release.get('version')) || _.contains(release.get('can_update_from_versions'), currentRelease.get('version'))) &&
                release.get('operating_system') == currentRelease.get('operating_system') &&
                release.id != cluster.get('release_id');
        },
        getDescriptionKey: function() {
            var cluster = this.props.cluster,
                action = this.getAction(),
                task = this.props.task,
                status = cluster.get('status');
            if (action == 'update' && status == 'operational' && !this.state.pendingReleaseId) return 'no_releases_to_update_message';
            if (action == 'rollback') return 'rollback_warning_message';
            if (task && _.contains(task.get('name'), action)) return 'repeated_' + action + '_disabled';
            if (task) return action + '_disabled_for_deploying_cluster';
            if ((action == 'reset' && status == 'new') || (action == 'update' && status != 'operational')) return action + '_disabled_for_new_cluster';
            return action + '_environment_description';
        },
        render: function() {
            var releases = this.props.releases.filter(this.isAvailableForUpdate, this),
                pendingRelease = this.props.releases.findWhere({id: this.state.pendingReleaseId}) || null,
                action = this.getAction(),
                isLocked = this.isLocked(),
                options = releases.map(function(release) {
                    return <option value={release.id} key={release.id}>{release.get('name') + ' (' + release.get('version') + ')'}</option>;
                }, this);
            return (
                <Action className='col-xs-12 col-md-3 action-update' title={i18n('cluster_page.dashboard_tab.update_environment')}>
                    <div className='action-body'>
                        {(action == 'rollback' || releases) &&
                            <div className='action-item-description'>
                                {i18n('cluster_page.dashboard_tab.' + this.getDescriptionKey(), {release: pendingRelease ? pendingRelease.get('name') + ' (' + pendingRelease.get('version') + ')' : ''})}
                            </div>
                        }
                        {action == 'rollback' &&
                            <div className='action-item-description'>
                                {i18n('cluster_page.dashboard_tab.rollback_message')}
                            </div>
                        }
                        {action == 'update' && !isLocked && this.state.pendingReleaseId &&
                            <select className='form-control' valueLink={this.linkState('pendingReleaseId')}>
                                {options}
                            </select>
                        }
                    </div>
                    {action == 'update' &&
                        <div>
                            <button
                                className='btn btn-success update-environment-btn'
                                onClick={this.updateEnvironmentAction}
                                disabled={_.isNull(this.state.pendingReleaseId) || isLocked}>
                                {i18n('common.update_button')}
                            </button>
                        </div>
                    }
                    {action == 'rollback' &&
                        <div>
                            <button
                                className='btn btn-success retry-update-environment-btn'
                                onClick={this.retryUpdateEnvironmentAction}>
                                {i18n('common.retry_button')}
                            </button>
                            <button
                                className='btn btn-danger rollback-environment-btn'
                                onClick={this.rollbackEnvironmentAction}>
                                {i18n('common.rollback_button')}
                            </button>
                        </div>
                    }
                </Action>
            );
        }
    });

    return DashboardTab;
});
