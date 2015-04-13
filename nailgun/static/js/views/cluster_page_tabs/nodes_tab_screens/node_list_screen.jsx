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
    'jquery',
    'underscore',
    'i18n',
    'backbone',
    'react',
    'utils',
    'models',
    'dispatcher',
    'jsx!views/controls',
    'jsx!views/dialogs',
    'jsx!component_mixins'
],
function($, _, i18n, Backbone, React, utils, models, dispatcher, controls, dialogs, componentMixins) {
    'use strict';
    var NodeListScreen, ManagementPanel, RolePanel, SelectAllMixin, NodeList, NodeGroup, Node;

    NodeListScreen = React.createClass({
        mixins: [
            componentMixins.pollingMixin(20, true),
            componentMixins.backboneMixin('cluster', 'change:status'),
            componentMixins.backboneMixin('nodes', 'add remove change'),
            componentMixins.backboneMixin({
                modelOrCollection: function(props) {return props.cluster.get('tasks');},
                renderOn: 'add remove change:status'
            })
        ],
        getInitialState: function() {
            return {
                loading: this.props.mode == 'add',
                filter: '',
                grouping: this.props.mode == 'add' ? 'hardware' : this.props.cluster.get('grouping'),
                selectedNodeIds: this.props.nodes.reduce(function(result, node) {
                    result[node.id] = this.props.mode == 'edit';
                    return result;
                }, {}, this)
            };
        },
        selectNodes: function(ids, name, checked) {
            var nodeSelection = this.state.selectedNodeIds;
            _.each(ids, function(id) {nodeSelection[id] = checked;});
            this.setState({selectedNodeIds: nodeSelection});
        },
        shouldDataBeFetched: function() {
            return !this.state.loading;
        },
        fetchData: function() {
            return this.props.nodes.fetch();
        },
        componentWillMount: function() {
            var clusterId = this.props.mode == 'add' ? '' : this.props.cluster.id;
            this.props.nodes.fetch = function(options) {
                return this.constructor.__super__.fetch.call(this, _.extend({data: {cluster_id: clusterId}}, options));
            };
            if (this.props.mode == 'edit') {
                var ids = this.props.nodes.pluck('id');
                this.props.nodes.parse = function(response) {
                    return _.filter(response, function(node) {return _.contains(ids, node.id);});
                };
            }
            this.updateInitialRoles();
            this.props.nodes.on('add remove reset', this.updateInitialRoles, this);
            // hack to prevent node roles update after node polling
            if (this.props.mode != 'list') this.props.nodes.on('change:pending_roles', this.checkRoleAssignment, this);
        },
        componentWillUnmount: function() {
            this.props.nodes.off('add remove reset', this.updateInitialRoles, this);
            this.props.nodes.off('change:pending_roles', this.checkRoleAssignment, this);
        },
        updateInitialRoles: function() {
            this.initialRoles = _.zipObject(this.props.nodes.pluck('id'), this.props.nodes.pluck('pending_roles'));
        },
        checkRoleAssignment: function(node, roles, options) {
            if (!options.assign) node.set({pending_roles: node.previous('pending_roles')}, {assign: true});
        },
        componentDidMount: function() {
            if (this.props.mode == 'add') {
                $.when(this.props.nodes.fetch(), this.props.cluster.get('settings').fetch({cache: true})).always(_.bind(function() {
                    this.setState({loading: false});
                    this.scheduleDataFetch();
                }, this));
            }
        },
        hasChanges: function() {
            return this.props.nodes.any(function(node) {
                return !_.isEqual(node.get('pending_roles'), this.initialRoles[node.id]);
            }, this);
        },
        changeFilter: _.debounce(function(value) {
            this.setState({filter: value});
        }, 200),
        clearFilter: function() {
            this.setState({filter: ''});
        },
        changeGrouping: function(name, value) {
            this.setState({grouping: value});
            this.props.cluster.save({grouping: value}, {patch: true, wait: true});
        },
        revertChanges: function() {
            this.props.nodes.each(function(node) {
                node.set({pending_roles: this.initialRoles[node.id]}, {silent: true});
            }, this);
        },
        render: function() {
            var locked = !!this.props.cluster.tasks({group: 'deployment', status: 'running'}).length,
                nodes = this.props.nodes;
            return (
                <div>
                    {this.props.mode == 'edit' &&
                        <div className='alert'>{i18n('cluster_page.nodes_tab.disk_configuration_reset_warning')}</div>
                    }
                    <ManagementPanel
                        mode={this.props.mode}
                        nodes={new models.Nodes(_.compact(_.map(this.state.selectedNodeIds, function(checked, id) {
                            if (checked) return nodes.get(id);
                        })))}
                        totalNodeAmount={nodes.length}
                        cluster={this.props.cluster}
                        grouping={this.state.grouping}
                        changeGrouping={this.changeGrouping}
                        filter={this.state.filter}
                        filtering={this.state.filtering}
                        changeFilter={this.changeFilter}
                        clearFilter={this.clearFilter}
                        hasChanges={!this.isMounted() || this.hasChanges()}
                        locked={locked || this.state.loading}
                        revertChanges={this.revertChanges}
                    />
                    {this.state.loading ? <controls.ProgressBar /> :
                        <div>
                            {this.props.mode != 'list' && <RolePanel {...this.props} selectedNodeIds={this.state.selectedNodeIds} />}
                            <NodeList {...this.props}
                                nodes={nodes.filter(function(node) {
                                    return _.contains(node.get('name').concat(' ', node.get('mac')).toLowerCase(), this.state.filter.toLowerCase());
                                }, this)}
                                grouping={this.state.grouping}
                                locked={locked}
                                selectedNodeIds={this.state.selectedNodeIds}
                                selectNodes={this.selectNodes}
                            />
                        </div>
                    }
                </div>
            );
        }
    });

    ManagementPanel = React.createClass({
        getInitialState: function() {
            return {
                isFilterButtonVisible: !!this.props.filter,
                actionInProgress: false
            };
        },
        changeScreen: function(url, passNodeIds) {
            if (!url) this.props.revertChanges();
            url = url ? '/' + url : '';
            if (passNodeIds) url += '/' + utils.serializeTabOptions({nodes: this.props.nodes.pluck('id')});
            app.navigate('#cluster/' + this.props.cluster.id + '/nodes' + url, {trigger: true});
        },
        goToConfigurationScreen: function(action, conflict) {
            if (conflict) {
                var ns = 'cluster_page.nodes_tab.node_management_panel.node_management_error.';
                utils.showErrorDialog({title: i18n(ns + 'title'), message: i18n(ns + action + '_configuration_warning')});
                return;
            }
            this.changeScreen(action, true);
        },
        showDeleteNodesDialog: function() {
            dialogs.DeleteNodesDialog.show({nodes: this.props.nodes, cluster: this.props.cluster});
        },
        applyChanges: function() {
            this.setState({actionInProgress: true});
            var nodes = new models.Nodes(this.props.nodes.map(function(node) {
                var data = {id: node.id, pending_roles: node.get('pending_roles')};
                if (node.get('pending_roles').length) {
                    if (this.props.mode == 'add') return _.extend(data, {cluster_id: this.props.cluster.id, pending_addition: true});
                } else {
                    if (node.get('pending_addition')) return _.extend(data, {cluster_id: null, pending_addition: false});
                }
                return data;
            }, this));
            Backbone.sync('update', nodes)
                .done(_.bind(function() {
                    $.when(this.props.cluster.fetch(), this.props.cluster.fetchRelated('nodes')).always(_.bind(function() {
                        this.changeScreen();
                        dispatcher.trigger('updateNodeStats networkConfigurationUpdated');
                    }, this));
                }, this))
                .fail(_.bind(function(response) {
                    this.setState({actionInProgress: false});
                    utils.showErrorDialog({
                        message: i18n('cluster_page.nodes_tab.node_management_panel.node_management_error.saving_warning'),
                        response: response
                    });
                }, this));
        },
        startFiltering: function(name, value) {
            this.setState({isFilterButtonVisible: !!value});
            this.props.changeFilter(value);
        },
        clearFilter: function() {
            this.setState({isFilterButtonVisible: false});
            this.refs.filter.getInputDOMNode().value = '';
            this.props.clearFilter();
        },
        render: function() {
            var ns = 'cluster_page.nodes_tab.node_management_panel.',
                sampleNode = this.props.nodes.at(0),
                disksConflict = this.props.nodes.any(function(node) {
                    var roleConflict = _.difference(_.union(sampleNode.get('roles'), sampleNode.get('pending_roles')), _.union(node.get('roles'), node.get('pending_roles'))).length;
                    return roleConflict || !_.isEqual(sampleNode.resource('disks'), node.resource('disks'));
                }),
                interfaceConflict = _.uniq(this.props.nodes.map(function(node) {return node.resource('interfaces');})).length > 1;
            return (
                <div className='row'>
                    <div id='sticker' className='node-management-panel'>
                        <div className='col-xs-2'>
                            <div className='filter-group'>
                                <controls.Input
                                    type='select'
                                    name='grouping'
                                    label={i18n(ns + 'group_by')}
                                    children={_.map(this.props.cluster.groupings(), function(label, grouping) {
                                        return <option key={grouping} value={grouping}>{label}</option>;
                                    })}
                                    defaultValue={this.props.grouping}
                                    disabled={!this.props.totalNodeAmount || this.props.mode == 'add'}
                                    onChange={this.props.changeGrouping}
                                    inputClassName='form-control'
                                />
                            </div>
                        </div>
                        <div className='col-xs-2'>
                            <div className='filter-group'>
                                <controls.Input
                                    type='text'
                                    name='filter'
                                    ref='filter'
                                    defaultValue={this.props.filter}
                                    label={i18n(ns + 'filter_by')}
                                    placeholder={i18n(ns + 'filter_placeholder')}
                                    disabled={!this.props.totalNodeAmount}
                                    onChange={this.startFiltering}
                                    inputClassName='form-control'
                                />
                                {this.state.isFilterButtonVisible &&
                                    <button className='close btn-clear-filter' onClick={this.clearFilter}>&times;</button>
                                }
                            </div>
                        </div>
                        <div className='col-xs-8'>
                            <div className='control-buttons-box pull-right'>
                                {this.props.mode != 'list' ?
                                    <div className='btn-group' role='group'>
                                        <button
                                            className='btn btn-default'
                                            disabled={this.state.actionInProgress}
                                            onClick={_.bind(this.changeScreen, this, '', false)}
                                        >
                                            {i18n('common.cancel_button')}
                                        </button>
                                        <button
                                            className='btn btn-success btn-apply'
                                            disabled={this.state.actionInProgress || !this.props.hasChanges}
                                            onClick={this.applyChanges}
                                        >
                                            {i18n('common.apply_changes_button')}
                                        </button>
                                    </div>
                                :
                                    [
                                        <div className='btn-group' role='group' key='configuration-buttons'>
                                            <button
                                                className='btn btn-default btn-configure-disks'
                                                disabled={this.props.locked || !this.props.nodes.length}
                                                onClick={_.bind(this.goToConfigurationScreen, this, 'disks', disksConflict)}
                                            >
                                                {disksConflict && <i className='glyphicon glyphicon-warning-sign text-red' />}
                                                {i18n('dialog.show_node.disk_configuration_button')}
                                            </button>
                                            {!this.props.nodes.any({status: 'error'}) &&
                                                <button
                                                    className='btn btn-default btn-configure-interfaces'
                                                    disabled={this.props.locked || !this.props.nodes.length}
                                                    onClick={_.bind(this.goToConfigurationScreen, this, 'interfaces', interfaceConflict)}
                                                >
                                                    {interfaceConflict && <i className='glyphicon glyphicon-warning-sign text-red' />}
                                                    {i18n('dialog.show_node.network_configuration_button')}
                                                </button>
                                            }
                                        </div>,
                                        <div className='btn-group' role='group' key='role-management-buttons'>
                                            {!!this.props.nodes.length && this.props.nodes.any({pending_deletion: false}) &&
                                                <button
                                                    className='btn btn-danger btn-delete-nodes'
                                                    onClick={this.showDeleteNodesDialog}
                                                >
                                                    <i className='glyphicon glyphicon-trash' />
                                                    {i18n('common.delete_button')}
                                                </button>
                                            }
                                            {!!this.props.nodes.length && !this.props.nodes.any({pending_addition: false}) &&
                                                <button
                                                    className='btn btn-success btn-edit-roles'
                                                    onClick={_.bind(this.changeScreen, this, 'edit', true)}
                                                >
                                                    <i className='glyphicon glyphicon-edit' />
                                                    {i18n(ns + 'edit_roles_button')}
                                                </button>
                                            }
                                            {!this.props.nodes.length &&
                                                <button
                                                    className='btn btn-success btn-add-nodes'
                                                    onClick={_.bind(this.changeScreen, this, 'add', false)}
                                                    disabled={this.props.locked}
                                                >
                                                    <i className='glyphicon glyphicon-plus' />
                                                    {i18n(ns + 'add_nodes_button')}
                                                </button>
                                            }
                                        </div>
                                    ]
                                }
                            </div>
                        </div>
                    </div>
                </div>
            );
        }
    });

    RolePanel = React.createClass({
        getInitialState: function() {
            var settings = this.props.cluster.get('settings'),
                roles = this.props.cluster.get('release').get('roles'),
                selectedRoles = this.props.nodes.length ? _.filter(roles, function(role) {
                    return !this.props.nodes.any(function(node) {return !node.hasRole(role);});
                }, this) : [];
            return {
                configModels: {
                    cluster: this.props.cluster,
                    settings: settings,
                    version: app.version,
                    default: settings
                },
                selectedRoles: selectedRoles,
                indeterminateRoles: this.props.nodes.length ? _.filter(_.difference(roles, selectedRoles), function(role) {
                    return this.props.nodes.any(function(node) {return node.hasRole(role);});
                }, this) : []
            };
        },
        componentDidMount: function() {
            this.updateIndeterminateRolesState();
        },
        componentDidUpdate: function() {
            this.updateIndeterminateRolesState();
            this.assignRoles();
        },
        updateIndeterminateRolesState: function() {
            _.each(this.refs, function(roleView, role) {
                roleView.getInputDOMNode().indeterminate = _.contains(this.state.indeterminateRoles, role);
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
            });
        },
        getNodesForLimitsCheck: function() {
            var selectedNodes = this.props.nodes.filter(function(node) {
                    return this.props.selectedNodeIds[node.id];
                }, this),
                clusterNodes = this.props.cluster.get('nodes').filter(function(node) {
                    return !_.contains(this.props.selectedNodeIds, node.id);
                }, this);
            return new models.Nodes(_.union(selectedNodes, clusterNodes));
        },
        assignRoles: function() {
            var roles = this.props.cluster.get('release').get('role_models'),
                nodesForLimitsCheck = this.getNodesForLimitsCheck();
            this.props.nodes.each(function(node) {
                if (this.props.selectedNodeIds[node.id]) roles.each(function(role) {
                    var roleName = role.get('name');
                    if (!node.hasRole(roleName, true)) {
                        var nodeRoles = node.get('pending_roles');
                        if (_.contains(this.state.selectedRoles, roleName)) {
                            if (this.checkLimits(role, nodesForLimitsCheck).valid) nodeRoles = _.union(nodeRoles, [roleName]);
                        } else if (!_.contains(this.state.indeterminateRoles, roleName)) {
                            nodeRoles = _.without(nodeRoles, roleName);
                        }
                        node.set({pending_roles: nodeRoles}, {assign: true});
                    }
                }, this);
            }, this);
        },
        checkLimits: function(role, nodes) {
            return role.checkLimits(this.state.configModels, false, ['max'], nodes);
        },
        processRestrictions: function(role, models, nodes) {
            var name = role.get('name'),
                restrictionsCheck = role.checkRestrictions(models, 'disable'),
                limitsCheck = this.checkLimits(role, nodes),
                roles = this.props.cluster.get('release').get('role_models'),
                conflicts = _.chain(this.state.selectedRoles)
                    .union(this.state.indeterminateRoles)
                    .map(function(role) {return roles.findWhere({name: role}).conflicts;})
                    .flatten()
                    .uniq()
                    .value(),
                messages = [];
            if (restrictionsCheck.result && restrictionsCheck.message) messages.push(restrictionsCheck.message);
            if (!limitsCheck.valid && limitsCheck.message) messages.push(limitsCheck.message);
            if (_.contains(conflicts, name)) messages.push(i18n('cluster_page.nodes_tab.role_conflict'));
            return {
                result: restrictionsCheck.result || _.contains(conflicts, name) || (!limitsCheck.valid && !_.contains(this.state.selectedRoles, name)),
                message: messages.join(' ')
            };
        },
        render: function() {
            var nodesForLimitsCheck = this.getNodesForLimitsCheck();
            return (
                <div className='role-panel'>
                    <h4>{i18n('cluster_page.nodes_tab.assign_roles')}</h4>
                    {this.props.cluster.get('release').get('role_models').map(function(role) {
                        if (!role.checkRestrictions(this.state.configModels, 'hide').result) {
                            var name = role.get('name'),
                                processedRestrictions = this.props.nodes.length ? this.processRestrictions(role, this.state.configModels, nodesForLimitsCheck) : {};
                            return (
                                <controls.Input
                                    key={name}
                                    ref={name}
                                    type='checkbox'
                                    name={name}
                                    label={role.get('label')}
                                    description={role.get('description')}
                                    defaultChecked={_.contains(this.state.selectedRoles, name)}
                                    disabled={!this.props.nodes.length || processedRestrictions.result}
                                    tooltipText={!!this.props.nodes.length && processedRestrictions.message}
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
        componentDidUpdate: function() {
            if (this.props.nodes.length) {
                var input = this.refs['select-all'].getInputDOMNode();
                input.indeterminate = !input.checked && _.any(this.props.nodes, function(node) {return this.props.selectedNodeIds[node.id];}, this);
            }
        },
        renderSelectAllCheckbox: function() {
            var availableNodesIds = _.compact(this.props.nodes.map(function(node) {if (node.isSelectable()) return node.id;}));
            return (
                <controls.Input
                    ref='select-all'
                    type='checkbox'
                    checked={this.props.mode == 'edit' || (availableNodesIds.length && !_.any(availableNodesIds, function(id) {return !this.props.selectedNodeIds[id];}, this))}
                    disabled={this.props.mode == 'edit' || this.props.locked || !availableNodesIds.length}
                    label={i18n('common.select_all')}
                    wrapperClassName='select-all pull-right'
                    onChange={_.bind(this.props.selectNodes, this.props, availableNodesIds)}
                />
            );
        }
    };

    NodeList = React.createClass({
        mixins: [SelectAllMixin],
        getEmptyListWarning: function() {
            var ns = 'cluster_page.nodes_tab.';
            if (this.props.mode == 'add') return i18n(ns + 'no_nodes_in_fuel');
            if (this.props.cluster.get('nodes').length) return i18n(ns + 'no_filtered_nodes_warning');
            return i18n(ns + 'no_nodes_in_environment');
        },
        groupNodes: function() {
            var releaseRoles = this.props.cluster.get('release').get('role_models'),
                method = _.bind(function(node) {
                    if (this.props.grouping == 'roles') return node.getRolesSummary(releaseRoles);
                    if (this.props.grouping == 'hardware') return node.getHardwareSummary();
                    return node.getRolesSummary(releaseRoles) + '; \u00A0' + node.getHardwareSummary();
                }, this),
                groups = _.pairs(_.groupBy(this.props.nodes, method));
            if (this.props.grouping == 'hardware') return _.sortBy(groups, _.first);
            var preferredOrder = releaseRoles.pluck('name');
            return groups.sort(function(group1, group2) {
                var roles1 = group1[1][0].sortedRoles(preferredOrder),
                    roles2 = group2[1][0].sortedRoles(preferredOrder),
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
                <div className='node-list row'>
                    {!!groups.length && <div className='col-xs-12 node-list-header'>{this.renderSelectAllCheckbox()}</div>}
                    <div className='col-xs-12'>
                        {groups.length ?
                            groups.map(function(group) {
                                return <NodeGroup {...this.props} key={group[0]} label={group[0]} nodes={group[1]} />;
                            }, this)
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
                <div className='nodes-group'>
                    <div className='row'>
                        <div className='col-xs-10'>
                            <h4>{this.props.label} ({this.props.nodes.length})</h4>
                        </div>
                        <div className='col-xs-2'>
                            {this.renderSelectAllCheckbox()}
                        </div>
                    </div>
                    <div>
                        {this.props.nodes.map(function(node) {
                            return <Node
                                key={node.id}
                                node={node}
                                checked={this.props.mode == 'edit' || this.props.selectedNodeIds[node.id]}
                                cluster={this.props.cluster}
                                locked={this.props.mode == 'edit' || this.props.locked}
                                onNodeSelection={_.bind(this.props.selectNodes, this.props, [node.id])}
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
                actionInProgress: false,
                eventNamespace: 'click.editnodename' + this.props.node.id
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
                if ($(e.target).hasClass('node-name')) {
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
        removeNode: function() {
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
            dialogs.ShowNodeInfoDialog.show({node: this.props.node});
        },
        calculateNodeViewStatus: function() {
            var node = this.props.node;
            // 'removing' status has priority over 'offline'
            if (node.get('status') == 'removing') return 'removing';
            if (!node.get('online')) return 'offline';
            if (node.get('pending_addition')) return 'pending_addition';
            if (node.get('pending_deletion')) return 'pending_deletion';
            // 'error' status has priority over 'discover'
            if (node.get('status') == 'error') return 'error';
            if (!node.get('cluster')) return 'discover';
            return node.get('status');
        },
        sortRoles: function(roles) {
            var preferredOrder = this.props.cluster.get('release').get('roles');
            return roles.sort(function(a, b) {
                return _.indexOf(preferredOrder, a) - _.indexOf(preferredOrder, b);
            });
        },
        render: function() {
            var ns = 'cluster_page.nodes_tab.node.',
                node = this.props.node,
                disabled = this.props.locked || !node.isSelectable() || this.state.actionInProgress,
                deployedRoles = node.get('roles'),
                rolesToDisplay = deployedRoles.length ? deployedRoles : node.get('pending_roles'),
                nodeProgess = _.max([node.get('progress'), 3]),
                status = this.calculateNodeViewStatus();

            // compose classes
            var nodePanelClasses = {
                node: true,
                selected: this.props.checked
            };
            nodePanelClasses[status] = status;

            var manufacturer = node.get('manufacturer'),
                logoClasses = {
                    'manufacturer-logo': true
                };
            logoClasses[manufacturer.toLowerCase()] = manufacturer;

            var nameClasses = {
                name: true,
                semibold: !this.state.renaming
            };

            var roleClasses = {'text-green': !deployedRoles.length};

            var statusClasses = {
                    'node-status': true
                },
                statusClass = {
                    pending_addition: 'text-green',
                    pending_deletion: 'text-orange',
                    error: 'text-red',
                    ready: 'text-blue',
                    provisioning: 'text-blue',
                    deploying: 'text-green',
                    provisioned: 'text-blue'
                }[status];
            statusClasses[statusClass] = true;

            return (
                <div className={utils.classNames(nodePanelClasses)}>
                    <label className='node-box'>
                        <controls.Input
                            type='checkbox'
                            name={node.id}
                            checked={this.props.checked}
                            disabled={disabled}
                            onChange={this.props.onNodeSelection}
                            wrapperClassName='check-box'
                        />
                        <div className={utils.classNames(logoClasses)} />
                        <div className='node-name'>
                            <div className={utils.classNames(nameClasses)}>
                                {this.state.renaming ?
                                    <p>
                                        <controls.Input
                                            ref='name'
                                            type='text'
                                            defaultValue={node.get('name')}
                                            inputClassName='form-control'
                                            disabled={this.state.actionInProgress}
                                            onKeyDown={this.onNodeNameInputKeydown}
                                            autoFocus
                                        />
                                    </p>
                                :
                                    <p title={i18n(ns + 'edit_name')} onClick={!disabled && this.startNodeRenaming}>
                                        {node.get('name') || node.get('mac')}
                                    </p>
                                }
                            </div>
                            <div className='role-list'>
                                {!!rolesToDisplay.length &&
                                    <ul>
                                        {_.map(this.sortRoles(rolesToDisplay), function(role) {
                                            return <li key={node.id + role} className={utils.classNames(roleClasses)}>{role}</li>;
                                        })}
                                    </ul>
                                }
                            </div>
                        </div>
                        <div className='node-action'>
                            {!!node.get('cluster') &&
                                ((this.props.locked || !node.hasChanges()) ?
                                    <a className='btn btn-link' title={i18n(ns + 'view_logs')} href={this.getNodeLogsLink()}>
                                        <i className='icon-logs' />
                                    </a>
                                :
                                    <div
                                        className='icon node-discard-changes-icon'
                                        title={i18n(ns + (node.get('pending_addition') ? 'discard_addition' : 'discard_deletion'))}
                                        onClick={this.discardNodeChanges}
                                    />
                                )
                            }
                        </div>
                        <div className={utils.classNames(statusClasses)}>
                            {_.contains(['provisioning', 'deploying'], status) ?
                                <div className='progress'>
                                    <div
                                        className='progress-bar'
                                        role='progressbar'
                                        style={{width: nodeProgess + '%'}}
                                    >
                                        {nodeProgess + '%'}
                                    </div>
                                </div>
                            :
                                <div>
                                    <span>{i18n(ns + 'status.' + status, {os: this.props.cluster.get('release').get('operating_system') || 'OS'})}</span>
                                    {status == 'offline' &&
                                        <button onClick={this.removeNode} className='node-remove-button'>{i18n(ns + 'remove')}</button>
                                    }
                                </div>
                            }
                        </div>
                        <div className='node-hardware'>
                            <span>{i18n('node_details.cpu')}: {node.resource('cores') || '0'} ({node.resource('ht_cores') || '?'})</span>
                            <span>{i18n('node_details.hdd')}: {node.resource('hdd') ? utils.showDiskSize(node.resource('hdd')) : '?' + i18n('common.size.gb')}</span>
                            <span>{i18n('node_details.ram')}: {node.resource('ram') ? utils.showMemorySize(node.resource('ram')) : '?' + i18n('common.size.gb')}</span>
                        </div>
                        <div className='node-settings' onClick={this.showNodeDetails} />
                    </label>
                </div>
            );
        }
    });

    return NodeListScreen;
});
