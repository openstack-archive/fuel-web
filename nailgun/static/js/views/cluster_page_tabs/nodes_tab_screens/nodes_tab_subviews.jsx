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
            var roles = this.props.cluster.get('release').get('roles').pluck('name'),
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
            var settings = this.props.cluster.get('settings');
            settings.fetch({cache: true}).always(this.processConflicts, this);
        },
        componentDidUpdate: function() {
            _.each(this.refs, function(roleView, role) {
                roleView.refs.input.getDOMNode().indeterminate = _.contains(this.state.indeterminateRoles, role);
            }, this);
        },
        processConflicts: function() {
            this.conflicts = {};
            this.props.cluster.get('release').get('roles').each(function(role) {
                var name = role.get('name'),
                    conflicts = role.get('conflicts');
                this.conflicts[name] = _.compact(_.uniq(_.union(this.conflicts[name], conflicts)));
                _.each(conflicts, function(conflictingRole) {
                    this.conflicts[conflictingRole] =  this.conflicts[conflictingRole] || [];
                    this.conflicts[conflictingRole].push(name);
                }, this);
            }, this);
            this.forceUpdate();
        },
        onChange: function(role, checked) {
            var selectedRoles = this.state.selectedRoles;
            if (checked) selectedRoles.push(role); else selectedRoles = _.difference(selectedRoles, role);
            this.setState({
                selectedRoles: selectedRoles,
                indeterminateRoles: _.difference(this.state.indeterminateRoles, role)
            }, this.assignRoles);
        },
        assignRoles: function() {
            var selectedNodes = this.props.nodes.where({checked: true});
            this.props.cluster.get('release').get('roles').each(function(role) {
                var name = role.get('name');
                _.each(selectedNodes, function(node) {
                    if (!node.hasRole(name, true)) {
                        var roles = node.get('pending_roles');
                        if (this.isRoleSelected(name)) {
                            if (this.isRoleAvailable(name)) roles = _.uniq(_.union(roles, name));
                        } else if (!_.contains(this.state.indeterminateRoles, name)) {
                            roles = _.difference(roles, name);
                        }
                        node.set({pending_roles: roles}, {assign: true});
                    }
                }, this);
            }, this);
        },
        isRoleSelected: function(role) {
            return _.contains(this.state.selectedRoles, role);
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
                settings = this.props.cluster.get('settings'),
                configModels = {
                    cluster: this.props.cluster,
                    settings: settings,
                    version: app.version,
                    default: settings
                },
                conflicts = this.conflicts ? _.uniq(_.flatten(_.map(_.union(this.state.selectedRoles, this.state.indeterminateRoles), function(role) {
                    return this.conflicts[role];
                } , this))) : [];
            return (
                <div>
                    <h4>{$.t(ns + 'assign_roles')}</h4>
                    {this.props.cluster.get('release').get('roles').map(function(role) {
                        var name = role.get('name');
                        if (!role.checkRestrictions(configModels, 'hide').result) {
                            var restrictionsCheck = role.checkRestrictions(configModels, 'disable'),
                                checked = this.isRoleSelected(name),
                                isAvailable = this.isRoleAvailable(name),
                                disabled = !this.props.nodes.length || _.contains(conflicts, name) || (!isAvailable && !checked) || restrictionsCheck.result,
                                warning = (restrictionsCheck.result && restrictionsCheck.warnings.join(' ')) || (_.contains(conflicts, name) ? $.t(ns + 'role_conflict') : !isAvailable ? $.t('cluster_page.nodes_tab.' + name + '_restriction') : '');
                            return (<controls.Input
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
                            />);
                        }
                    }, this)}
                </div>
            );
        }
    });

    return panels;
});
