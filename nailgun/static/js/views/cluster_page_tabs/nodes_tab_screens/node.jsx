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
    'views/dialogs',
],
function(React, utils, models, dialogs) {
	'use strict';

	var Node = React.createClass({
        mixins: [React.BackboneMixin('node')],
        getInitialState: function() {
            return {renaming: false};
        },
        componentDidMount: function(options) {
            this.eventNamespace = 'click.editnodename' + this.props.node.id;
        },
        componentWillUnmount: function(options) {
            $('html').off(this.eventNamespace);
        },
        onNodeSelection: function(e) {
            this.props.checked = e.target.checked;
        },
        startNodeRenaming: function() {
            $('html').on(this.eventNamespace, _.bind(function(e) {
                if ($(e.target).hasClass('node-name') || $(e.target).hasClass('node-renameable')) {
                    e.preventDefault();
                } else {
                    this.endNodeRenaming();
                }
            }, this));
            this.setState({renaming: 'start'}, function() {
                $(this.getDomNode()).find('.node-name').focus();
            });
        },
        endNodeRenaming: function() {
            $('html').off(this.eventNamespace);
            this.setState({renaming: false});
        },
        applyNewNodeName: function(newName) {
            if (newName && newName != this.props.node.get('name')) {
                this.setState({renaming: 'save'});
                this.props.node.save({name: name}, {patch: true, wait: true}).always(_.bind(this.endNodeRenaming, this));
            } else {
                this.endNodeRenaming();
            }
        },
        onNodeNameInputKeydown: function(e) {
            if (e.which == 13) {
                this.applyNewNodeName(e.target.value);
            } else if (e.which == 27) {
                this.endNodeRenaming();
            }
        },
        updateNode: function(data) {
            var cluster = this.props.cluster;
            this.props.node.save(data, {patch: true, wait: true})
                .done(function() {
                    cluster.fetch();
                    cluster.fetchRelated('nodes');
                    app.navbar.refresh();
                    app.page.removeFinishedNetworkTasks();
                })
                .fail(function() {utils.showErrorDialog({title: $.t('dialog.discard_changes.cant_discard')});});
        },
        discardNodeChanges: function() {
            var options = this.props.node.get('pending_addition') ? {cluster_id: null, pending_addition: false, pending_roles: []} : {pending_deletion: false};
            this.updateNode(options);
        },
        showNodeLogs: function() {
            var node = this.props.node,
                status = node.get('status'),
                error = node.get('error_type'),
                options = {type: 'remote', node: node.id};
            if (status == 'discover') {
                options.source = 'bootstrap/messages';
            } else if (status == 'provisioning' || status == 'provisioned' || (status == 'error' && error == 'provision')) {
                options.source = 'install/anaconda';
            } else if (status == 'deploying' || status == 'ready' || (status == 'error' && error == 'deploy')) {
                options.source = 'install/puppet';
            }
            app.navigate('#cluster/' + this.props.cluster.id + '/logs/' + utils.serializeTabOptions(options), {trigger: true});
        },
        showNodeDetails: function() {
            app.page.tab.registerSubView(new dialogs.ShowNodeInfoDialog({node: this.props.node})).render();
        },
        sortRoles: function(roles) {
            var preferredOrder = this.props.cluster.get('release').get('roles');
            return roles.sort(function(a, b) {
                return _.indexOf(preferredOrder, a) - _.indexOf(preferredOrder, b);
            });
        },
        calculateNodeViewStatus: function() {
            var node = this.props.node;
            if (!node.get('online')) return 'offline';
            if (node.get('pending_addition')) return 'pending_addition';
            if (node.get('pending_deletion')) return 'pending_deletion';
            return node.get('status');
        },
        render: function() {
            var node = this.props.node,
                roles = node.get('roles'),
                pendingRoles = node.get('pending_roles'),
                showLogsButton = this.props.locked || !node.hasChanges(),
                ns = 'cluster_page.nodes_tab.node.',
                status = this.calculateNodeViewStatus(),
                statusClasses = {
                    offline: 'msg-offline',
                    pending_addition: 'msg-ok',
                    pending_deletion: 'msg-warning',
                    ready: 'msg-ok',
                    provisioning: 'provisioning',
                    provisioned: 'msg-provisioned',
                    deploying: 'deploying',
                    error: 'msg-error',
                    discover: 'msg-discover'
                },
                iconClasses = {
                    offline: 'icon-block',
                    pending_addition: 'icon-ok-circle-empty',
                    pending_deletion: 'icon-cancel-circle',
                    ready: 'icon-ok',
                    provisioned: 'icon-install',
                    error: 'icon-attention',
                    discover: 'icon-ok-circle-empty'
                };
            return (
                <div className={'node' + (this.props.checked ? 'checked' : '')}>
                    <label className={'node-box ' + status + (this.props.disabled ? ' disabled' : '')}>
                        <div className='custom-tumbler'>
                            <input type='checkbox' checked={this.props.checked} disabled={this.props.locked} onChange={this.onNodeSelection}/>
                            <span>&nbsp;</span>
                        </div>
                        <div className='node-content'>
                            <div className={'node-logo ' + node.get('manufacturer') ? 'manufacturer-' + node.get('manufacturer').toLowerCase() : ''} />
                            <div className='node-name-roles'>
                                <div className='name enable-selection'>
                                    {this.state.renaming ?
                                        <input
                                            type='text'
                                            className='node-name'
                                            value={node.get('name') || ''}
                                            disabled={this.state.renaming == 'save'}
                                            onKeyDown={this.onNodeNameInputKeydown} />
                                    :
                                        <p
                                            className={this.props.locked ? '' : 'node-renameable'}
                                            title={$.t(ns + 'edit_name')}
                                            onclick={!this.props.locked && this.startNodeRenaming}
                                        > {node.get('name') || node.get('mac')} </p>
                                    }
                                </div>
                                <div className='role-list'>
                                    {_.union(roles, pendingRoles).length ?
                                        <div>
                                            <ul className='roles'>
                                                {_.map(this.sortRoles(roles), function(role, index) { return <li key={index}>{role}</li>; })}
                                            </ul>
                                            <ul className='pending-roles'>
                                                {_.map(this.sortRoles(pendingRoles), function(role, index) { return <li key={index}>{role}</li>; })}
                                            </ul>
                                        </div>
                                    : $.t(ns + 'unallocated')}
                                </div>
                            </div>
						    {node.get('cluster') &&
                                <div className='node-button'>
                                    <button
                                        className='btn btn-link'
                                        title={showLogsButton ? $.t(ns + 'view_logs') : node.get('pending_addition') ? $.t(ns + 'discard_addition') : $.t(ns + 'discard_deletion')}
                                        onClick={showLogsButton ? this.showNodeLogs : this.discardNodeChanges}
                                    ><i className={showLogsButton ? 'icon-logs' : 'icon-back-in-time'} /></button>
                                </div>
                            }
						    <div className={'node-status '+ statusClasses[status]}>
						        <div className='node-status-container'>
							        {!_.contains(['provisioning', 'deploying'], status) &&
                                        <div>
                                            <div className={'progress ' + (status == 'deploying' ? 'progress-success' : '')}>
                                                <div className='bar' style={{width: _.max([node.get('progress'), 3]) + '%'}} />
                                            </div>
                                            <i className={iconClasses[status]} />
                                        </div>
                                    }
							        <span>
                                        {$.t(ns + 'status.' + status, {os: this.props.cluster.get('release').get('operating_system') || 'OS'})}
                                    </span>
						        </div>
						    </div>
						    <div className='node-details' onclick={this.showNodeDetails} />
						    <div className='node-hardware'>
						        <span>
                                    {$.t('node_details.cpu')}: {node.resource('cores') || '?'}
						        </span>
						        <span>
                                    {$.t('node_details.hdd')}: {node.resource('hdd') ? utils.showDiskSize(node.resource('hdd')) : '?' + $.t('common.size.gb')}
						        </span>
						        <span>
                                    {$.t('node_details.ram')}: {node.resource('ram') ? utils.showMemorySize(node.resource('ram')) : '?' + $.t('common.size.gb')}
						        </span>
						    </div>
                        </div>
                    </label>
				</div>
            );
        }
    });

	return Node;
});