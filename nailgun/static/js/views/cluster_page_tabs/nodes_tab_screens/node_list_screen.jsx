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
    'expression',
    'jsx!component_mixins',
    'jsx!views/dialogs',
    'jsx!views/controls'
],
function(React, utils, models, Expression, componentMixins, dialogs, controls) {
    'use strict';

    var cx = React.addons.classSet;

    var NodeListScreen = React.createClass({
        mixins: [
            componentMixins.pollingMixin(20),
            React.BackboneMixin('nodes'),
            React.BackboneMixin('model', 'change:status'),
            React.BackboneMixin({modelOrCollection: function(props) {return props.model.get('tasks');}}),
            React.BackboneMixin({modelOrCollection: function(props) {return props.model.task({group: 'deployment', status: 'running'});}})
        ],
        getInitialState: function() {
            return {
                loading: true,
                filteredNodes: this.props.nodes,
                grouping: this.props.AddNodesScreen ? 'hardware' : this.props.model.get('grouping')
            };
        },
        filterNodes: function(filter) {
            this.setState({filteredNodes: new models.Nodes(this.props.nodes.filter(function(node) {
                return _.contains(node.get('name').toLowerCase(), filter) || _.contains(node.get('mac').toLowerCase(), filter);
            }))});
        },
        hasChanges: function() {
            return !_.isEqual(this.props.nodes.pluck('pending_roles'), this.initialNodes.pluck('pending_roles'));
        },
        fetchData: function() {
            this.props.nodes.fetch();
        },
        revertChanges: function() {
            this.props.nodes.each(function(node) {
                node.set({pending_roles: this.initialNodes.get(node.id).get('pending_roles')}, {silent: true});
            }, this);
        },
        actualizePendingRoles: function(node, roles, options) {
            if (!options.assign) {
                node.set({pending_roles: node.previous('pending_roles')}, {assign: true});
            }
        },
        componentDidMount: function() {
            this.initialNodes = new models.Nodes(this.props.nodes.invoke('clone'));
            this.props.nodes.on('resize', this.filterNodes, this);
            this.props.nodes.fetch = function(options) {
                return this.constructor.__super__.fetch.call(this, _.extend({data: {cluster_id: this.props.model ? this.props.model.id : ''}}, options));
            };
            if (this.props.EditNodesScreen) {
                var nodeIds = utils.deserializeTabOptions(this.screenOptions[0]).nodes.split(',').map(function(id) {return parseInt(id, 10);});
                this.props.nodes.parse = function(response) {
                    return _.filter(response, function(node) {return _.contains(nodeIds, node.id);});
                };
            }
            if (this.props.AddNodesScreen || (this.props.EditNodesScreen)) {
                this.props.nodes.on('change:pending_roles', this.actualizePendingRoles, this);
                this.props.model.on('change:status', function() {
                    app.navigate('#cluster/' + this.props.model.id + '/nodes', {trigger: true});
                }, this);
            }
            this.startPolling();
            if (this.props.EditNodesScreen) {
                this.setState({loading: false});
            } else {
                this.props.nodes.deferred = this.nodes.fetch().always(_.bind(function() {
                    this.setState({loading: false});
                }, this));
            }
        },
        render: function() {
            return (
                <div>
                    {this.props.EditNodesScreen &&
                        <div className='alert'>{$.t('cluster_page.nodes_tab.disk_configuration_reset_warning')}</div>
                    }
                    <NodeManagementPanel cluster={this.props.model} nodes={this.state.filteredNodes} />
                    {(this.props.AddNodesScreen || this.props.EditNodesScreen) &&
                        <RolesPanel cluster={this.props.model} nodes={this.state.filteredNodes} />
                    }
                    <NodeList
                        cluster={this.props.model}
                        nodes={this.state.filteredNodes}
                        checked={this.props.EditNodesScreen}
                        locked={this.props.EditNodesScreen || !!this.props.model.tasks({group: 'deployment', status: 'running'}).length}
                    />
                </div>
            );
        }
    });

    var NodeManagementPanel = React.createClass({
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
            app.page.tab.screen.filterNodes(filter);
        }, 300),
        onFilterChange: function(name, filter) {
            filter = $.trim(filter).toLowerCase();
            this.setState({filter: filter});
            this.filterNodes(filter);
        },
        clearFilter: function() {
            this.setState({filter: ''});
            app.page.tab.screen.filterNodes('');
        },
        groupNodes: function(name, grouping) {
            this.props.cluster.save({grouping: grouping}, {patch: true, wait: true});
            if (app.page.tab) app.page.tab.screen.setState({grouping: grouping});
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
                <div className='node-management-panel'>
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
                </div>
            );
        }
    });

    var RolesPanel = React.createClass({
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
                <div className='roles-panel'>
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

    var SelectAllMixin = {
        renderSelectAllCheckbox: function() {
            var selectableNodes = this.props.nodes.filter(function(node) {return node.isSelectable();}),
                roles = app.page.screen.rolePanel,
                roleLimitation = roles && (roles.isRoleSelected('controller') || roles.isRoleSelected('zabbix-server')) && selectableNodes.length > 1;
            return (
                <controls.Input
                    type='checkbox'
                    checked={this.props.checked || (selectableNodes.length && this.props.nodes.where({checked: true}).length == selectableNodes.length)}
                    disabled={this.props.locked || !this.props.nodes.where({disabled: false}).length || roleLimitation}
                    label={$.t('common.select_all')}
                    wrapperClassName='span2 select-all'
                    onChange={this.selectNodes}
                />
            );
        },
        selectNodes: function(name, value) {
            _.invoke(this.props.nodes.where({disabled: false}), 'set', {checked: value});
        }
    };

    var NodeList = React.createClass({
        mixins: [
            SelectAllMixin,
            React.BackboneMixin('nodes', 'change:checked')
        ],
        componentWillMount: function() {
            // group nodes
            this.groups = _.pairs(this.props.nodes.groupByAttribute(this.props.grouping));
            // sort node groups
            if (this.props.grouping == 'hardware') {
                this.groups = _.sortBy(this.groups, function(group) {return group[0];});
            } else {
                var preferredOrder = this.props.cluster.get('release').get('roles');
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
            if (!this.props.cluster) return $.t(ns + 'no_nodes_in_fuel');
            if (this.props.cluster.get('nodes').length) return $.t(ns + 'no_filtered_nodes_warning');
            if (this.props.EditNodesScreen) return $.t(ns + 'no_selected_nodes');
            return $.t(ns + 'no_nodes_in_environment');
        },
        render: function() {
            return (
                <div className='node-list'>
                    {this.props.nodes.length &&
                        <div className='row-fluid node-list-header'>
                            <div className='span10' />
                            {this.renderSelectAllCheckbox()}
                        </div>
                    }
                    <div className='row-fluid node-list-header'>
                        {this.state.loading ?
                            <controls.ProgressBar />
                        :
                            this.props.nodes.length ?
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
        mixins: [
            SelectAllMixin,
            React.BackboneMixin('nodes', 'change:checked')
        ],
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
                            return this.trahsferPropsTo(<Node key={node.id} node={node} />);
                        }, this)}
                    </div>
                </div>
            );
        }
    });

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
        onNodeSelection: function(name, checked) {
            this.props.node.set('checked', checked);
        },
        startNodeRenaming: function(e) {
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
            this.props.node.save(data, {patch: true, wait: true})
                .done(_.bind(function() {
                    this.props.cluster.fetch();
                    this.props.cluster.fetchRelated('nodes');
                    app.navbar.refresh();
                    app.page.removeFinishedNetworkTasks();
                }, this))
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
                statusClassName = {
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
                iconClasses = {
                    offline: 'icon-block',
                    pending_addition: 'icon-ok-circle-empty',
                    pending_deletion: 'icon-cancel-circle',
                    ready: 'icon-ok',
                    provisioned: 'icon-install',
                    error: 'icon-attention',
                    discover: 'icon-ok-circle-empty'
                },
                locked = this.props.locked || !node.isSelectable(),
                logoClasses = {'node-logo': true},
                nodeClasses = {'node-box': true, disabled: locked};
            logoClasses['manufacturer-' + node.get('manufacturer').toLowerCase()] = node.get('manufacturer');
            nodeClasses[status] = status;
            return (
                <div className={'node' + (this.props.checked ? 'checked' : '')}>
                    <label className={cx(nodeClasses)}>
                        <controls.Input
                            type='checkbox'
                            defaultChecked={this.props.checked}
                            disabled={locked}
                            onChange={this.onNodeSelection}
                        />
                        <div className='node-content'>
                            <div className={cx(logoClasses)} />
                            <div className='node-name-roles'>
                                <div className='name enable-selection'>
                                    {this.state.renaming ?
                                        <controls.Input
                                            type='text'
                                            defaultValue={node.get('name')}
                                            inputClassName='node-name'
                                            disabled={this.state.renaming == 'save'}
                                            onKeyDown={this.onNodeNameInputKeydown}
                                        />
                                    :
                                        <p className={cx({'node-renameable': !locked})} title={$.t(ns + 'edit_name')} onClick={!locked && this.startNodeRenaming}>
                                            {node.get('name') || node.get('mac')}
                                        </p>
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
                            <div className={cx({'node-status': true, statusClassName: status})}>
                                <div className='node-status-container'>
                                    {_.contains(['provisioning', 'deploying'], status) &&
                                        <div className={'progress ' + (status == 'deploying' ? 'progress-success' : '')}>
                                            <div className='bar' style={{width: _.max([node.get('progress'), 3]) + '%'}} />
                                        </div>
                                    }
                                    <i className={iconClasses[status]} />
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

    return NodeListScreen;
});
