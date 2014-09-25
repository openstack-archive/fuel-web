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
    'expression',
    'utils',
    'models',
    'jsx!views/dialogs',
    'jsx!views/controls'
],
function(React, Expression, utils, models, dialogs, controls) {
    'use strict';
    var panels = {};

    var cx = React.addons.classSet;

    panels.NodeManagementPanel = React.createClass({
        mixins: [
            React.BackboneMixin('cluster', 'change:status'),
            React.BackboneMixin('nodes', 'add remove change'),
            React.BackboneMixin({modelOrCollection: function(props) {
                return props.cluster.get('tasks');
            }}),
            React.BackboneMixin({modelOrCollection: function(props) {
                return props.cluster.task({group: 'deployment', status: 'running'});
            }})
        ],
        getInitialState: function() {
            return {
                filter: '',
                actionInProgress: false
            };
        },
        filterNodes: _.debounce(function(filter) {
            app.page.tab.screen.nodeList.filterNodes(filter);
        }, 300),
        onFilterChange: function(name, filter) {
            filter = $.trim(filter).toLowerCase();
            this.setState({filter: filter});
            this.filterNodes(filter);
        },
        clearFilter: function() {
            this.setState({filter: ''});
            app.page.tab.screen.nodeList.filterNodes('');
        },
        groupNodes: function(name, grouping) {
            this.props.cluster.save({grouping: grouping}, {patch: true, wait: true});
            if (app.page.tab) app.page.tab.screen.nodeList.groupNodes(grouping);
        },
        getCheckedNodes: function() {
            return this.props.nodes.where({checked: true});
        },
        showDeleteNodesDialog: function() {
            utils.showDialog(dialogs.DeleteNodesDialog({nodes: new models.Nodes(_.invoke(this.getCheckedNodes(), 'clone'))}));
        },
        applyChanges: function() {
            this.setState({actionInProgress: true});
            var cluster = this.props.cluster,
                nodes = new models.Nodes(_.invoke(this.getCheckedNodes(), 'clone'));
            nodes.each(function(node) {
                if (!this.props.nodes.cluster) node.set({cluster_id: cluster.id, pending_addition: true});
                if (!node.get('pending_roles').length && node.get('pending_addition')) node.set({cluster_id: null, pending_addition: false});
            }, this);
            nodes.toJSON = function(options) {
                return this.map(function(node) {
                    return _.pick(node.attributes, 'id', 'cluster_id', 'pending_roles', 'pending_addition');
                });
            };
            nodes.sync('update', nodes)
                .done(function() {
                    $.when(cluster.fetch(), cluster.fetchRelated('nodes')).always(function() {
                        app.navigate('#cluster/' + cluster.id + '/nodes', {trigger: true});
                        app.navbar.refresh();
                        app.page.removeFinishedNetworkTasks();
                    });
                })
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
            app.navigate('#cluster/' + this.props.cluster.id + '/nodes/' + action + '/' + utils.serializeTabOptions({nodes: _.pluck(this.getCheckedNodes(), 'id')}), {trigger: true});
        },
        goToAddNodesScreen: function() {
            app.navigate('#cluster/' + this.props.cluster.id + '/nodes/add', {trigger: true});
        },
        goToEditRolesScreen: function() {
            app.navigate('#cluster/' + this.props.cluster.id + '/nodes/edit/' + utils.serializeTabOptions({nodes: _.pluck(this.getCheckedNodes(), 'id')}), {trigger: true});
        },
        goToNodeList: function() {
            if (app.page.tab) app.page.tab.screen.revertChanges();
            app.navigate('#cluster/' + this.props.cluster.id + '/nodes', {trigger: true});
        },
        renderButtons: function() {
            if (!this.props.clusterNodesScreen && app.page) return [
                <button key='cancel' className='btn' disabled={this.state.actionInProgress} onClick={this.goToNodeList}>
                    {$.t('common.cancel_button')}
                </button>,
                <button key='apply' className='btn btn-success btn-apply' disabled={this.state.actionInProgress || !app.page.tab.screen.hasChanges()} onClick={this.applyChanges}>
                    {$.t('common.apply_changes_button')}
                </button>
            ];
            if (!this.props.cluster.tasks({group: 'deployment', status: 'running'}).length) {
                var checkedNodes = this.getCheckedNodes(),
                    classes;
                if (checkedNodes.length) {
                    var buttons = [],
                        sampleNode = checkedNodes[0],
                        disksConflict = _.any(checkedNodes, function(node) {
                            var roleConflict = _.difference(_.union(sampleNode.get('roles'), sampleNode.get('pending_roles')), _.union(node.get('roles'), node.get('pending_roles'))).length;
                            return roleConflict || !_.isEqual(sampleNode.resource('disks'), node.resource('disks'));
                        });
                    classes = {'btn btn-configure-disks': true, conflict: disksConflict};
                    buttons.push(
                        <button key='disks' className={cx(classes)} onClick={_.bind(this.goToConfigurationScreen, this, 'disks', disksConflict)}>
                            {disksConflict && <i className='icon-attention text-error' />}
                            <span>{$.t('dialog.show_node.disk_configuration_button')}</span>
                        </button>
                    );
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
                        <button key='delete' className='btn btn-danger btn-delete-nodes' onClick={this.showDeleteNodesDialog}>
                            <i className='icon-trash' /><span>{$.t('common.delete_button')}</span>
                        </button>
                    );
                    if (!_.any(checkedNodes, function(node) {return !node.get('pending_addition');})) buttons.push(
                        <button key='roles' className='btn btn-success btn-edit-roles' onClick={this.goToEditRolesScreen}>
                            <i className='icon-edit' /><span>{$.t('cluster_page.nodes_tab.node_management_panel.edit_roles_button')}</span>
                        </button>
                    );
                    return buttons;
                }
                return (
                    <button key='add' className='btn btn-success btn-add-nodes' onClick={this.goToAddNodesScreen}>
                        <i className='icon-plus' /><span>{$.t('cluster_page.nodes_tab.node_management_panel.add_nodes_button')}</span>
                    </button>
                );
            }
            return null;
        },
        render: function() {
            var ns = 'cluster_page.nodes_tab.node_management_panel.',
                cluster = this.props.cluster,
                groupings = _.map(cluster.groupings(), function(label, grouping) {return <option key={grouping} value={grouping}>{label}</option>;});
            return (
                <div className='cluster-toolbar'>
                    <div className='node-management-control'>
                        <controls.Input
                            type='select'
                            name='grouping'
                            label={$.t(ns + 'group_by')}
                            children={groupings}
                            defaultValue={this.props.addNodesScreen ? 'hardware' : cluster.get('grouping')}
                            disabled={this.props.addNodesScreen || !this.props.nodes.length}
                            onChange={this.groupNodes}
                        />
                    </div>
                    <div className='node-management-control'>
                        <controls.Input
                            type='text'
                            name='filter'
                            ref='filter'
                            value={this.state.filter}
                            label={$.t(ns + 'filter_by')}
                            placeholder={$.t(ns + 'filter_placeholder')}
                            disabled={!this.props.nodes.length}
                            onChange={this.onFilterChange}
                        />
                        {this.state.filter &&
                            <button className='close btn-clear-filter' onClick={this.clearFilter} >&times;</button>
                        }
                    </div>
                    <div className='node-management-control buttons'>
                        {this.renderButtons()}
                    </div>
                </div>
            );
        }
    });

    panels.RolesPanel = React.createClass({
        mixins: [React.BackboneMixin('nodes', 'add remove change:checked change:status')],
        getInitialState: function() {
            var roles = this.getRoleList(),
                nodes = this.props.nodes,
                getAssignedNodes = function(role) {
                    return nodes.filter(function(node) { return node.hasRole(role); });
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
        componentDidMount: function() {
            if (!this.parsedDependencies) this.props.cluster.get('settings').fetch({cache: true}).always(this.parseRoleData, this);
        },
        componentDidUpdate: function() {
            _.each(this.refs, function(roleView, role) {
                roleView.refs.input.getDOMNode().indeterminate = _.contains(this.state.indeterminateRoles, role);
            }, this);
        },
        parseRoleData: function() {
            this.parsedDependencies = {};
            this.conflicts = {};
            var configModels = {
                cluster: this.props.cluster,
                settings: this.props.cluster.get('settings'),
                version: app.version,
                default: this.props.cluster.get('settings')
            };
            _.each(this.getRoleData(), function(data, role) {
                this.conflicts[role] = _.compact(_.uniq(_.union(this.conflicts[role], data.conflicts)));
                _.each(data.conflicts, function(conflictingRole) {
                    this.conflicts[conflictingRole] =  this.conflicts[conflictingRole] || [];
                    this.conflicts[conflictingRole].push(role);
                }, this);
                this.parsedDependencies[role] = [];
                _.each(data.depends, function(dependency) {
                    dependency = utils.expandRestriction(dependency);
                    this.parsedDependencies[role].push({
                        expression: new Expression(dependency.condition, configModels),
                        action: dependency.action,
                        warning: dependency.warning
                    });
                }, this);
            }, this);
            this.forceUpdate();
        },
        getRoleList: function(role) {
            return this.props.cluster.get('release').get('roles');
        },
        getRoleData: function() {
            return this.props.cluster.get('release').get('roles_metadata');
        },
        onChange: function(role, checked) {
            var selectedRoles = this.state.selectedRoles;
            if (checked) {
                selectedRoles.push(role);
            } else {
                selectedRoles = _.difference(selectedRoles, role);
            }
            this.setState({
                selectedRoles: selectedRoles,
                indeterminateRoles: _.difference(this.state.indeterminateRoles, role)
            }, this.assignRoles);
        },
        assignRoles: function() {
            var selectedNodes = this.props.nodes.where({checked: true});
            _.each(this.getRoleList(), function(role) {
                _.each(selectedNodes, function(node) {
                    if (!node.hasRole(role, true)) {
                        var roles = node.get('pending_roles');
                        if (this.isRoleSelected(role)) {
                            if (this.isRoleAvailable(role)) roles = _.uniq(_.union(roles, role));
                        } else if (!_.contains(this.state.indeterminateRoles, role)) {
                            roles = _.difference(roles, role);
                        }
                        node.set({pending_roles: roles}, {assign: true});
                    }
                }, this);
            }, this);
        },
        isRoleSelected: function(role) {
            return _.contains(this.state.selectedRoles, role);
        },
        checkDependencies: function(role, action) {
            var checkResult = {result: true, warning: ''};
            if (this.parsedDependencies) {
                action = action || 'disable';
                var warnings = [];
                _.each(_.where(this.parsedDependencies[role], {action: action}), function(dependency) {
                    if (!dependency.expression.evaluate()) {
                        checkResult.result = false;
                        warnings.push(dependency.warning);
                    }
                });
                checkResult.warning = warnings.join(' ');
            }
            return checkResult;
        },
        isRoleAvailable: function(role) {
            // FIXME: the following hacks should be described declaratively in yaml
            var selectedNodesIds = _.pluck(this.props.nodes.where({checked: true}), 'id');
            if ((role == 'controller' && this.props.cluster.get('mode') == 'multinode') || role == 'zabbix-server') {
                return selectedNodesIds.length <= 1 && !this.props.cluster.get('nodes').filter(function(node) {
                    return !_.contains(selectedNodesIds, node.id) && node.hasRole(role) && !node.get('pending_deletion');
                }).length;
            }
            return true;
        },
        render: function() {
            var ns = 'cluster_page.nodes_tab.',
                conflicts = this.conflicts ? _.uniq(_.flatten(_.map(_.union(this.state.selectedRoles, this.state.indeterminateRoles), function(role) {
                    return this.conflicts[role];
                } , this))) : [];
            return (
                <div>
                    <h4>{$.t(ns + 'assign_roles')}</h4>
                    {_.map(this.getRoleList(), function(role) {
                        if (this.checkDependencies(role, 'hide').result) {
                            var data = this.getRoleData()[role],
                                dependenciesCheck = this.checkDependencies(role),
                                checked = this.isRoleSelected(role),
                                isAvailable = this.isRoleAvailable(role),
                                disabled = !this.props.nodes.length || _.contains(conflicts, role) || (!isAvailable && !checked) || !dependenciesCheck.result,
                                warning = dependenciesCheck.warning || (_.contains(conflicts, role) ? $.t(ns + 'role_conflict') : !isAvailable ? $.t('cluster_page.nodes_tab.' + role + '_restriction') : '');
                            return (<controls.Input
                                key={role}
                                ref={role}
                                type='checkbox'
                                name={role}
                                label={data.name}
                                description={data.description}
                                defaultChecked={checked}
                                disabled={disabled}
                                tooltipText={warning}
                                wrapperClassName='role-container'
                                labelClassName='role-label'
                                descriptionClassName='role-description'
                                onChange={this.onChange}
                            />);
                        }
                    }, this)}
                </div>
            );
        }
    });

    return panels;
});
