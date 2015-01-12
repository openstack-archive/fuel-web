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
    'react',
    'utils',
    'models',
    'jsx!views/controls',
    'jsx!views/dialogs',
    'jsx!component_mixins'
],
function($, _, i18n, React, utils, models, controls, dialogs, componentMixins) {
    'use strict';
    var cx = React.addons.classSet,
        NodeListScreen, ManagementPanel, RolePanel, SelectAllMixin, NodeList, NodeGroup, Node;

    NodeListScreen = React.createClass({
        mixins: [
            componentMixins.pollingMixin(20),
            componentMixins.backboneMixin('cluster', 'change:status'),
            componentMixins.backboneMixin('nodes', 'add remove change'),
            componentMixins.backboneMixin({
                modelOrCollection: function(props) {return props.cluster.get('tasks');},
                renderOn: 'add remove change:status'
            })
        ],
        getInitialState: function() {
            return {
                loading: true,
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
                }, this));
            } else {
                this.setState({loading: false});
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
            var assignedRoles = _.chain(this.props.nodes.pluck('roles')).union(this.props.nodes.pluck('pending_roles')).flatten().uniq().value(),
                locked = !!this.props.cluster.tasks({group: 'deployment', status: 'running'}).length;
            return (
                <div>
                    {this.props.mode == 'edit' &&
                        <div className='alert'>{i18n('cluster_page.nodes_tab.disk_configuration_reset_warning')}</div>
                    }
                    <ManagementPanel
                        mode={this.props.mode}
                        nodes={new models.Nodes(_.compact(_.map(this.state.selectedNodeIds, function(checked, id) {
                            if (checked) return this.props.nodes.get(id);
                        }, this)))}
                        totalNodeAmount={this.props.nodes.length}
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
                                nodes={this.props.nodes.models}
                                grouping={this.state.grouping}
                                filter={this.state.filter}
                                locked={locked}
                                selectedNodeIds={this.state.selectedNodeIds}
                                selectNodes={this.selectNodes}
                                // FIXME: one more role limits hack
                                roleLimitation={(this.props.cluster.get('mode') == 'multi-node' && _.contains(assignedRoles, 'controller')) || _.contains(assignedRoles, 'zabbix-server')}
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
            utils.showDialog(dialogs.DeleteNodesDialog, {nodes: this.props.nodes, cluster: this.props.cluster});
        },
        applyChanges: function() {
            this.setState({actionInProgress: true});
            this.props.nodes.each(function(node) {
                var data;
                if (node.get('pending_roles').length) {
                    if (this.props.mode == 'add') data = {cluster_id: this.props.cluster.id, pending_addition: true};
                } else {
                    if (node.get('pending_addition')) data = {cluster_id: null, pending_addition: false};
                }
                node.set(data, {silent: true});
            }, this);
            this.props.nodes.toJSON = function() {
                return this.map(function(node) {
                    return _.pick(node.attributes, 'id', 'cluster_id', 'pending_roles', 'pending_addition');
                });
            };
            this.props.nodes.sync('update', this.props.nodes)
                .done(_.bind(function() {
                    $.when(this.props.cluster.fetch(), this.props.cluster.fetchRelated('nodes')).always(_.bind(function() {
                        this.changeScreen();
                        app.navbar.refresh();
                        app.page.removeFinishedNetworkTasks();
                    }, this));
                }, this))
                .fail(_.bind(function() {
                    this.setState({actionInProgress: false});
                    utils.showErrorDialog({message: i18n('cluster_page.nodes_tab.node_management_panel.node_management_error.saving_warning')});
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
                <div className='node-management-panel'>
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
                    />
                    <div className='node-filter'>
                        <controls.Input
                            type='text'
                            name='filter'
                            ref='filter'
                            defaultValue={this.props.filter}
                            label={i18n(ns + 'filter_by')}
                            placeholder={i18n(ns + 'filter_placeholder')}
                            disabled={!this.props.totalNodeAmount}
                            onChange={this.startFiltering}
                        />
                        {this.state.isFilterButtonVisible &&
                            <button className='close btn-clear-filter' onClick={this.clearFilter}>&times;</button>
                        }
                    </div>
                    <div className='buttons'>
                        {this.props.mode != 'list' ? [
                            <button
                                key='cancel'
                                className='btn'
                                disabled={this.state.actionInProgress}
                                onClick={_.bind(this.changeScreen, this, '', false)}
                            >
                                {i18n('common.cancel_button')}
                            </button>,
                            <button
                                key='apply'
                                className='btn btn-success btn-apply'
                                disabled={this.state.actionInProgress || !this.props.hasChanges}
                                onClick={this.applyChanges}
                            >
                                {i18n('common.apply_changes_button')}
                            </button>
                        ] : [
                            <button
                                key='disks'
                                className={cx({'btn btn-configure-disks': true, conflict: disksConflict})}
                                disabled={this.props.locked || !this.props.nodes.length}
                                onClick={_.bind(this.goToConfigurationScreen, this, 'disks', disksConflict)}
                            >
                                {disksConflict && <i className='icon-attention text-error' />}
                                <span>{i18n('dialog.show_node.disk_configuration_button')}</span>
                            </button>,
                            !this.props.nodes.any(function(node) {return node.get('status') == 'error';}) &&
                                <button
                                    key='interfaces'
                                    className={cx({'btn btn-configure-interfaces': true, conflict: interfaceConflict})}
                                    disabled={this.props.locked || !this.props.nodes.length}
                                    onClick={_.bind(this.goToConfigurationScreen, this, 'interfaces', interfaceConflict)}
                                >
                                    {interfaceConflict && <i className='icon-attention text-error' />}
                                    <span>{i18n('dialog.show_node.network_configuration_button')}</span>
                                </button>,
                            !!this.props.nodes.length && this.props.nodes.any(function(node) {return !node.get('pending_deletion');}) &&
                                <button
                                    key='delete'
                                    className='btn btn-danger btn-delete-nodes'
                                    onClick={this.showDeleteNodesDialog}
                                >
                                    <i className='icon-trash' />
                                    <span>{i18n('common.delete_button')}</span>
                                </button>,
                            !!this.props.nodes.length && !this.props.nodes.any(function(node) {return !node.get('pending_addition');}) &&
                                <button
                                    key='roles'
                                    className='btn btn-success btn-edit-roles'
                                    onClick={_.bind(this.changeScreen, this, 'edit', true)}
                                >
                                    <i className='icon-edit' />
                                    <span>{i18n(ns + 'edit_roles_button')}</span>
                                </button>,
                            !this.props.nodes.length &&
                                <button
                                    key='add'
                                    className='btn btn-success btn-add-nodes'
                                    onClick={_.bind(this.changeScreen, this, 'add', false)}
                                    disabled={this.props.locked}
                                >
                                    <i className='icon-plus' />
                                    <span>{i18n(ns + 'add_nodes_button')}</span>
                                </button>
                        ]}
                    </div>
                </div>
            );
        }
    });

    RolePanel = React.createClass({
        getInitialState: function() {
            var roles = this.props.cluster.get('release').get('roles'),
                selectedRoles = this.props.nodes.length ? _.filter(roles, function(role) {
                    return !this.props.nodes.any(function(node) {return !node.hasRole(role);});
                }, this) : [];
            return {
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
        assignRoles: function() {
            var roles = this.props.cluster.get('release').get('roles');
            this.props.nodes.each(function(node) {
                if (this.props.selectedNodeIds[node.id]) _.each(roles, function(role) {
                    if (!node.hasRole(role, true)) {
                        var nodeRoles = node.get('pending_roles');
                        if (_.contains(this.state.selectedRoles, role)) {
                            if (this.isRoleAvailable(role)) nodeRoles = _.union(nodeRoles, [role]);
                        } else if (!_.contains(this.state.indeterminateRoles, role)) {
                            nodeRoles = _.without(nodeRoles, role);
                        }
                        node.set({pending_roles: nodeRoles}, {assign: true});
                    }
                }, this);
            }, this);
        },
        isRoleAvailable: function(role) {
            // FIXME: the following hack should be described declaratively in yaml
            if ((role == 'controller' && this.props.cluster.get('mode') == 'multinode') || role == 'zabbix-server') {
                return _.compact(_.values(this.props.selectedNodeIds)).length <= 1 && !this.props.cluster.get('nodes').any(function(node) {
                    return !this.props.selectedNodeIds[node.id] && node.hasRole(role) && !node.get('pending_deletion');
                }, this);
            }
            return true;
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
                isAvailable = this.isRoleAvailable(name),
                messages = [];
            if (restrictionsCheck.message) messages.push(restrictionsCheck.message);
            if (_.contains(conflicts, name)) messages.push(i18n('cluster_page.nodes_tab.role_conflict'));
            if (!isAvailable) messages.push(i18n('cluster_page.nodes_tab.' + name + '_restriction'));
            return {
                result: restrictionsCheck.result || _.contains(conflicts, name) || (!isAvailable && !_.contains(this.state.selectedRoles, name)),
                message: messages.join(' ')
            };
        },
        render: function() {
            var settings = this.props.cluster.get('settings'),
                configModels = {
                    cluster: this.props.cluster,
                    settings: settings,
                    version: app.version,
                    default: settings
                };
            return (
                <div className='role-panel'>
                    <h4>{i18n('cluster_page.nodes_tab.assign_roles')}</h4>
                    {this.props.cluster.get('release').get('role_models').map(function(role) {
                        if (!role.checkRestrictions(configModels, 'hide').result) {
                            var name = role.get('name'),
                                processedRestrictions = this.props.nodes.length ? this.processRestrictions(role, configModels) : {};
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
                    disabled={this.props.mode == 'edit' || this.props.locked || !availableNodesIds.length || (this.props.roleLimitation && availableNodesIds.length > 1)}
                    label={i18n('common.select_all')}
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
            if (this.props.mode == 'add') return i18n(ns + 'no_nodes_in_fuel');
            if (this.props.cluster.get('nodes').length) return i18n(ns + 'no_filtered_nodes_warning');
            return i18n(ns + 'no_nodes_in_environment');
        },
        groupNodes: function() {
            var nodes = _.filter(this.props.nodes, function(node) {
                    return _.contains(node.get('name').concat(' ', node.get('mac')).toLowerCase(), this.props.filter);
                }, this),
                releaseRoles = this.props.cluster.get('release').get('role_models'),
                method = _.bind(function(node) {
                    if (this.props.grouping == 'roles') return node.getRolesSummary(releaseRoles);
                    if (this.props.grouping == 'hardware') return node.getHardwareSummary();
                    return node.getRolesSummary(releaseRoles) + '; \u00A0' + node.getHardwareSummary();
                }, this),
                groups = _.pairs(_.groupBy(nodes, method));
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
                                    return <NodeGroup {...this.props}
                                        key={group[0]}
                                        label={group[0]}
                                        nodes={group[1]}
                                    />;
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
            var data = this.props.node.get('pending_addition') ? {cluster_id: null, pending_addition: false, pending_roles: []} : {pending_deletion: false};
            this.props.node.save(data, {patch: true, wait: true, silent: true})
                .done(_.bind(function() {
                    $.when(this.props.cluster.fetch(), this.props.cluster.fetchRelated('nodes')).done(_.bind(function() {
                        this.setState({actionInProgress: false});
                    }, this));
                    app.navbar.refresh();
                    app.page.removeFinishedNetworkTasks();
                }, this))
                .fail(function() {utils.showErrorDialog({title: i18n('dialog.discard_changes.cant_discard')});});
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
        showNodeDetails: function(e) {
            e.preventDefault();
            utils.showDialog(dialogs.ShowNodeInfoDialog, {
                node: this.props.node,
                title: this.props.node.get('name') || this.props.node.get('mac')
            });
        },
        calculateNodeViewStatus: function() {
            var node = this.props.node;
            if (!node.get('online')) return 'offline';
            if (node.get('pending_addition')) return 'pending_addition';
            if (node.get('pending_deletion')) return 'pending_deletion';
            return node.get('status');
        },
        sortRoles: function(roles) {
            var preferredOrder = this.props.cluster.get('release').get('roles');
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
        render: function() {
            var ns = 'cluster_page.nodes_tab.node.',
                node = this.props.node,
                disabled = this.props.locked || !node.isSelectable() || this.state.actionInProgress,
                roles = [this.renderRoleList('roles'), this.renderRoleList('pending_roles')];
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
                            onChange={this.props.onNodeSelection}
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
                                        <p title={i18n(ns + 'edit_name')} onClick={!disabled && this.startNodeRenaming}>
                                            {node.get('name') || node.get('mac')}
                                        </p>
                                    }
                                </div>
                                <div className='role-list'>
                                    {_.compact(roles).length ? roles : i18n(ns + 'unallocated')}
                                </div>
                            </div>
                            <div className='node-button'>
                                {!!node.get('cluster') && (
                                    (this.props.locked || !node.hasChanges()) ?
                                        <a className='btn btn-link' title={i18n(ns + 'view_logs')} href={this.getNodeLogsLink()}>
                                            <i className='icon-logs' />
                                        </a>
                                    :
                                        <button
                                            className='btn btn-link'
                                            title={i18n(ns + (node.get('pending_addition') ? 'discard_addition' : 'discard_deletion'))}
                                            onClick={this.discardNodeChanges}
                                        >
                                            <i className='icon-back-in-time' />
                                        </button>
                                )}
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
                                        {i18n(ns + 'status.' + status, {os: this.props.cluster.get('release').get('operating_system') || 'OS'})}
                                    </span>
                                </div>
                            </div>
                            <div className='node-details' onClick={this.showNodeDetails} />
                            <div className='node-hardware'>
                                <span>
                                    {i18n('node_details.cpu')}: {node.resource('cores') || '0'} ({node.resource('ht_cores') || '?'})
                                </span>
                                <span>
                                    {i18n('node_details.hdd')}: {node.resource('hdd') ? utils.showDiskSize(node.resource('hdd')) : '?' + i18n('common.size.gb')}
                                </span>
                                <span>
                                    {i18n('node_details.ram')}: {node.resource('ram') ? utils.showMemorySize(node.resource('ram')) : '?' + i18n('common.size.gb')}
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
