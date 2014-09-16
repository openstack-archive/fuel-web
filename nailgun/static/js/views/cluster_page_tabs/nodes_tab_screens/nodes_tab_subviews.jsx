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
    'utils'
],
function(React, Expression, utils) {
    'use strict';
    var panels = {};

    panels.RolesPanel = React.createClass({
        getInitialState: function() {
            return {
                loading: true,
                selectedRoles: []
            };
        },
        componentDidMount: function() {
            this.props.cluster.get('settings').fetch({cache: true}).always(_.bind(function() {
                this.parseRoleData();
                this.setState({loading: false});
            }, this));
        },
        parseRoleData: function() {
            var configModels = {
                cluster: this.props.cluster,
                settings: this.props.cluster.get('settings'),
                version: app.version,
                default: this.props.cluster.get('settings')
            };
            this.parsedDependencies = {};
            this.conflicts = {};
            _.each(this.getRoleData(), function(data, role) {
                if (data.conflicts) {
                    this.conflicts[role] = _.uniq(_.union(this.conflicts[role], data.conflicts));
                    _.each(data.conflicts, function(conflict) {
                        this.conflicts[conflict] =  this.conflicts[conflict] || [];
                        this.conflicts[conflict].push(role);
                    }, this);
                }
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
        },
        getRoleData: function(role) {
            var data = this.props.cluster.get('release').get('roles_metadata');
            return role ? data[role] : data;
        },
        onChange: function(e) {
            var role = e.target.name,
                selectedRoles = this.state.selectedRoles;
            if (e.target.checked) {
                selectedRoles.push(role);
            } else {
                selectedRoles = _.difference(selectedRoles, role);
            }
            this.setState({selectedRoles: selectedRoles}, this.assignRoles);
        },
        assignRoles: function() {
            _.each(this.props.cluster.get('release').get('roles'), function(role) {
                _.each(this.getSelectedNodes(), function(node) {
                    if (!node.hasDeployedRole(role)) {
                        var roles = node.get('pending_roles');
                        node.set({
                            pending_roles: this.isRoleSelected(role) ? _.uniq(_.union(roles, role)) : _.difference(roles, role)
                        }, {assign: true});
                    }
                }, this);
            }, this);
        },
        isRoleSelected: function(role) {
            return _.contains(this.state.selectedRoles, role);
        },
        // FIXME: this method should be moved to NodeList view
        checkNodeForConflicts: function(e) {
            var selectedNodes = this.getSelectedNodes();
            var controllerNode = _.filter(selectedNodes, function(node) {return node.hasRole('controller');})[0];
            var zabbixNode = _.filter(selectedNodes, function(node) {return node.hasRole('zabbix-server');})[0];
            _.each(this.screen.nodes.where({checked: false}), function(node) {
                var isControllerAssigned = this.props.cluster.get('mode') == 'multinode' && this.isRoleSelected('controller') && controllerNode && controllerNode.id != node.id;
                var isZabbixAssigned = this.isRoleSelected('zabbix-server') && zabbixNode && zabbixNode.id != node.id;
                var disabled = isControllerAssigned || isZabbixAssigned || !node.isSelectable() || this.screen instanceof this.screen.EditNodesScreen || this.screen.isLocked();
                node.set('disabled', disabled);
                var filteredNode = this.screen.nodeList.filteredNodes.get(node.id);
                if (filteredNode) {
                    filteredNode.set('disabled', disabled);
                }
            }, this);
            this.screen.nodeList.calculateSelectAllDisabledState();
            _.invoke(this.screen.nodeList.subViews, 'calculateSelectAllDisabledState', this);
        },
        getConflicts: function() {
            return _.uniq(_.flatten(_.map(this.state.selectedRoles, function(role) { return this.conflicts[role];} , this)));
        },
        getSelectedNodes: function() {
            return this.props.nodes.where({checked: true});
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
        // FIXME: the following hacks should be described declaratively in yaml
        isRoleSelectable: function(role) {
            if ((role == 'controller' && this.props.cluster.get('mode') != 'multinode') || role == 'zabbix-server') {
                return this.getSelectedNodes().length <= 1 && !this.props.cluster.get('nodes').filter(function(node) {
                    return !_.contains(_.pluck(this.getSelectedNodes(), 'id'), node.id) && node.hasRole(role) && !node.get('pending_deletion');
                }, this).length;
            }
            if (role == 'mongo') return !this.props.cluster.get('nodes').filter(function(node) {
                return node.hasDeployedRole(role) && !node.get('pending_deletion');
            }, this).length;
            return true;
        },
        render: function() {
            var ns = 'cluster_page.nodes_tab.';
            return (
                <div>
                    <h4>{$.t(ns + 'assign_roles')}</h4>
                    {_.map(this.props.cluster.get('release').get('roles'), function(role) {
                        if (this.checkDependencies(role, 'hide').result) {
                            var data = this.getRoleData(role),
                                assignedNodes = this.props.nodes.filter(function(node) {return node.hasRole(role);}),
                                conflict = _.contains(this.getConflicts(), role.name),
                                isAvailable = this.isRoleSelectable(role),
                                dependenciesCheck = this.checkDependencies(role),
                                warning = conflict ? $.t(ns + 'role_conflict') : !isAvailable ? $.t('cluster_page.nodes_tab.' + role + '_restriction') : dependenciesCheck.warning;
                            return (<div className='role-container' key={role}>
                                <label>
                                    <input
                                        type='checkbox'
                                        name={role}
                                        defaultChecked={!!assignedNodes.length && assignedNodes.length == this.props.nodes.length}
                                        disabled={this.state.loading || !this.props.nodes.length || conflict || !isAvailable || !dependenciesCheck.result}
                                        onChange={this.onChange} />
                                    {data.name}
                                </label>
                                <div className='role-conflict'>{warning}</div>
                                <div className='role-description'>{data.description}</div>
                            </div>);
                        }
                    }, this)}
                </div>
            );
        }
    });

    return panels;
});