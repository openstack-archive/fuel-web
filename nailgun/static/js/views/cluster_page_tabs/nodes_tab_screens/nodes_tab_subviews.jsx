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
    'jsx!views/controls'
],
function(React, Expression, utils, controls) {
    'use strict';
    var panels = {};

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
