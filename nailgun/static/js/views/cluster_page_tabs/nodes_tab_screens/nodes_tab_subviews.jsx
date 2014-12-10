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
    'underscore',
    'react',
    'jsx!views/controls'
],
function(_, React, controls) {
    'use strict';
    var panels = {};

    panels.RolesPanel = React.createClass({
        mixins: [React.BackboneMixin('nodes', 'add remove change:checked change:status')],
        getInitialState: function() {
            var roles = this.props.cluster.get('release').get('roles'),
                nodes = this.props.nodes,
                getAssignedNodes = function(role) {
                    return nodes.filter(function(node) { return node.hasRole(role); });
                };
            return {
                loading: true,
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
            // FIXME(vkramskikh): this should be passed from parent. The correct place to load
            // this data is route handler of subroute, though our router doesn't support
            // subrouting yet
            this.props.cluster.get('settings').fetch({cache: true}).always(_.bind(function() {
                this.setState({loading: false});
            }, this));
        },
        componentDidUpdate: function() {
            _.each(this.refs, function(roleView, role) {
                roleView.refs.input.getDOMNode().indeterminate = _.contains(this.state.indeterminateRoles, role);
            }, this);
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
            }, this.assignRoles);
        },
        assignRoles: function() {
            var selectedNodes = this.props.nodes.where({checked: true}),
                release = this.props.cluster.get('release'),
                models = this.getConfigModels();
            _.each(release.get('roles'), function(name) {
                _.each(selectedNodes, function(node) {
                    if (!node.hasRole(name, true)) {
                        var roles = node.get('pending_roles'),
                            role = release.get('role_models').findWhere({name: name});
                        if (this.isRoleSelected(name)) {
                            if (this.isRoleAvailable(name) && role.checkLimits(models, false, ['max'])) {
                                roles = _.uniq(_.union(roles, [name]));
                            }
                        } else if (!_.contains(this.state.indeterminateRoles, name)) {
                            roles = _.without(roles, name);
                        }
                        node.set({pending_roles: roles}, {assign: true});
                    }
                }, this);
            }, this);
        },
        isRoleSelected: function(role) {
            return _.contains(this.state.selectedRoles, role);
        },
        processRestrictions: function(role, models) {
            var name = role.get('name'),
                restrictionsCheck = role.checkRestrictions(models, 'disable'),
                roles = this.props.cluster.get('release').get('role_models'),
                conflicts = _.chain(this.state.selectedRoles)
                    .union(this.state.indeterminateRoles)
                    .map(function(role) {return roles.findWhere({name: role}).conflicts;})
                    .flatten()
                    .uniq()
                    .value(),
                limits = role.checkLimits(models, false, ['max']),
                messages = limits.valid ? [limits.message] : [];
            if (restrictionsCheck.message) messages.push(restrictionsCheck.message);
            if (_.contains(conflicts, name)) messages.push($.t('cluster_page.nodes_tab.role_conflict'));
            return {
                result: restrictionsCheck.result || _.contains(conflicts, name) || (!limits.valid && !this.isRoleSelected(name)),
                message: messages.join(' ')
            };
        },
        getConfigModels: function() {
            var cluster = this.props.cluster,
                settings = cluster.get('settings');
            return {
                cluster: cluster,
                settings: settings,
                version: app.version,
                default: settings,
                networking_parameters: cluster.get('networkConfiguration').get('networking_parameters')
            };
        },
        render: function() {
            var configModels = this.getConfigModels();

            return this.state.loading ? null : (
                <div>
                    <h4>{$.t('cluster_page.nodes_tab.assign_roles')}</h4>
                    {this.props.cluster.get('release').get('role_models').map(function(role) {
                        if (!role.checkRestrictions(configModels, 'hide').result) {
                            var name = role.get('name'),
                                processedRestrictions = this.props.nodes.length ? this.processRestrictions(role, configModels) : {},
                                // FIXME(pkaminski): 'min' errors should go to recommendations
                                warnings = processedRestrictions.message,
                                errors = role.checkLimits(configModels, ['max']).message;

                            if (!warnings) warnings = role.checkLimits(configModels, true, ['recommended']).message;

                            return (
                                <controls.Input
                                    key={name}
                                    ref={name}
                                    type='checkbox'
                                    name={name}
                                    label={role.get('label')}
                                    description={role.get('description')}
                                    defaultChecked={this.isRoleSelected(name)}
                                    disabled={!this.props.nodes.length || processedRestrictions.result}
                                    tooltipText={!!this.props.nodes.length && warnings}
                                    /*error={errors}*/
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

    return panels;
});
