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
    'jquery',
    'underscore',
    'i18n',
    'backbone',
    'react',
    'utils',
    'models',
    'dispatcher',
    'jsx!views/controls',
    'jsx!views/dialogs'
],
function($, _, i18n, Backbone, React, utils, models, dispatcher, controls, dialogs) {
    'use strict';

    var Node = React.createClass({
        getInitialState: function() {
            return {
                renaming: false,
                actionInProgress: false,
                eventNamespace: 'click.editnodename' + this.props.node.id,
                extendedView: false
            };
        },
        componentWillUnmount: function() {
            $('html').off(this.state.eventNamespace);
        },
        componentDidUpdate: function() {
            if (!this.props.node.get('cluster') && !this.props.checked) this.props.node.set({pending_roles: []}, {assign: true});
        },
        startNodeRenaming: function(e) {
            e.preventDefault();
            $('html').on(this.state.eventNamespace, _.bind(function(e) {
                if ($(e.target).hasClass('node-name-input')) {
                    e.preventDefault();
                } else {
                    this.endNodeRenaming();
                }
            }, this));
            this.setState({renaming: true});
        },
        endNodeRenaming: function() {
            $('html').off(this.state.eventNamespace);
            this.setState({
                renaming: false,
                actionInProgress: false
            });
        },
        getNodeLogsLink: function() {
            var status = this.props.node.get('status'),
                error = this.props.node.get('error_type'),
                options = {type: 'remote', node: this.props.node.id};
            if (status == 'discover') {
                options.source = 'bootstrap/messages';
            } else if (status == 'provisioning' || status == 'provisioned' || (status == 'error' && error == 'provision')) {
                options.source = 'install/anaconda';
            } else if (status == 'deploying' || status == 'ready' || (status == 'error' && error == 'deploy')) {
                options.source = 'install/puppet';
            }
            return '#cluster/' + this.props.cluster.id + '/logs/' + utils.serializeTabOptions(options);
        },
        applyNewNodeName: function(newName) {
            if (newName && newName != this.props.node.get('name')) {
                this.setState({actionInProgress: true});
                this.props.node.save({name: newName}, {patch: true, wait: true}).always(this.endNodeRenaming);
            } else {
                this.endNodeRenaming();
            }
        },
        onNodeNameInputKeydown: function(e) {
            if (e.key == 'Enter') {
                this.applyNewNodeName(this.refs.name.getInputDOMNode().value);
            } else if (e.key == 'Escape') {
                this.endNodeRenaming();
            }
        },
        discardNodeChanges: function() {
            if (this.state.actionInProgress) return;
            this.setState({actionInProgress: true});
            var node = new models.Node(this.props.node.attributes),
                nodeWillBeRemoved = node.get('pending_addition'),
                data = nodeWillBeRemoved ? {cluster_id: null, pending_addition: false, pending_roles: []} : {pending_deletion: false};
            node.save(data, {patch: true})
                .done(_.bind(function() {
                    this.props.cluster.fetchRelated('nodes').done(_.bind(function() {
                        if (!nodeWillBeRemoved) this.setState({actionInProgress: false});
                    }, this));
                    dispatcher.trigger('updateNodeStats networkConfigurationUpdated');
                }, this))
                .fail(function(response) {
                    utils.showErrorDialog({
                        title: i18n('dialog.discard_changes.cant_discard'),
                        response: response
                    });
                });
        },
        removeNode: function(e) {
            e.preventDefault();
            if (this.props.viewMode == 'compact') this.toggleExtendedNodePanel();
            dialogs.RemoveNodeConfirmDialog.show({
                cb: this.removeNodeConfirmed
            });
        },
        removeNodeConfirmed: function() {
            // sync('delete') is used instead of node.destroy() because we want
            // to keep showing the 'Removing' status until the node is truly removed
            // Otherwise this node would disappear and might reappear again upon
            // cluster nodes refetch with status 'Removing' which would look ugly
            // to the end user
            Backbone.sync('delete', this.props.node).then(_.bind(function(task) {
                    dispatcher.trigger('networkConfigurationUpdated updateNodeStats updateNotifications');
                    if (task.status == 'ready') {
                        // Do not send the 'DELETE' request again, just get rid
                        // of this node.
                        this.props.node.trigger('destroy', this.props.node);
                        return;
                    }
                    this.props.cluster.get('tasks').add(new models.Task(task), {parse: true});
                    this.props.node.set('status', 'removing');
                }, this)
            );
        },
        showNodeDetails: function(e) {
            e.preventDefault();
            if (this.state.extendedView) this.toggleExtendedNodePanel();
            dialogs.ShowNodeInfoDialog.show({node: this.props.node});
        },
        sortRoles: function(roles) {
            var preferredOrder = this.props.cluster.get('release').get('roles');
            return roles.sort(function(a, b) {
                return _.indexOf(preferredOrder, a) - _.indexOf(preferredOrder, b);
            });
        },
        toggleExtendedNodePanel: function() {
            var states = this.state.extendedView ? {extendedView: false, renaming: false} : {extendedView: true};
            this.setState(states);
        },
        renderNameControl: function() {
            if (this.state.renaming) return (
                <controls.Input
                    ref='name'
                    type='text'
                    name='node-name'
                    defaultValue={this.props.node.get('name')}
                    inputClassName='form-control node-name-input'
                    disabled={this.state.actionInProgress}
                    onKeyDown={this.onNodeNameInputKeydown}
                    autoFocus
                />
            );
            return (
                <p
                    title={i18n('cluster_page.nodes_tab.node.edit_name')}
                    onClick={!this.state.actionInProgress && this.startNodeRenaming}
                >
                    {this.props.node.get('name') || this.props.node.get('mac')}
                </p>
            );
        },
        renderStatusLabel: function(status) {
            return (
                <span>
                    {i18n('cluster_page.nodes_tab.node.status.' + status, {
                        os: this.props.cluster.get('release').get('operating_system') || 'OS'
                    })}
                </span>
            );
        },
        renderNodeProgress: function(showPercentage) {
            var nodeProgress = this.props.node.get('progress');
            return (
                <div className='progress'>
                    <div className='progress-bar' role='progressbar' style={{width: _.max([nodeProgress, 3]) + '%'}}>
                        {showPercentage && (nodeProgress + '%')}
                    </div>
                </div>
            );
        },
        renderNodeHardwareSummary: function() {
            var node = this.props.node;
            return (
                <div className='node-hardware'>
                    <span>{i18n('node_details.cpu')}: {node.resource('cores') || '0'} ({node.resource('ht_cores') || '?'})</span>
                    <span>{i18n('node_details.hdd')}: {node.resource('hdd') ? utils.showDiskSize(node.resource('hdd')) : '?' + i18n('common.size.gb')}</span>
                    <span>{i18n('node_details.ram')}: {node.resource('ram') ? utils.showMemorySize(node.resource('ram')) : '?' + i18n('common.size.gb')}</span>
                </div>
            );
        },
        renderLogsLink: function(iconRepresentation) {
            return (
                <a className={iconRepresentation ? 'icon icon-logs' : 'btn'} href={this.getNodeLogsLink()}>
                    {!iconRepresentation && i18n('cluster_page.nodes_tab.node.view_logs')}
                </a>
            );
        },
        renderNodeCheckbox: function() {
            return (
                <controls.Input
                    type='checkbox'
                    name={this.props.node.id}
                    checked={this.props.checked}
                    disabled={!this.props.node.isSelectable()}
                    onChange={this.props.mode != 'edit' && this.props.onNodeSelection}
                    wrapperClassName='pull-left'
                />
            );
        },
        renderRemoveButton: function() {
            return (
                <button onClick={this.removeNode} className='btn node-remove-button'>
                    {i18n('cluster_page.nodes_tab.node.remove')}
                </button>
            );
        },
        renderRoleList: function(roles) {
            return (
                <ul className='clearfix'>
                    {_.map(roles, function(role) {
                        return (
                            <li
                                key={this.props.node.id + role}
                                className={utils.classNames({'text-success': !this.props.node.get('roles').length})}
                            >
                                {role}
                            </li>
                        );
                    }, this)}
                </ul>
            );
        },
        showDeleteNodesDialog: function() {
            if (this.props.viewMode == 'compact') this.toggleExtendedNodePanel();
            dialogs.DeleteNodesDialog.show({nodes: [this.props.node], cluster: this.props.cluster});
        },
        render: function() {
            var ns = 'cluster_page.nodes_tab.node.',
                node = this.props.node,
                isSelectable = node.isSelectable() && this.props.mode != 'edit',
                status = node.getStatusSummary(),
                roles = this.sortRoles(node.get('roles').length ? node.get('roles') : node.get('pending_roles'));

            // compose classes
            var nodePanelClasses = {
                node: true,
                selected: this.props.checked,
                'col-xs-12': this.props.viewMode != 'compact',
                unavailable: !isSelectable
            };
            nodePanelClasses[status] = status;

            var manufacturer = node.get('manufacturer') || '',
                logoClasses = {
                    'manufacturer-logo': true
                };
            logoClasses[manufacturer.toLowerCase()] = manufacturer;

            var statusClasses = {
                    'node-status': true
                },
                statusClass = {
                    pending_addition: 'text-success',
                    pending_deletion: 'text-warning',
                    error: 'text-danger',
                    ready: 'text-info',
                    provisioning: 'text-info',
                    deploying: 'text-success',
                    provisioned: 'text-info'
                }[status];
            statusClasses[statusClass] = true;

            if (this.props.viewMode == 'compact') return (
                <div className='compact-node'>
                    <div className={utils.classNames(nodePanelClasses)}>
                        <label className='node-box'>
                            <div
                                className='node-box-inner clearfix'
                                onClick={isSelectable && _.partial(this.props.onNodeSelection, null, !this.props.checked)}
                            >
                                <div className='node-buttons'>
                                    {this.props.checked && <i className='glyphicon glyphicon-ok' />}
                                </div>
                                <div className='node-name'>
                                    <p>{node.get('name') || node.get('mac')}</p>
                                </div>
                                <div className={utils.classNames(statusClasses)}>
                                    {_.contains(['provisioning', 'deploying'], status) ?
                                        this.renderNodeProgress()
                                    :
                                        this.renderStatusLabel(status)
                                    }
                                </div>
                            </div>
                            <div className='node-hardware'>
                                <p>
                                    <span>
                                        {node.resource('cores') || '0'} ({node.resource('ht_cores') || '?'})
                                    </span> / <span>
                                        {node.resource('hdd') ? utils.showDiskSize(node.resource('hdd')) : '?' + i18n('common.size.gb')}
                                    </span> / <span>
                                        {node.resource('ram') ? utils.showMemorySize(node.resource('ram')) : '?' + i18n('common.size.gb')}
                                    </span>
                                </p>
                                <p className='btn btn-link' onClick={this.toggleExtendedNodePanel}>
                                    {i18n(ns + 'more_info')}
                                </p>
                            </div>
                        </label>
                    </div>
                    {this.state.extendedView &&
                        <controls.Popover className='node-popover' toggle={this.toggleExtendedNodePanel}>
                            <div>
                                <div className='node-name clearfix'>
                                    {this.renderNodeCheckbox()}
                                    <div className='name pull-left'>
                                        {this.renderNameControl()}
                                    </div>
                                </div>
                                <div className='node-stats'>
                                    {!!roles.length &&
                                        <div className='role-list'>
                                            <i className='glyphicon glyphicon-pushpin' />
                                            {this.renderRoleList(roles)}
                                        </div>
                                    }
                                    <div className={utils.classNames(statusClasses)}>
                                        <i className='glyphicon glyphicon-time' />
                                        {_.contains(['provisioning', 'deploying'], status) ?
                                            <div>
                                                {this.renderStatusLabel(status)}
                                                {this.renderLogsLink()}
                                                {this.renderNodeProgress(true)}
                                            </div>
                                        :
                                            <div>
                                                {this.renderStatusLabel(status)}
                                                {status == 'offline' && this.renderRemoveButton()}
                                                {!!node.get('cluster') &&
                                                    (node.hasChanges() ?
                                                        <button className='btn btn-discard' onClick={node.get('pending_addition') ? this.showDeleteNodesDialog : this.discardNodeChanges}>
                                                            {i18n(ns + (node.get('pending_addition') ? 'discard_addition' : 'discard_deletion'))}
                                                        </button>
                                                    :
                                                        this.renderLogsLink()
                                                    )
                                                }
                                            </div>
                                        }
                                    </div>
                                </div>
                                <div className='hardware-info clearfix'>
                                    <div className={utils.classNames(logoClasses)} />
                                    {this.renderNodeHardwareSummary()}
                                </div>
                                <div className='node-popover-buttons'>
                                    <button className='btn btn-default node-details' onClick={this.showNodeDetails}>Details</button>
                                </div>
                            </div>
                        </controls.Popover>
                    }
                </div>
            );

            return (
                <div className={utils.classNames(nodePanelClasses)}>
                    <label className='node-box'>
                        {this.renderNodeCheckbox()}
                        <div className={utils.classNames(logoClasses)} />
                        <div className='node-name'>
                            <div className='name'>
                                {this.renderNameControl()}
                            </div>
                            <div className='role-list'>
                                {this.renderRoleList(roles)}
                            </div>
                        </div>
                        <div className='node-action'>
                            {!!node.get('cluster') &&
                                ((this.props.locked || !node.hasChanges()) ?
                                    this.renderLogsLink(true)
                                :
                                    <div
                                        className='icon'
                                        title={i18n(ns + (node.get('pending_addition') ? 'discard_addition' : 'discard_deletion'))}
                                        onClick={node.get('pending_addition') ? this.showDeleteNodesDialog : this.discardNodeChanges}
                                    />
                                )
                            }
                        </div>
                        <div className={utils.classNames(statusClasses)}>
                            {_.contains(['provisioning', 'deploying'], status) ?
                                this.renderNodeProgress(true)
                            :
                                <div>
                                    {this.renderStatusLabel(status)}
                                    {status == 'offline' && this.renderRemoveButton()}
                                </div>
                            }
                        </div>
                        {this.renderNodeHardwareSummary()}
                        <div className='node-settings' onClick={this.showNodeDetails} />
                    </label>
                </div>
            );
        }
    });

    return Node;
});
