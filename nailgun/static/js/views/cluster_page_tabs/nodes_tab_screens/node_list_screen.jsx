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
    'jsx!views/controls',
    'jsx!views/dialogs',
    'jsx!component_mixins'
],
function(React, utils, models, controls, dialogs, componentMixins) {
    'use strict';
    var cx = React.addons.classSet,
        NodeListScreen, RolePanel, SelectAllMixin, NodeList, NodeGroup, Node;

    NodeListScreen = React.createClass({
        mixins: [
            componentMixins.pollingMixin(20),
            React.BackboneMixin('model', 'change:status'),
            React.BackboneMixin('nodes', 'add remove change'),
            React.BackboneMixin({modelOrCollection: function(props) {
                return props.model.get('tasks');
            }}),
            React.BackboneMixin({modelOrCollection: function(props) {
                return props.model.task({group: ['deployment', 'network'], status: 'running'});
            }})
        ],
        getInitialState: function() {
            return {
                loading: this.props.mode == 'add',
                filter: '',
                grouping: this.props.mode == 'add' ? 'hardware' : this.props.model.get('grouping'),
                selectedNodeIds: this.props.mode == 'edit' ? this.props.nodes.pluck('id') : [],
                actionInProgress: false
            };
        },
        selectNodes: function(ids, name, checked) {
            this.setState({
                selectedNodeIds: checked ? _.uniq(_.union(this.state.selectedNodeIds, ids)) : _.difference(this.state.selectedNodeIds, ids)
            });
        },
        shouldDataBeFetched: function() {
            return !this.state.loading;
        },
        fetchData: function() {
            return this.props.nodes.fetch();
        },
        componentWillMount: function() {
            var screenMode = this.props.mode,
                clusterId = screenMode == 'add' ? '' : this.props.model.id;
            this.props.nodes.fetch = function(options) {
                return this.constructor.__super__.fetch.call(this, _.extend({data: {cluster_id: clusterId}}, options));
            };
            var nodeIds = this.props.screenOptions[0] && utils.deserializeTabOptions(this.props.screenOptions[0]).nodes.split(',').map(function(id) {return parseInt(id, 10);});
            this.props.nodes.parse = function(response) {
                return screenMode != 'edit' ? response : _.filter(response, function(node) {return _.contains(nodeIds, node.id);});
            };
        },
        updateinitialRoles: function() {
            this.initialRoles = this.props.nodes.pluck('pending_roles');
        },
        componentDidMount: function() {
            if (this.props.mode != 'list') {
                this.updateinitialRoles();
                this.props.nodes.on('resize', this.updateinitialRoles, this);
                // hack to prevent node roles update after node polling
                this.props.nodes.on('change:pending_roles', function(node, roles, options) {
                    if (!options.assign) node.set({pending_roles: node.previous('pending_roles')}, {assign: true});
                }, this);
            }
            if (this.props.mode == 'add') {
                $.when(this.props.nodes.fetch(), this.props.model.get('settings').fetch({cache: true})).always(_.bind(function() {
                    this.setState({loading: false});
                    this.startPolling();
                }, this));
            }
        },
        hasChanges: function() {
            return this.state.loading ? false : !_.isEqual(this.props.nodes.pluck('pending_roles'), this.initialRoles);
        },
        changeFilter: function(name, value) {
            this.setState({filter: value});
        },
        changeGrouping: function(name, value) {
            this.setState({grouping: value});
        },
        revertChanges: function() {
            this.props.nodes.each(function(node, index) {
                node.set({pending_roles: this.initialRoles[index]}, {silent: true});
            }, this);
        },
        showDeleteNodesDialog: function(nodes) {
            app.page.tab.registerSubView(new dialogs.DeleteNodesDialog({nodes: new models.Nodes(_.invoke(nodes, 'clone'))})).render();
        },
        applyChanges: function(nodes) {
            this.setState({actionInProgress: true});
            var cluster = this.props.model;
            nodes = new models.Nodes(_.invoke(nodes, 'clone'));
            nodes.each(function(node) {
                if (this.props.mode == 'add') node.set({cluster_id: cluster.id, pending_addition: true});
                if (!node.get('pending_roles').length && node.get('pending_addition')) node.set({cluster_id: null, pending_addition: false});
            }, this);
            nodes.toJSON = function() {
                return this.map(function(node) {
                    return _.pick(node.attributes, 'id', 'cluster_id', 'pending_roles', 'pending_addition');
                });
            };
            nodes.sync('update', nodes)
                .done(_.bind(function() {
                    $.when(cluster.fetch(), cluster.fetchRelated('nodes')).always(_.bind(function() {
                        this.changeScreen();
                        app.navbar.refresh();
                        app.page.removeFinishedNetworkTasks();
                    }, this));
                }, this))
                .fail(_.bind(function() {
                    this.setState({actionInProgress: false});
                    this.showError('saving_warning');
                }, this));
        },
        showError: function(warning, hideLogsLink) {
            utils.showErrorDialog({
                title: $.t('cluster_page.nodes_tab.node_management_panel.node_management_error.title'),
                message: $.t('cluster_page.nodes_tab.node_management_panel.node_management_error.' + warning),
                hideLogsLink: hideLogsLink
            });
        },
        goToConfigurationScreen: function(action, conflict) {
            if (conflict) {
                this.showError(action + '_configuration_warning', true);
                return;
            }
            this.changeScreen(action, true);
        },
        changeScreen: function(url, passNodeIds) {
            if (!url) this.revertChanges();
            url = url ? '/' + url : '';
            if (passNodeIds) url += '/' + utils.serializeTabOptions({nodes: this.state.selectedNodeIds});
            app.navigate('#cluster/' + this.props.model.id + '/nodes' + url, {trigger: true});
        },
        renderManagementButtons: function() {
            var checkedNodes = this.state.selectedNodeIds.map(function(id) {return this.props.nodes.get(id);}, this);
            if (this.props.mode != 'list') {
                return [
                    <button key='cancel' className='btn' disabled={this.state.actionInProgress} onClick={_.bind(this.changeScreen, this, '', false)}>
                        {$.t('common.cancel_button')}
                    </button>,
                    <button key='apply' className='btn btn-success btn-apply' disabled={this.state.actionInProgress || !this.hasChanges()} onClick={_.bind(this.applyChanges, this, checkedNodes)}>
                        {$.t('common.apply_changes_button')}
                    </button>
                ];
            }
            var locked = !!this.props.model.tasks({group: 'deployment', status: 'running'}).length;
            if (!locked) {
                if (checkedNodes.length) {
                    var sampleNode = checkedNodes[0],
                        disksConflict = _.any(checkedNodes, function(node) {
                            var roleConflict = _.difference(_.union(sampleNode.get('roles'), sampleNode.get('pending_roles')), _.union(node.get('roles'), node.get('pending_roles'))).length;
                            return roleConflict || !_.isEqual(sampleNode.resource('disks'), node.resource('disks'));
                        }),
                        classes = {'btn btn-configure-disks': true, conflict: disksConflict},
                        buttons = [
                            <button key='disks' className={cx(classes)} onClick={_.bind(this.goToConfigurationScreen, this, 'disks', disksConflict)}>
                                {disksConflict && <i className='icon-attention text-error' />}
                                <span>{$.t('dialog.show_node.disk_configuration_button')}</span>
                            </button>
                        ];
                    if (!_.any(checkedNodes, function(node) {return node.get('status') == 'error';})) {
                        var interfaceConflict = _.uniq(checkedNodes.map(function(node) {return node.resource('interfaces');})).length > 1;
                        classes = {'btn btn-configure-interfaces': true, conflict: interfaceConflict};
                        buttons.push(
                            <button key='interfaces' className={cx(classes)} onClick={_.bind(this.goToConfigurationScreen, this, 'interfaces', interfaceConflict)}>
                                {interfaceConflict && <i className='icon-attention text-error' />}
                                <span>{$.t('dialog.show_node.network_configuration_button')}</span>
                            </button>
                        );
                    }
                    if (_.any(checkedNodes, function(node) {return !node.get('pending_deletion');})) buttons.push(
                        <button key='delete' className='btn btn-danger btn-delete-nodes' onClick={_.bind(this.showDeleteNodesDialog, this, checkedNodes)}>
                            <i className='icon-trash' /><span>{$.t('common.delete_button')}</span>
                        </button>
                    );
                    if (!_.any(checkedNodes, function(node) {return !node.get('pending_addition');})) buttons.push(
                        <button key='roles' className='btn btn-success btn-edit-roles' onClick={_.bind(this.changeScreen, this, 'edit', true)}>
                            <i className='icon-edit' /><span>{$.t('cluster_page.nodes_tab.node_management_panel.edit_roles_button')}</span>
                        </button>
                    );
                    return buttons;
                }
                return (
                    <button key='add' className='btn btn-success btn-add-nodes' onClick={_.bind(this.changeScreen, this, 'add', false)} disabled={this.state.loading}>
                        <i className='icon-plus' /><span>{$.t('cluster_page.nodes_tab.node_management_panel.add_nodes_button')}</span>
                    </button>
                );
            }
            return null;
        },
        render: function() {
            return (
                <div>
                    {this.props.mode == 'edit' &&
                        <div className='alert'>{$.t('cluster_page.nodes_tab.disk_configuration_reset_warning')}</div>
                    }
                    <div className='node-management-panel'>
                        <controls.Input
                            type='select'
                            name='grouping'
                            label={$.t('cluster_page.nodes_tab.node_management_panel.group_by')}
                            children={_.map(this.props.model.groupings(), function(label, grouping) {
                                return <option key={grouping} value={grouping}>{label}</option>;
                            })}
                            value={this.state.grouping}
                            disabled={!this.props.nodes.length || this.props.mode == 'add'}
                            onChange={this.changeGrouping}
                        />
                        <div className='node-filter'>
                            <controls.Input
                                type='text'
                                name='filter'
                                ref='filter'
                                value={this.state.filter}
                                label={$.t('cluster_page.nodes_tab.node_management_panel.filter_by')}
                                placeholder={$.t('cluster_page.nodes_tab.node_management_panel.filter_placeholder')}
                                disabled={!this.props.nodes.length}
                                onChange={this.changeFilter}
                            />
                            {!!this.state.filter &&
                                <button className='close btn-clear-filter' onClick={_.bind(this.changeFilter, this, '', '')} >&times;</button>
                            }
                        </div>
                        <div className='buttons'>{this.renderManagementButtons()}</div>
                    </div>
                    {this.state.loading ? <controls.ProgressBar /> :
                        <div>
                            {this.props.mode != 'list' && <RolePanel {...this.props} selectedNodeIds={this.state.selectedNodeIds} />}
                            <NodeList {...this.props}
                                grouping={this.state.grouping}
                                filter={this.state.filter}
                                locked={!!this.props.model.tasks({group: 'deployment', status: 'running'}).length}
                                selectedNodeIds={this.state.selectedNodeIds}
                                selectNodes={this.selectNodes}
                            />
                        </div>
                    }
                </div>
            );
        }
    });

    RolePanel = React.createClass({
        getInitialState: function() {
            var roles = this.props.model.get('release').get('roles'),
                nodes = this.props.nodes,
                getAssignedNodes = function(role) {
                    return nodes.filter(function(node) {return node.hasRole(role);});
                };
            return {
                selectedRoles: nodes.length ? _.filter(roles, function(role) {
                    return getAssignedNodes(role).length == nodes.length;
                }) : [],
                indeterminateRoles: nodes.length ? _.filter(roles, function(role) {
                    var assignedNodes = getAssignedNodes(role);
                    return assignedNodes.length && assignedNodes.length != nodes.length;
                }) : []
            };
        },
        componentDidUpdate: function() {
            _.each(this.refs, function(roleView, role) {
                roleView.refs.input.getDOMNode().indeterminate = _.contains(this.state.indeterminateRoles, role);
            }, this);
            this.assignRoles();
        },
        onChange: function(role, checked) {
            var selectedRoles = this.state.selectedRoles;
            if (checked) {
                selectedRoles.push(role);
            } else {
                selectedRoles = _.without(selectedRoles, role);
            }
            this.setState({
                selectedRoles: selectedRoles,
                indeterminateRoles: _.without(this.state.indeterminateRoles, role)
            });
        },
        assignRoles: function() {
            var roles = this.props.model.get('release').get('roles');
            this.props.nodes.each(function(node) {
                if (_.contains(this.props.selectedNodeIds, node.id)) _.each(roles, function(role) {
                    if (!node.hasRole(role, true)) {
                        var nodeRoles = node.get('pending_roles');
                        if (this.isRoleSelected(role)) {
                            if (this.isRoleAvailable(role)) nodeRoles = _.uniq(_.union(nodeRoles, role));
                        } else if (!_.contains(this.state.indeterminateRoles, role)) {
                            nodeRoles = _.without(nodeRoles, role);
                        }
                        node.set({pending_roles: nodeRoles}, {assign: true});
                    }
                }, this);
            }, this);
        },
        isRoleSelected: function(role) {
            return _.contains(this.state.selectedRoles, role);
        },
        isRoleAvailable: function(role) {
            // FIXME: the following hack should be described declaratively in yaml
            if ((role == 'controller' && this.props.model.get('mode') == 'multinode') || role == 'zabbix-server') {
                return this.props.selectedNodeIds.length <= 1 && !this.props.model.get('nodes').filter(function(node) {
                    return !_.contains(this.props.selectedNodeIds, node.id) && node.hasRole(role) && !node.get('pending_deletion');
                }, this).length;
            }
            return true;
        },
        render: function() {
            var ns = 'cluster_page.nodes_tab.',
                settings = this.props.model.get('settings'),
                configModels = {
                    cluster: this.props.model,
                    settings: settings,
                    version: app.version,
                    default: settings
                },
                roles = this.props.model.get('release').get('role_models'),
                conflicts = _.chain(this.state.selectedRoles)
                    .union(this.state.indeterminateRoles)
                    .map(function(role) {return roles.findWhere({name: role}).conflicts;})
                    .flatten()
                    .uniq()
                    .value();
            return (
                <div className='role-panel'>
                    <h4>{$.t(ns + 'assign_roles')}</h4>
                    {roles.map(function(role) {
                        var name = role.get('name');
                        if (!role.checkRestrictions(configModels, 'hide')) {
                            var checked = this.isRoleSelected(name),
                                isAvailable = this.isRoleAvailable(name),
                                disabled = !this.props.nodes.length || _.contains(conflicts, name) || (!isAvailable && !checked) || role.checkRestrictions(configModels, 'disable'),
                                warning = _.contains(conflicts, name) ? $.t(ns + 'role_conflict') : !isAvailable ? $.t('cluster_page.nodes_tab.' + name + '_restriction') : '';
                            return (
                                <controls.Input
                                    key={name}
                                    ref={name}
                                    type='checkbox'
                                    name={name}
                                    label={role.get('label')}
                                    description={role.get('description')}
                                    defaultChecked={checked}
                                    disabled={disabled}
                                    tooltipText={warning}
                                    wrapperClassName='role-container'
                                    labelClassName='role-label'
                                    descriptionClassName='role-description'
                                    onChange={this.onChange}
                                />
                            );
                        }
                    }, this)}
                </div>
            );
        }
    });

    SelectAllMixin = {
        renderSelectAllCheckbox: function() {
            var availableNodesIds = _.compact(this.props.nodes.map(function(node) {if (node.isSelectable()) return node.id;}));
            // FIXME: one more role limits management hack
            var roles = app.page && app.page.tab.screen.roles,
                roleLimitation = roles && ((roles.isRoleSelected('controller') && this.props.model.get('mode') == 'multi-node') || roles.isRoleSelected('zabbix-server')) && availableNodesIds.length > 1;
            return (
                <controls.Input
                    type='checkbox'
                    checked={this.props.mode == 'edit' || (availableNodesIds.length && !_.difference(availableNodesIds, this.props.selectedNodeIds).length)}
                    disabled={this.props.mode == 'edit' || this.props.locked || !availableNodesIds.length || roleLimitation}
                    label={$.t('common.select_all')}
                    wrapperClassName='span2 select-all'
                    onChange={_.bind(this.props.selectNodes, this.props, availableNodesIds)}
                />
            );
        }
    };

    NodeList = React.createClass({
        mixins: [SelectAllMixin],
        getEmptyListWarning: function() {
            var ns = 'cluster_page.nodes_tab.';
            if (this.props.mode == 'add') return $.t(ns + 'no_nodes_in_fuel');
            if (this.props.model.get('nodes').length) return $.t(ns + 'no_filtered_nodes_warning');
            return $.t(ns + 'no_nodes_in_environment');
        },
        groupNodes: function() {
            var nodes = this.props.nodes.filter(function(node) {
                    return _.contains(node.get('name').concat(' ', node.get('mac')).toLowerCase(), this.props.filter);
                }, this),
                method = _.bind(function(node) {
                    if (this.props.grouping == 'roles') return node.getRolesSummary();
                    if (this.props.grouping == 'hardware') return node.getHardwareSummary();
                    return node.getRolesSummary() + '; \u00A0' + node.getHardwareSummary();
                }, this),
                groups = _.pairs(_.groupBy(nodes, method));
            if (this.props.grouping == 'hardware') return _.sortBy(groups, function(group) {return group[0];});
            var preferredOrder = this.props.model.get('release').get('roles');
            return groups.sort(function(group1, group2) {
                var roles1 = group1[1][0].sortedRoles(),
                    roles2 = group2[1][0].sortedRoles(),
                    order;
                while (!order && roles1.length && roles2.length) {
                    order = _.indexOf(preferredOrder, roles1.shift()) - _.indexOf(preferredOrder, roles2.shift());
                }
                return order || roles1.length - roles2.length;
            });
        },
        render: function() {
            var groups = this.groupNodes();
            return (
                <div className='node-list'>
                    {!!groups.length &&
                        <div className='row-fluid node-list-header'>
                            <div className='span10' />
                            {this.renderSelectAllCheckbox()}
                        </div>
                    }
                    <div className='row-fluid'>
                        {groups.length ?
                            <div>
                                {groups.map(function(group) {
                                    return <NodeGroup {...this.props} key={group[0]} label={group[0]} nodes={group[1]} />;
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

    NodeGroup = React.createClass({
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
                            return <Node {...this.props}
                                key={node.id}
                                node={node}
                                checked={this.props.mode == 'edit' || _.contains(this.props.selectedNodeIds, node.id)}
                            />;
                        }, this)}
                    </div>
                </div>
            );
        }
    });

    Node = React.createClass({
        getInitialState: function() {
            return {
                renaming: false,
                actionInProgress: false
            };
        },
        componentDidMount: function() {
            this.eventNamespace = 'click.editnodename' + this.props.node.id;
        },
        componentWillUnmount: function() {
            $('html').off(this.eventNamespace);
        },
        componentDidUpdate: function() {
            if (this.props.mode == 'add' && !this.props.checked) this.props.node.set({pending_roles: []}, {assign: true});
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
                this.props.node.save({name: newName}, {patch: true, wait: true}).always(this.endNodeRenaming);
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
            var node = new models.Node(this.props.node.attributes),
                data = this.props.node.get('pending_addition') ? {cluster_id: null, pending_addition: false, pending_roles: []} : {pending_deletion: false};
            node.save(data, {patch: true, wait: true, silent: true})
                .done(_.bind(function() {
                    this.props.model.fetch();
                    this.props.model.fetchRelated('nodes');
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
            app.navigate('#cluster/' + this.props.model.id + '/logs/' + utils.serializeTabOptions(options), {trigger: true});
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
            var preferredOrder = this.props.model.get('release').get('roles');
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
                disabled = this.props.mode == 'edit' || this.props.locked || !node.isSelectable() || this.state.actionInProgress,
                roles = _.compact([this.renderRoleList('roles'), this.renderRoleList('pending_roles')]),
                buttonOptions = (this.props.mode == 'edit' || this.props.locked || !node.hasChanges()) ? {
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
            var statusClasses = {'node-status': true};
            statusClasses[statusClass] = true;
            var logoClasses = {'node-logo': true};
            logoClasses['manufacturer-' + node.get('manufacturer').toLowerCase()] = node.get('manufacturer');
            var nodeBoxClasses = {'node-box': true, disabled: disabled};
            nodeBoxClasses[status] = status;
            return (
                <div className={cx({node: true, checked: this.props.checked})}>
                    <label className={cx(nodeBoxClasses)}>
                        <controls.Input
                            type='checkbox'
                            name={node.id}
                            checked={this.props.checked}
                            disabled={disabled}
                            onChange={_.bind(this.props.selectNodes, this.props, [node.id])}
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
                            <div className={cx(statusClasses)}>
                                <div className='node-status-container'>
                                    {_.contains(['provisioning', 'deploying'], status) &&
                                        <div className={cx({progress: true, 'progress-success': status == 'deploying'})}>
                                            <div className='bar' style={{width: _.max([node.get('progress'), 3]) + '%'}} />
                                        </div>
                                    }
                                    <i className={iconClass} />
                                    <span>
                                        {$.t(ns + 'status.' + status, {os: this.props.model.get('release').get('operating_system') || 'OS'})}
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

    return NodeListScreen;
});
