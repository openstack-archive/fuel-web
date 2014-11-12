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
    'jsx!views/dialogs',
    'jsx!views/controls'
],
function(React, utils, models, dialogs, controls) {
    'use strict';

    var cx = React.addons.classSet;

    var SelectAllMixin = {
        getSelectableNodes: function() {
            return _.compact(this.props.nodes.filter(function(node) {return node.isSelectable();}));
        },
        selectNodes: function(name, checked) {
            var ids = _.pluck(this.getSelectableNodes(), 'id');
            _.invoke(app.page.tab.screen.nodes.filter(function(node) {return _.contains(ids, node.id);}), 'set', {checked: checked});
        },
        renderSelectAllCheckbox: function() {
            var selectableNodes = this.getSelectableNodes(),
                roles = app.page && app.page.tab.screen && app.page.tab.screen.roles,
                // FIXME: one more role limits management hack
                roleLimitation = roles && ((roles.isRoleSelected('controller') && this.props.cluster.get('mode') == 'multi-node') || roles.isRoleSelected('zabbix-server')) && selectableNodes.length > 1;
            return (
                <controls.Input
                    type='checkbox'
                    checked={this.props.checked || (selectableNodes.length && this.props.nodes.where({checked: true}).length == selectableNodes.length)}
                    disabled={this.props.locked || !selectableNodes.length || roleLimitation}
                    label={$.t('common.select_all')}
                    wrapperClassName='span2 select-all'
                    onChange={this.selectNodes}
                />
            );
        }
    };

    var NodeList = React.createClass({
        mixins: [
            SelectAllMixin,
            React.BackboneMixin('nodes', 'reset change')
        ],
        groupNodes: function() {
            if (this.props.grouping == 'hardware') {
                this.groups = _.sortBy(this.groups, function(group) {return group[0];});
            } else {
                this.groups = _.pairs(this.props.nodes.groupByAttribute(this.props.grouping));
                var preferredOrder = this.props.cluster.get('release').get('roles').pluck('name');
                this.groups.sort(function(group1, group2) {
                    var roles1 = group1[1][0].sortedRoles(),
                        roles2 = group2[1][0].sortedRoles(),
                        order;
                    while (!order && roles1.length && roles2.length) {
                        order = _.indexOf(preferredOrder, roles1.shift()) - _.indexOf(preferredOrder, roles2.shift());
                    }
                    return order || roles1.length - roles2.length;
                });
            }
        },
        getEmptyListWarning: function() {
            var ns = 'cluster_page.nodes_tab.';
            if (!this.props.nodes.cluster) return $.t(ns + 'no_nodes_in_fuel');
            if (this.props.cluster.get('nodes').length) return $.t(ns + 'no_filtered_nodes_warning');
            return $.t(ns + 'no_nodes_in_environment');
        },
        render: function() {
            this.groupNodes();
            return (
                <div className='node-list'>
                    {!!this.props.nodes.length &&
                        <div className='row-fluid node-list-header'>
                            <div className='span10' />
                            {this.renderSelectAllCheckbox()}
                        </div>
                    }
                    <div className='row-fluid'>
                        {this.props.nodes.length ?
                            <div>
                                {this.groups.map(function(group) {
                                    return this.transferPropsTo(<NodeGroup key={group[0]} label={group[0]} nodes={new models.Nodes(group[1])} />);
                                }, this)}
                            </div>
                        :
                            <div className='alert alert-warning'>{this.getEmptyListWarning()}</div>
                        }
                    </div>
                </div>
            );
        }
    });

    var NodeGroup = React.createClass({
        mixins: [SelectAllMixin],
        render: function() {
            return (
                <div className='node-group'>
                    <div className='row-fluid node-group-header'>
                        <div className='span10'>
                            <h4>{this.props.label} ({this.props.nodes.length})</h4>
                        </div>
                        {this.renderSelectAllCheckbox()}
                    </div>
                    <div>
                        {this.props.nodes.map(function(node) {
                            return this.transferPropsTo(<Node key={node.id} node={node} />);
                        }, this)}
                    </div>
                </div>
            );
        }
    });

    var Node = React.createClass({
        mixins: [React.BackboneMixin('node', 'change')],
        getInitialState: function() {
            return {
                renaming: false,
                actionInProgress: false
            };
        },
        componentDidMount: function(options) {
            this.eventNamespace = 'click.editnodename' + this.props.node.id;
        },
        componentWillUnmount: function(options) {
            $('html').off(this.eventNamespace);
        },
        getOriginalNode: function(id) {
            return app.page.tab.screen.nodes.get(id);
        },
        onNodeSelection: function(id, checked) {
            this.getOriginalNode(id).set('checked', checked);
        },
        startNodeRenaming: function(e) {
            e.preventDefault();
            $('html').on(this.eventNamespace, _.bind(function(e) {
                if ($(e.target).hasClass('node-name')) {
                    e.preventDefault();
                } else {
                    this.endNodeRenaming();
                }
            }, this));
            this.setState({renaming: true});
        },
        endNodeRenaming: function() {
            $('html').off(this.eventNamespace);
            this.setState({
                renaming: false,
                actionInProgress: false
            });
        },
        applyNewNodeName: function(newName) {
            if (newName && newName != this.props.node.get('name')) {
                this.setState({actionInProgress: true});
                this.getOriginalNode(this.props.node.id).save({name: newName}, {patch: true, wait: true}).always(this.endNodeRenaming);
            } else {
                this.endNodeRenaming();
            }
        },
        onNodeNameInputKeydown: function(e) {
            if (e.which == 13) {
                this.applyNewNodeName(this.refs.name.getValue());
            } else if (e.which == 27) {
                this.endNodeRenaming();
            }
        },
        discardNodeChanges: function() {
            this.setState({actionInProgress: true});
            var data = this.props.node.get('pending_addition') ? {cluster_id: null, pending_addition: false, pending_roles: []} : {pending_deletion: false};
            this.getOriginalNode(this.props.node.id).save(data, {patch: true, wait: true, silent: true})
                .done(_.bind(function() {
                    this.props.cluster.fetch();
                    this.props.cluster.fetchRelated('nodes');
                    this.setState({actionInProgress: false});
                    app.navbar.refresh();
                    app.page.removeFinishedNetworkTasks();
                }, this))
                .fail(function() {utils.showErrorDialog({title: $.t('dialog.discard_changes.cant_discard')});});
        },
        showNodeLogs: function() {
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
            app.navigate('#cluster/' + this.props.cluster.id + '/logs/' + utils.serializeTabOptions(options), {trigger: true});
        },
        showNodeDetails: function(e) {
            e.preventDefault();
            app.page.tab.registerSubView(new dialogs.ShowNodeInfoDialog({node: this.props.node})).render();
        },
        calculateNodeViewStatus: function() {
            var node = this.props.node;
            if (!node.get('online')) return 'offline';
            if (node.get('pending_addition')) return 'pending_addition';
            if (node.get('pending_deletion')) return 'pending_deletion';
            return node.get('status');
        },
        sortRoles: function(roles) {
            var preferredOrder = this.props.cluster.get('release').get('roles').pluck('name');
            return roles.sort(function(a, b) {
                return _.indexOf(preferredOrder, a) - _.indexOf(preferredOrder, b);
            });
        },
        renderRoleList: function(attribute) {
            var roles = this.props.node.get(attribute);
            if (!roles.length) return null;
            return (
                <ul key={attribute} className={attribute}>
                    {_.map(this.sortRoles(roles), function(role, index) {
                        return <li key={index}>{role}</li>;
                    })}
                </ul>
            );
        },
        renderButton: function(options) {
            return (
                <button
                    className='btn btn-link'
                    title={$.t('cluster_page.nodes_tab.node.' + options.title)}
                    onClick={!this.state.actionInProgress && options.onClick}
                >
                    <i className={options.className} />
                </button>
            );
        },
        render: function() {
            var ns = 'cluster_page.nodes_tab.node.',
                node = this.props.node,
                disabled = this.props.locked || !node.isSelectable() || this.state.actionInProgress,
                checked = (this.props.checked && node.isSelectable()) || node.get('checked'),
                roles = _.compact([this.renderRoleList('roles'), this.renderRoleList('pending_roles')]),
                buttonOptions = (this.props.locked || !node.hasChanges()) ? {
                        title: 'view_logs',
                        onClick: this.showNodeLogs,
                        className: 'icon-logs'
                    } : {
                        title: node.get('pending_addition') ? 'discard_addition' : 'discard_deletion',
                        onClick: this.discardNodeChanges,
                        className: 'icon-back-in-time'
                    };
            var status = this.calculateNodeViewStatus(),
                statusClass = {
                    offline: 'msg-offline',
                    pending_addition: 'msg-ok',
                    pending_deletion: 'msg-warning',
                    ready: 'msg-ok',
                    provisioning: 'provisioning',
                    provisioned: 'msg-provisioned',
                    deploying: 'deploying',
                    error: 'msg-error',
                    discover: 'msg-discover'
                }[status],
                iconClass = {
                    offline: 'icon-block',
                    pending_addition: 'icon-ok-circle-empty',
                    pending_deletion: 'icon-cancel-circle',
                    ready: 'icon-ok',
                    provisioned: 'icon-install',
                    error: 'icon-attention',
                    discover: 'icon-ok-circle-empty'
                }[status];
            var logoClasses = {'node-logo': true};
            logoClasses['manufacturer-' + node.get('manufacturer').toLowerCase()] = node.get('manufacturer');
            var nodeBoxClasses = {'node-box': true, disabled: disabled};
            nodeBoxClasses[status] = status;
            return (
                <div className={cx({node: true, checked: checked})}>
                    <label className={cx(nodeBoxClasses)}>
                        <controls.Input
                            type='checkbox'
                            name={node.id}
                            checked={checked}
                            disabled={disabled}
                            onChange={this.onNodeSelection}
                        />
                        <div className='node-content'>
                            <div className={cx(logoClasses)} />
                            <div className='node-name-roles'>
                                <div className='name enable-selection'>
                                    {this.state.renaming ?
                                        <controls.Input
                                            ref='name'
                                            type='text'
                                            defaultValue={node.get('name')}
                                            inputClassName='node-name'
                                            disabled={this.state.actionInProgress}
                                            onKeyDown={this.onNodeNameInputKeydown}
                                            autoFocus
                                        />
                                    :
                                        <p title={$.t(ns + 'edit_name')} onClick={!disabled && this.startNodeRenaming}>
                                            {node.get('name') || node.get('mac')}
                                        </p>
                                    }
                                </div>
                                <div className='role-list'>
                                    {roles.length ? roles : $.t(ns + 'unallocated')}
                                </div>
                            </div>
                            <div className='node-button'>
                                {!!node.get('cluster') && this.renderButton(buttonOptions)}
                            </div>
                            <div className='node-status'>
                                <div className='node-status-container'>
                                    {_.contains(['provisioning', 'deploying'], status) &&
                                        <div className={cx({progress: true, 'progress-success': status == 'deploying'})}>
                                            <div className='bar' style={{width: _.max([node.get('progress'), 3]) + '%'}} />
                                        </div>
                                    }
                                    <i className={iconClass} />
                                    <span>
                                        {$.t(ns + 'status.' + status, {os: this.props.cluster.get('release').get('operating_system') || 'OS'})}
                                    </span>
                                </div>
                            </div>
                            <div className='node-details' onClick={this.showNodeDetails} />
                            <div className='node-hardware'>
                                <span>
                                    {$.t('node_details.cpu')}: {node.resource('cores') || '0'} ({node.resource('ht_cores') || '?'})
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

    return NodeList;
});
