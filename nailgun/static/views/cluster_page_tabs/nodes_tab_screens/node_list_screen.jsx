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
            componentMixins.backboneMixin('nodes', 'update change'),
            componentMixins.backboneMixin({
                modelOrCollection: function(props) {return props.cluster.get('tasks');},
                renderOn: 'update change:status'
            })
        ],
        getInitialState: function() {
            var cluster = this.props.cluster,
                settings = cluster.get('settings'),
                uiSettings = cluster.get('ui_settings'),
                roles = cluster.get('release').get('roles'),
                selectedRoles = this.props.nodes.length ? _.filter(roles, function(role) {
                    return !this.props.nodes.any(function(node) {return !node.hasRole(role);});
                }, this) : [];
            return {
                search: '',
                sorting: (this.props.query || {}).sort || [this.getDefaultSorting()],
                filters: (this.props.query || {}).filter || {},
                viewMode: uiSettings.view_mode,
                selectedNodeIds: this.props.nodes.reduce(function(result, node) {
                    result[node.id] = this.props.mode == 'edit';
                    return result;
                }, {}, this),
                selectedRoles: selectedRoles,
                indeterminateRoles: this.props.nodes.length ? _.filter(_.difference(roles, selectedRoles), function(role) {
                    return this.props.nodes.any(function(node) {return node.hasRole(role);});
                }, this) : [],
                configModels: {
                    cluster: cluster,
                    settings: settings,
                    version: app.version,
                    default: settings
                }
            };
        },
        getDefaultSorting: function() {
            if (this.props.mode == 'add') return {status: 'asc'};
            return {roles: 'asc'};
        },
        selectNodes: function(ids, name, checked) {
            var nodeSelection = this.state.selectedNodeIds;
            _.each(ids, function(id) {nodeSelection[id] = checked;});
            this.setState({selectedNodeIds: nodeSelection});
        },
        selectRoles: function(role, checked) {
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
        fetchData: function() {
            return this.props.nodes.fetch();
        },
        componentWillMount: function() {
            this.updateInitialRoles();
            this.props.nodes.on('update reset', this.updateInitialRoles, this);
            // hack to prevent node roles update after node polling
            if (this.props.mode != 'list') this.props.nodes.on('change:pending_roles', this.checkRoleAssignment, this);
        },
        componentWillUnmount: function() {
            this.props.nodes.off('update reset', this.updateInitialRoles, this);
            this.props.nodes.off('change:pending_roles', this.checkRoleAssignment, this);
        },
        processRoleLimits: function() {
            var cluster = this.props.cluster,
                nodesForLimitCheck = this.getNodesForLimitsCheck(),
                maxNumberOfNodes = [],
                processedRoleLimits = {};

            cluster.get('release').get('role_models').map(function(role) {
                if ((role.get('limits') || {}).max) {
                    var roleName = role.get('name'),
                        isRoleAlreadyAssigned = nodesForLimitCheck.any(function(node) {
                            return node.hasRole(roleName);
                        }, this);
                    processedRoleLimits[roleName] = role.checkLimits(this.state.configModels,
                        !isRoleAlreadyAssigned, ['max'], nodesForLimitCheck);
                }
            }, this);

            _.each(processedRoleLimits, function(roleLimit, roleName) {
                if (_.contains(this.state.selectedRoles, roleName)) {
                    maxNumberOfNodes.push(roleLimit.limits.max);
                }
            }, this);
            return {
                // need to cache roles with limits in order to avoid calculating this twice on the RolePanel
                processedRoleLimits: processedRoleLimits,
                // real number of nodes to add used by Select All controls
                maxNumberOfNodes: maxNumberOfNodes.length ? _.min(maxNumberOfNodes) - _.filter(this.state.selectedNodeIds).length : null
            };
        },
        updateInitialRoles: function() {
            this.initialRoles = _.zipObject(this.props.nodes.pluck('id'), this.props.nodes.pluck('pending_roles'));
        },
        checkRoleAssignment: function(node, roles, options) {
            if (!options.assign) node.set({pending_roles: node.previous('pending_roles')}, {assign: true});
        },
        hasChanges: function() {
            return this.props.nodes.any(function(node) {
                return !_.isEqual(node.get('pending_roles'), this.initialRoles[node.id]);
            }, this);
        },
        changeSearch: _.debounce(function(value) {
            this.setState({search: value});
        }, 200, {leading: true}),
        clearSearchField: function() {
            this.setState({search: ''});
        },
        updateQueryString: function() {
            var parameters = encodeURIComponent(JSON.stringify({filter: this.state.filters, sort: this.state.sorting}));
            app.navigate('#cluster/' + this.props.cluster.id + '/nodes/' + this.props.mode + '/' + parameters, {trigger: false, replace: true});
        },
        changeSortingOrder: function(sorterName, index) {
            var sorting = this.state.sorting,
                changedSorter = sorting[index];
            changedSorter[sorterName] = changedSorter[sorterName] == 'asc' ? 'desc' : 'asc';
            this.setState({sorting: sorting}, this.updateQueryString);
        },
        addSorting: function(sorterName) {
            var sorting = this.state.sorting,
                newSorter = {};
            newSorter[sorterName] = 'asc';
            sorting.push(newSorter);
            this.setState({sorting: sorting}, this.updateQueryString);
        },
        removeSorting: function(index) {
            var sorting = this.state.sorting;
            sorting.splice(index, 1);
            this.setState({sorting: sorting}, this.updateQueryString);
        },
        resetSorters: function() {
            this.setState({sorting: [this.getDefaultSorting()]}, this.updateQueryString);
        },
        applyFilters: function(filtersData) {
            this.setState({filters: filtersData}, this.updateQueryString);
        },
        resetFilters: function() {
            this.setState({filters: {}}, this.updateQueryString);
        },
        changeViewMode: function() {
            var newMode = $(this.refs['management-panel'].refs['view-mode-switcher'].getDOMNode()).find('input:checked').val();
            this.setState({viewMode: newMode});
            this.changeUISettings('view_mode', newMode);
        },
        changeUISettings: function(name, value) {
            var uiSettings = this.props.cluster.get('ui_settings');
            uiSettings[name] = value;
            this.props.cluster.save({ui_settings: uiSettings}, {patch: true, wait: true});
        },
        revertChanges: function() {
            this.props.nodes.each(function(node) {
                node.set({pending_roles: this.initialRoles[node.id]}, {silent: true});
            }, this);
        },
        getNodesForLimitsCheck: function() {
            var selectedNodes = this.props.nodes.filter(function(node) {
                    return this.state.selectedNodeIds[node.id];
                }, this),
                clusterNodes = this.props.cluster.get('nodes').filter(function(node) {
                    return !_.contains(this.state.selectedNodeIds, node.id);
                }, this);
            return new models.Nodes(_.union(selectedNodes, clusterNodes));
        },
        render: function() {
            var cluster = this.props.cluster,
                locked = !!cluster.tasks({group: 'deployment', status: 'running'}).length,
                nodes = this.props.nodes,
                processedRoleData = this.processRoleLimits();

            // filter nodes
            var filteredNodes = nodes.filter(function(node) {
                // search field
                if (!_.contains(node.get('name').concat(' ', node.get('mac')).concat(' ', node.get('ip')).toLowerCase(), this.state.search.toLowerCase())) return false;

                // filters
                return _.all(this.state.filters, function(activeFilters, filter) {
                    // filter is not active
                    if (!activeFilters.length) return true;

                    if (filter == 'roles') return _.any(activeFilters, function(f) {return node.hasRole(f);});
                    if (filter == 'status') return _.contains(activeFilters, node.getStatusSummary());
                    if (filter == 'manufacturer') return _.contains(activeFilters, node.get('manufacturer'));

                    // handke number ranges
                    var resourceName = filter == 'cpu_real' ? 'cores' : filter == 'cpu_total' ? 'ht_cores' : filter,
                        value = _.contains(['hdd', 'ram'], resourceName) ? node.resource(resourceName) / Math.pow(1024, 3) : node.resource(resourceName);
                    return value >= activeFilters[0] && (_.isUndefined(activeFilters[1]) || value <= activeFilters[1]);
                });
            }, this);

            return (
                <div>
                    {this.props.mode == 'edit' &&
                        <div className='alert alert-warning'>{i18n('cluster_page.nodes_tab.disk_configuration_reset_warning')}</div>
                    }
                    <ManagementPanel
                        {... _.pick(this.state, 'viewMode', 'search', 'sorting', 'filters')}
                        ref='management-panel'
                        mode={this.props.mode}
                        screenNodes={nodes}
                        filteredNodes={filteredNodes}
                        nodes={new models.Nodes(_.compact(_.map(this.state.selectedNodeIds, function(checked, id) {
                            if (checked) return nodes.get(id);
                        })))}
                        cluster={cluster}
                        changeSortingOrder={this.changeSortingOrder}
                        addSorting={this.addSorting}
                        removeSorting={this.removeSorting}
                        resetSorters={this.resetSorters}
                        applyFilters={this.applyFilters}
                        resetFilters={this.resetFilters}
                        changeSearch={this.changeSearch}
                        clearSearchField={this.clearSearchField}
                        changeViewMode={this.changeViewMode}
                        hasChanges={this.hasChanges()}
                        locked={locked}
                        revertChanges={this.revertChanges}
                    />
                    {this.props.mode != 'list' &&
                        <RolePanel
                            {...this.props}
                            {... _.pick(processedRoleData, 'processedRoleLimits')}
                            {... _.pick(this.state, 'selectedNodeIds', 'selectedRoles', 'indeterminateRoles')}
                            selectRoles={this.selectRoles}
                            configModels={this.state.configModels}
                        />
                    }
                    <NodeList {...this.props}
                        {... _.pick(this.state, 'sorting', 'selectedNodeIds', 'selectedRoles', 'viewMode')}
                        {... _.pick(processedRoleData, 'maxNumberOfNodes', 'processedRoleLimits')}
                        screenNodes={nodes}
                        nodes={filteredNodes}
                        locked={locked}
                        selectNodes={this.selectNodes}
                    />
                </div>
            );
        }
    });

    ManagementPanel = React.createClass({
        getInitialState: function() {
            return {
                isSearchButtonVisible: !!this.props.search,
                actionInProgress: false,
                visibleFilters: _.pluck(_.filter(this.getFilters(), 'base'), 'name'),
                activeSearch: !!this.props.search
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
        startSearch: function(name, value) {
            this.setState({isSearchButtonVisible: !!value});
            this.props.changeSearch(value);
        },
        clearSearchField: function() {
            this.setState({isSearchButtonVisible: false});
            this.refs['search-input'].getInputDOMNode().value = '';
            this.props.clearSearchField();
        },
        activateSearch: function() {
            this.setState({activeSearch: true});
            $('html').on('click.search', _.bind(function(e) {
                if (!this.props.search && this.refs.search && !$(e.target).closest(this.refs.search.getDOMNode()).length) {
                    this.setState({activeSearch: false});
                }
            }, this));
        },
        componentWillUnmount: function() {
            $('html').off('click.search');
        },
        removeSorting: function(index) {
            this.props.removeSorting(index);
            this.setState({sortersKey: _.now()});
        },
        applyFilters: function() {
            var filtersData = {};
            _.each(this.state.visibleFilters, function(name) {
                var chosenOptions = _.uniq(this.refs[name].state.values);
                if (!_.all(chosenOptions, _.isUndefined)) filtersData[name] = chosenOptions;
            }, this);
            this.props.applyFilters(filtersData);
            this.setState({filtersVisible: false});
        },
        resetSorters: function(e) {
            e.stopPropagation();
            this.props.resetSorters();
            this.setState({sortersKey: _.now()});
        },
        resetFilters: function(e) {
            e.stopPropagation();
            this.setState({
                visibleFilters: _.pluck(_.filter(this.getFilters(), 'base'), 'name'),
                filtersKey: _.now()
            });
            this.props.resetFilters();
        },
        getFilters: function() {
            var release = this.props.cluster.get('release'),
                os = release.get('operating_system') || i18n('node_details.os');

            var filters = [
                    {
                        name: 'status',
                        label: 'Status',
                        type: 'multiselect',
                        base: true,
                        options: _.map(this.props.mode == 'list' ? [
                                'ready',
                                'pending_addition',
                                'pending_deletion',
                                'provisioned',
                                'provisioning',
                                'deploying',
                                'removing',
                                'error',
                                'offline'
                            ] : [
                                'error',
                                'offline'
                            ], function(status) {
                                return {name: status, label: i18n('cluster_page.nodes_tab.node.status.' + status, {os: os})};
                            }, this)
                    },
                    {
                        name: 'manufacturer',
                        label: 'Manufacturer',
                        type: 'multiselect',
                        sort: true,
                        options: _.map(_.uniq(this.props.screenNodes.pluck('manufacturer')), function(data) {
                                return {name: data.toString().replace(/\s/g, '_'), label: data};
                            })
                    },
                    {
                        name: 'cpu_real',
                        label: 'CPU (real)',
                        type: 'range',
                        prefix: 'CPU (real)'
                    },
                    {
                        name: 'cpu_total',
                        label: 'CPU (total)',
                        type: 'range',
                        prefix: 'CPU (total)'
                    },
                    {
                        name: 'hdd',
                        label: 'HDD total size',
                        type: 'range',
                        prefix: 'Gb HDD'
                    },
                    {
                        name: 'disks_amount',
                        label: 'Disks amount',
                        type: 'range',
                        prefix: 'disks'
                    },
                    {
                        name: 'ram',
                        label: 'RAM total size',
                        type: 'range',
                        prefix: 'Gb RAM'
                    },
                    {
                        name: 'interfaces',
                        label: 'Interfaces amount',
                        type: 'range',
                        prefix: 'interfaces'
                    }
                ];
                if (this.props.mode == 'list') {
                    var roleModels = release.get('role_models');
                    filters.unshift({
                        name: 'roles',
                        label: 'Roles',
                        type: 'multiselect',
                        base: true,
                        options: _.map(release.get('roles'), function(role) {
                            return {name: role, label: roleModels.findWhere({name: role}).get('label')};
                        })
                    });
                }
                return filters;
        },
        addFilter: function(name, checked) {
            if (checked) this.setState({
                visibleFilters: _.union(this.state.visibleFilters, [name])
            });
        },
        removeFilter: function(name) {
            this.setState({
                visibleFilters: _.difference(this.state.visibleFilters, [name])
            });
        },
        toggleSorters: function() {
            this.setState({
                sortersVisible: !this.state.sortersVisible,
                filtersVisible: false
            });
            $(this.refs.filters.getDOMNode()).collapse('hide');
        },
        toggleFilters: function() {
            this.setState({
                filtersVisible: !this.state.filtersVisible,
                sortersVisible: false
            });
            $(this.refs.sorters.getDOMNode()).collapse('hide');
        },
        renderDeleteFilterButton: function(filter) {
            if (filter.base) return null;
            return <i className='btn btn-link glyphicon glyphicon-minus-sign' onClick={_.partial(this.removeFilter, filter.name)} />;
        },
        renderDeleteSorterButton: function(index) {
            if (index == 0) return null;
            return <i className='btn btn-link glyphicon glyphicon-minus-sign' onClick={_.partial(this.removeSorting, index)} />;
        },
        render: function() {
            var ns = 'cluster_page.nodes_tab.node_management_panel.',
                sampleNode = this.props.nodes.at(0),
                disksConflict = this.props.nodes.any(function(node) {
                    var roleConflict = _.difference(_.union(sampleNode.get('roles'), sampleNode.get('pending_roles')), _.union(node.get('roles'), node.get('pending_roles'))).length;
                    return roleConflict || !_.isEqual(sampleNode.resource('disks'), node.resource('disks'));
                }),
                interfaceConflict = _.uniq(this.props.nodes.map(function(node) {return node.resource('interfaces');})).length > 1;

            var viewModeButtonClasses = _.bind(function(mode) {
                var classes = {
                    'btn btn-default': true,
                    active: mode == this.props.viewMode
                };
                classes[mode] = true;
                return classes;
            }, this);

            var activeSorters = _.flatten(_.map(this.props.sorting, _.keys)),
                hiddenSorters = _.compact(_.map(this.props.cluster.sorters(this.props.mode), function(sorterName) {
                    if (!_.contains(activeSorters, sorterName)) {
                        return {
                            name: sorterName,
                            label: i18n('cluster_page.nodes_tab.sorters.' + sorterName)
                        };
                    }
                }));

            var filters = this.getFilters(),
                hiddenFilters = _.filter(filters, function(filter) {
                    return !_.contains(this.state.visibleFilters, filter.name);
                }, this);

            return (
                <div className='row'>
                    <div className='sticker node-management-panel'>
                        <div className='node-list-management-buttons col-xs-6'>
                            <div className='view-mode-switcher'>
                                <div className='btn-group' data-toggle='buttons' ref='view-mode-switcher'>
                                    {_.map(this.props.cluster.getViewModes(), function(mode) {
                                        return (
                                            <label
                                                key={mode + '-view'}
                                                className={utils.classNames(viewModeButtonClasses(mode))}
                                                onClick={this.props.changeViewMode}
                                            >
                                                <input type='radio' name='view_mode' value={mode} />
                                                <i className={utils.classNames({glyphicon: true, 'glyphicon-th-list': mode == 'standard', 'glyphicon-th': mode == 'compact'})} />
                                            </label>
                                        );
                                    }, this)}
                                </div>
                            </div>
                            {this.props.mode != 'edit' && [
                                <button
                                    key='sorters-btn'
                                    className={utils.classNames({'btn btn-default pull-left': true, active: this.state.sortersVisible})}
                                    disabled={!this.props.screenNodes.length}
                                    data-toggle='collapse'
                                    data-target='.sorters'
                                    onClick={this.toggleSorters}
                                >
                                    <i className='glyphicon glyphicon-sort' />
                                </button>,
                                <button
                                    key='filters-btn'
                                    className={utils.classNames({'btn btn-default pull-left': true, active: this.state.filtersVisible})}
                                    disabled={!this.props.screenNodes.length}
                                    data-toggle='collapse'
                                    data-target='.filters'
                                    onClick={this.toggleFilters}
                                >
                                    <i className='glyphicon glyphicon-filter' />
                                </button>
                            ]}
                            {this.props.mode != 'edit' && !this.state.activeSearch &&
                                <button
                                    className='btn btn-default pull-left'
                                    disabled={!this.props.screenNodes.length}
                                    onClick={this.activateSearch}
                                >
                                    <i className='glyphicon glyphicon-search' />
                                </button>
                            }
                            {this.props.mode != 'edit' && this.state.activeSearch &&
                                <div className='search pull-left' ref='search'>
                                    <controls.Input
                                        type='text'
                                        name='search'
                                        ref='search-input'
                                        defaultValue={this.props.search}
                                        placeholder={i18n(ns + 'search_placeholder')}
                                        disabled={!this.props.screenNodes.length}
                                        onChange={this.startSearch}
                                        autoFocus
                                    />
                                    {this.state.isSearchButtonVisible &&
                                        <button className='close btn-clear-search' onClick={this.clearSearchField}>&times;</button>
                                    }
                                </div>
                            }
                        </div>
                        <div className='control-buttons-box col-xs-6 text-right'>
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
                                            disabled={!this.props.nodes.length}
                                            onClick={_.bind(this.goToConfigurationScreen, this, 'disks', disksConflict)}
                                        >
                                            {disksConflict && <i className='glyphicon glyphicon-warning-sign text-danger' />}
                                            {i18n('dialog.show_node.disk_configuration_button')}
                                        </button>
                                        {!this.props.nodes.any({status: 'error'}) &&
                                            <button
                                                className='btn btn-default btn-configure-interfaces'
                                                disabled={!this.props.nodes.length}
                                                onClick={_.bind(this.goToConfigurationScreen, this, 'interfaces', interfaceConflict)}
                                            >
                                                {interfaceConflict && <i className='glyphicon glyphicon-warning-sign text-danger' />}
                                                {i18n('dialog.show_node.network_configuration_button')}
                                            </button>
                                        }
                                    </div>,
                                    <div className='btn-group' role='group' key='role-management-buttons'>
                                        {!this.props.locked && !!this.props.nodes.length && this.props.nodes.any({pending_deletion: false}) &&
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
                                        {!this.props.locked && !this.props.nodes.length &&
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
                        {this.props.mode != 'edit' && !!this.props.screenNodes.length && [
                            <div className='col-xs-12 sorters collapse' key='sorters' ref='sorters'>
                                <div className='well clearfix' key={this.state.sortersKey}>
                                    <div className='well-heading'>
                                        <i className='glyphicon glyphicon-sort' /> {i18n(ns + 'sort_by')}
                                        {(this.props.sorting.length > 1 || _.values(this.props.sorting[0])[0] == 'desc') &&
                                            <button className='btn btn-link pull-right' onClick={this.resetSorters}>
                                                <i className='glyphicon glyphicon-remove-sign' /> Clear All
                                            </button>
                                        }
                                    </div>
                                    {this.props.sorting.map(function(sortObject, index) {
                                        var sorter = _.keys(sortObject)[0],
                                            asc = sortObject[sorter] == 'asc';
                                        return (
                                            <div key={'sort_by-' + sorter} className='pull-left'>
                                                <button className='btn btn-default' onClick={_.partial(this.props.changeSortingOrder, sorter, index)}>
                                                    {i18n('cluster_page.nodes_tab.sorters.' + sorter)}
                                                    <i
                                                        className={utils.classNames({
                                                            glyphicon: true,
                                                            'glyphicon-arrow-down': asc,
                                                            'glyphicon-arrow-up': !asc
                                                        })}
                                                    />
                                                </button>
                                                {this.renderDeleteSorterButton(index)}
                                            </div>
                                        );
                                    }, this)}
                                    {!!hiddenSorters.length &&
                                        <controls.MultiSelect
                                            name='sorter-more'
                                            label='More'
                                            options={hiddenSorters}
                                            onChange={this.props.addSorting}
                                            simple={true}
                                        />
                                    }
                                </div>
                            </div>,
                            <div className='col-xs-12 filters collapse' key='filters' ref='filters'>
                                <div className='well clearfix' key={this.state.filtersKey}>
                                    <div className='well-heading'>
                                        <i className='glyphicon glyphicon-filter' /> {i18n(ns + 'filter_by')}
                                        <button className='btn btn-link pull-right' onClick={this.resetFilters}>
                                            <i className='glyphicon glyphicon-remove-sign' /> Clear All
                                        </button>
                                    </div>
                                    {_.map(this.state.visibleFilters, function(filterName) {
                                        var filter = _.find(filters, {name: filterName}),
                                            Control = filter.type == 'range' ? controls.NumberRange : controls.MultiSelect;
                                        return (
                                            <Control {...filter}
                                                key={filterName}
                                                ref={filterName}
                                                values={this.props.filters[filterName]}
                                                extraContent={this.renderDeleteFilterButton(filter)}
                                            />
                                        );
                                    }, this)}
                                    {!!hiddenFilters.length &&
                                        <controls.MultiSelect
                                            name='filter-more'
                                            label='More'
                                            options={hiddenFilters}
                                            onChange={this.addFilter}
                                            simple={true}
                                        />
                                    }
                                    <div className='control-buttons text-right'>
                                        <div className='btn-group' role='group'>
                                            <button className='btn btn-default' data-toggle='collapse' data-target='.filters'>
                                                {i18n('common.cancel_button')}
                                            </button>
                                            <button className='btn btn-success' data-toggle='collapse' data-target='.filters' onClick={this.applyFilters}>
                                                {i18n('common.apply_button')}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ]}
                        {this.props.mode != 'edit' && !!this.props.screenNodes.length &&
                            <div className='col-xs-12'>
                                {(!this.state.sortersVisible || !this.state.filtersVisible && !!_.keys(this.props.filters).length) &&
                                    <div className='active-sorters-filters'>
                                        {!this.state.filtersVisible && !!_.keys(this.props.filters).length &&
                                            <div
                                                className='active-filters row'
                                                data-toggle='collapse'
                                                data-target='.filters'
                                                onClick={this.toggleFilters}
                                            >
                                                <strong className='col-xs-1'>
                                                    <i className='glyphicon glyphicon-filter' /> {i18n(ns + 'filter_by')}
                                                </strong>
                                                <div className='col-xs-11'>
                                                    {i18n('cluster_page.nodes_tab.filter_results_amount', {count: this.props.filteredNodes.length, total: this.props.screenNodes.length})}
                                                    {_.map(this.props.filters, function(values, filterName) {
                                                        var filter = _.find(filters, {name: filterName});
                                                        return (
                                                            <div key={filterName}>
                                                                <span>{filter.label}: </span>
                                                                <strong>
                                                                    {filter.type == 'range' ?
                                                                        (_.isUndefined(values[0]) ? 'Less than ' + values[1] : _.isUndefined(values[1]) ? 'More than ' + values[0] : _.uniq(values).join(' - ')) + ' ' + filter.prefix
                                                                    :
                                                                        _.map(values, function(value) {
                                                                            return _.find(filter.options, {name: value}).label;
                                                                        }).join(', ')
                                                                    }
                                                                </strong>
                                                            </div>
                                                        );
                                                    })}
                                                </div>
                                                <button className='btn btn-link' onClick={this.resetFilters}>
                                                    <i className='glyphicon glyphicon-remove-sign' />
                                                </button>
                                            </div>
                                        }
                                        {!this.state.sortersVisible && !this.state.filtersVisible && !!_.keys(this.props.filters).length && <hr/>}
                                        {!this.state.sortersVisible &&
                                            <div
                                                className='active-sorters row'
                                                data-toggle='collapse'
                                                data-target='.sorters'
                                                onClick={this.toggleSorters}
                                            >
                                                <strong className='col-xs-1'>
                                                    <i className='glyphicon glyphicon-sort' /> {i18n(ns + 'sort_by')}
                                                </strong>
                                                <div className='col-xs-11'>
                                                    {_.map(this.props.sorting, function(sorter, index) {
                                                        var sorterName = _.keys(sorter)[0],
                                                            asc = sorter[sorterName] == 'asc';
                                                        return (
                                                            <span key={sorterName}>
                                                                {i18n('cluster_page.nodes_tab.sorters.' + sorterName)}
                                                                <i
                                                                    className={utils.classNames({
                                                                        glyphicon: true,
                                                                        'glyphicon-arrow-down': asc,
                                                                        'glyphicon-arrow-up': !asc
                                                                    })}
                                                                />
                                                                {index + 1 < this.props.sorting.length && ' + '}
                                                            </span>
                                                        );
                                                    }, this)}
                                                </div>
                                                {(this.props.sorting.length > 1 || !_.isEqual(this.props.sorting[0], {roles: 'asc'})) &&
                                                    <button className='btn btn-link' onClick={this.resetSorters}>
                                                        <i className='glyphicon glyphicon-remove-sign' />
                                                    </button>
                                                }
                                            </div>
                                        }
                                    </div>
                                }
                            </div>
                        }
                    </div>
                </div>
            );
        }
    });

    RolePanel = React.createClass({
        componentDidMount: function() {
            this.updateIndeterminateRolesState();
        },
        componentDidUpdate: function() {
            this.updateIndeterminateRolesState();
            this.assignRoles();
        },
        updateIndeterminateRolesState: function() {
            _.each(this.refs, function(roleView, role) {
                roleView.getInputDOMNode().indeterminate = _.contains(this.props.indeterminateRoles, role);
            }, this);
        },
        assignRoles: function() {
            var roles = this.props.cluster.get('release').get('role_models');
            this.props.nodes.each(function(node) {
                if (this.props.selectedNodeIds[node.id]) roles.each(function(role) {
                    var roleName = role.get('name');
                    if (!node.hasRole(roleName, true)) {
                        var nodeRoles = node.get('pending_roles');
                        if (_.contains(this.props.selectedRoles, roleName)) {
                            nodeRoles = _.union(nodeRoles, [roleName]);
                        } else if (!_.contains(this.props.indeterminateRoles, roleName)) {
                            nodeRoles = _.without(nodeRoles, roleName);
                        }
                        node.set({pending_roles: nodeRoles}, {assign: true});
                    }
                }, this);
            }, this);
        },
        processRestrictions: function(role, models) {
            var name = role.get('name'),
                restrictionsCheck = role.checkRestrictions(models, 'disable'),
                roleLimitsCheckResults = this.props.processedRoleLimits[name],
                roles = this.props.cluster.get('release').get('role_models'),
                conflicts = _.chain(this.props.selectedRoles)
                    .union(this.props.indeterminateRoles)
                    .map(function(role) {return roles.findWhere({name: role}).conflicts;})
                    .flatten()
                    .uniq()
                    .value(),
                messages = [];

            if (restrictionsCheck.result && restrictionsCheck.message) messages.push(restrictionsCheck.message);
            if (roleLimitsCheckResults && !roleLimitsCheckResults.valid && roleLimitsCheckResults.message) messages.push(roleLimitsCheckResults.message);
            if (_.contains(conflicts, name)) messages.push(i18n('cluster_page.nodes_tab.role_conflict'));

            return {
                result: restrictionsCheck.result || _.contains(conflicts, name) || (roleLimitsCheckResults && !roleLimitsCheckResults.valid && !_.contains(this.props.selectedRoles, name)),
                message: messages.join(' ')
            };
        },
        render: function() {
            return (
                <div className='well role-panel'>
                    <h4>{i18n('cluster_page.nodes_tab.assign_roles')}</h4>
                    {this.props.cluster.get('release').get('role_models').map(function(role) {
                        if (!role.checkRestrictions(this.props.configModels, 'hide').result) {
                            var name = role.get('name'),
                                processedRestrictions = this.props.nodes.length ? this.processRestrictions(role, this.props.configModels) : {};
                            return (
                                <controls.Input
                                    key={name}
                                    ref={name}
                                    type='checkbox'
                                    name={name}
                                    label={role.get('label')}
                                    description={role.get('description')}
                                    checked={_.contains(this.props.selectedRoles, name)}
                                    disabled={!this.props.nodes.length || processedRestrictions.result}
                                    tooltipText={!!this.props.nodes.length && processedRestrictions.message}
                                    onChange={this.props.selectRoles}
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
            if (this.refs['select-all']) {
                var input = this.refs['select-all'].getInputDOMNode();
                input.indeterminate = !input.checked && _.any(this.props.nodes, function(node) {return this.props.selectedNodeIds[node.id];}, this);
            }
        },
        renderSelectAllCheckbox: function() {
            var availableNodesIds = _.compact(this.props.nodes.map(function(node) {if (node.isSelectable()) return node.id;})),
                checked = this.props.mode == 'edit' || (availableNodesIds.length && !_.any(availableNodesIds, function(id) {return !this.props.selectedNodeIds[id];}, this));
            return (
                <controls.Input
                    ref='select-all'
                    name='select-all'
                    type='checkbox'
                    checked={checked}
                    disabled={
                        this.props.mode == 'edit' || this.props.locked || !availableNodesIds.length ||
                        !checked && !_.isNull(this.props.maxNumberOfNodes) && this.props.maxNumberOfNodes < availableNodesIds.length
                    }
                    label={i18n('common.select_all')}
                    wrapperClassName='select-all pull-right'
                    onChange={_.bind(this.props.selectNodes, this.props, availableNodesIds)} />
            );
        }
    };

    NodeList = React.createClass({
        mixins: [SelectAllMixin],
        groupNodes: function() {
            var release = this.props.cluster.get('release'),
                releaseRoles = new models.Roles(release.get('role_models').models),
                os = release.get('operating_system') || i18n('node_details.os');

            var specialSorters = ['name', 'mac', 'ip'],
                usedSorters = _.uniq(_.flatten(_.map(this.props.sorting, _.keys))),
                usedNotSpecialSorters = _.difference(usedSorters, specialSorters);

            var groups;
            if (this.props.mode != 'add') {
                if (_.find(this.props.sorting, function(sortObject) {return sortObject.roles;}).roles != 'asc') {
                    releaseRoles.models.reverse();
                }
            }
            if (usedNotSpecialSorters.length) {
                var groupingMethod = _.bind(function(node) {
                    return (_.map(usedNotSpecialSorters, function(sorter) {
                        if (sorter == 'roles') {
                            return node.getRolesSummary(releaseRoles);
                        }
                        if (sorter == 'status') {
                            return i18n('cluster_page.nodes_tab.node.status.' + node.getStatusSummary(), {
                                os: os
                            });
                        }
                        if (sorter == 'manufacturer') {
                            return node.get('manufacturer');
                        }
                        if (sorter == 'hdd') {
                            return i18n('node_details.total_hdd', {
                                total: utils.showDiskSize(node.resource('hdd'))
                            });
                        }
                        if (sorter == 'disks') {
                            var diskSizes = node.resource('disks');
                            return i18n('node_details.disks_amount', {
                                count: diskSizes.length,
                                size: diskSizes.map(function(size) {
                                        return utils.showDiskSize(size) + ' ' + i18n('node_details.hdd');
                                    }).join(', ')
                            });
                        }
                        if (sorter == 'ram') {
                            return i18n('node_details.total_ram', {
                                total: utils.showMemorySize(node.resource('ram'))
                            });
                        }
                        if (sorter == 'interfaces') {
                            return i18n('node_details.interfaces_amount', {
                                count: node.resource('interfaces')
                            });
                        }
                        return i18n('node_details.cpu_details', {
                            real: node.resource('cores'),
                            total: node.resource('ht_cores')
                        });
                    }, this)).join('; ');
                }, this);
                groups = _.pairs(_.groupBy(this.props.nodes, groupingMethod));
            } else {
                groups = [[this.props.cluster.get('name'), this.props.nodes]];
            }

            // sort grouped nodes by name, mac or ip
            var usedSpecialSorters = _.intersection(usedSorters, specialSorters);
            if (usedSpecialSorters.length) {
                var formattedSorters = _.map(usedSpecialSorters, function(sorter) {
                    return {
                        attr: sorter,
                        desc: _.find(this.props.sorting, function(sortObject) {return sortObject[sorter];})[sorter] == 'desc'
                    };
                }, this);
                _.each(groups, function(group) {
                    group[1].sort(function(node1, node2) {
                        return utils.multiSort(node1, node2, formattedSorters);
                    });
                });
            }

            var statusPreferredOrder = ['error', 'offline', 'discover', 'pending_addition', 'provisioning', 'provisioned', 'ready'];
            if (this.props.mode != 'add') {
                var preferredOrder = releaseRoles.pluck('name');
                var statusSorter = _.find(this.props.sorting, function(sortObject) {return sortObject.status;});
                return groups.sort(function(group1, group2) {
                    var roles1 = group1[1][0].sortedRoles(preferredOrder),
                        roles2 = group2[1][0].sortedRoles(preferredOrder),
                        order, statusOrder;
                    while (!order && roles1.length && roles2.length) {
                        order = _.indexOf(preferredOrder, roles1.shift()) - _.indexOf(preferredOrder, roles2.shift());
                    }
                    if (statusSorter) {
                        statusOrder = _.indexOf(statusPreferredOrder, group1[1][0].getStatusSummary()) - _.indexOf(statusPreferredOrder, group2[1][0].getStatusSummary());
                        if (statusSorter.status != 'asc') statusOrder = -statusOrder;
                    }
                    return order || roles1.length - roles2.length || statusOrder;
                });
            } else {
                if (_.find(this.props.sorting, function(sortObject) {return sortObject.status;}).status != 'asc') {
                    statusPreferredOrder.reverse();
                }
                return groups.sort(function(group1, group2) {
                    return _.indexOf(statusPreferredOrder, group1[1][0].getStatusSummary()) - _.indexOf(statusPreferredOrder, group2[1][0].getStatusSummary());
                });
            }
        },
        render: function() {
            var groups = this.groupNodes(),
                rolesWithLimitReached = _.keys(_.omit(this.props.processedRoleLimits, function(roleLimit, roleName) {
                    return roleLimit.valid || !_.contains(this.props.selectedRoles, roleName);
                }, this));
            return (
                <div className='node-list row'>
                    {groups.length > 1 &&
                        <div className='col-xs-12 node-list-header'>
                            {this.renderSelectAllCheckbox()}
                        </div>
                    }
                    <div className='col-xs-12 content-elements'>
                        {groups.map(function(group, index) {
                            return <NodeGroup {...this.props}
                                key={group[0]}
                                index={index}
                                label={group[0]}
                                nodes={group[1]}
                                rolesWithLimitReached={rolesWithLimitReached}
                            />;
                        }, this)}
                        {this.props.screenNodes.length ?
                            (
                                !this.props.nodes.length &&
                                    <div className='alert alert-warning'>
                                        {i18n('cluster_page.nodes_tab.no_filtered_nodes_warning')}
                                    </div>
                            )
                        :
                            <div className='alert alert-warning'>
                                {i18n('cluster_page.nodes_tab.' + (this.props.mode == 'add' ? 'no_nodes_in_fuel' : 'no_nodes_in_environment'))}
                            </div>
                        }
                    </div>
                </div>
            );
        }
    });

    NodeGroup = React.createClass({
        mixins: [SelectAllMixin],
        getInitialState: function() {
            return {collapsed: false};
        },
        toggleIcon: function() {
            this.setState({collapsed: !this.state.collapsed});
        },
        render: function() {
            var availableNodes = this.props.nodes.filter(function(node) {return node.isSelectable();}),
                nodesWithRestrictionsIds = _.pluck(_.filter(availableNodes, function(node) {
                    return _.any(this.props.rolesWithLimitReached, function(role) {return !node.hasRole(role);}, this);
                }, this), 'id');

            return (
                <div className='nodes-group'>
                    <div className='row node-group-header'>
                        <div className='col-xs-10'>
                            <h4>{this.props.label} ({this.props.nodes.length})</h4>
                        </div>
                        <div className='col-xs-2'>
                            {this.renderSelectAllCheckbox()}
                        </div>
                    </div>
                    <div className={'row collapse in node-group-content ' + this.props.index}>
                        {this.props.nodes.map(function(node) {
                            return <Node
                                key={node.id}
                                node={node}
                                checked={this.props.mode == 'edit' || this.props.selectedNodeIds[node.id]}
                                viewMode={this.props.viewMode}
                                cluster={this.props.cluster}
                                locked={this.props.mode == 'edit' || this.props.locked || _.contains(nodesWithRestrictionsIds, node.id)}
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
                eventNamespace: 'click.editnodename' + this.props.node.id,
                extendedView: false,
                onHoverHardwareInfo: false
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
                if ($(e.target).hasClass('node-name-input')) {
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
        removeNode: function(e) {
            e.preventDefault();
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
            if (this.state.extendedView) this.toggleExtendedNodePanel();
            dialogs.ShowNodeInfoDialog.show({node: this.props.node});
        },
        sortRoles: function(roles) {
            var preferredOrder = this.props.cluster.get('release').get('roles');
            return roles.sort(function(a, b) {
                return _.indexOf(preferredOrder, a) - _.indexOf(preferredOrder, b);
            });
        },
        toggleExtendedNodePanel: function() {
            var states = this.state.extendedView ? {extendedView: false, renaming: false} : {extendedView: true};
            this.setState(states);
        },
        toggleExtendedPanelink: function(value) {
            this.setState({onHoverHardwareInfo: value});
        },
        renderNameControl: function() {
            if (this.state.renaming) return (
                <controls.Input
                    ref='name'
                    type='text'
                    name='node-name'
                    defaultValue={this.props.node.get('name')}
                    inputClassName='form-control node-name-input'
                    disabled={this.state.actionInProgress}
                    onKeyDown={this.onNodeNameInputKeydown}
                    autoFocus
                />
            );
            return (
                <p
                    title={i18n('cluster_page.nodes_tab.node.edit_name')}
                    onClick={!this.state.actionInProgress && this.startNodeRenaming}
                >
                    {this.props.node.get('name') || this.props.node.get('mac')}
                </p>
            );
        },
        renderStatusLabel: function(status) {
            return (
                <span>
                    {i18n('cluster_page.nodes_tab.node.status.' + status, {
                        os: this.props.cluster.get('release').get('operating_system') || 'OS'
                    })}
                </span>
            );
        },
        renderNodeProgress: function(showPercentage) {
            var nodeProgress = _.max([this.props.node.get('progress'), 3]);
            return (
                <div className='progress'>
                    <div className='progress-bar' role='progressbar' style={{width: nodeProgress + '%'}}>
                        {showPercentage && (nodeProgress + '%')}
                    </div>
                </div>
            );
        },
        renderNodeHardwareSummary: function() {
            var node = this.props.node;
            return (
                <div className='node-hardware'>
                    <span>{i18n('node_details.cpu')}: {node.resource('cores') || '0'} ({node.resource('ht_cores') || '?'})</span>
                    <span>{i18n('node_details.hdd')}: {node.resource('hdd') ? utils.showDiskSize(node.resource('hdd')) : '?' + i18n('common.size.gb')}</span>
                    <span>{i18n('node_details.ram')}: {node.resource('ram') ? utils.showMemorySize(node.resource('ram')) : '?' + i18n('common.size.gb')}</span>
                </div>
            );
        },
        renderLogsLink: function(iconRepresentation) {
            return (
                <a className={iconRepresentation ? 'icon icon-logs' : 'btn'} href={this.getNodeLogsLink()}>
                    {i18n('cluster_page.nodes_tab.node.view_logs')}
                </a>
            );
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
        renderNodeCheckbox: function() {
            return (
                <controls.Input
                    type='checkbox'
                    name={this.props.node.id}
                    checked={this.props.checked}
                    disabled={!this.props.node.isSelectable()}
                    onChange={this.props.onNodeSelection}
                    wrapperClassName='pull-left'
                />
            );
        },
        renderRemoveButton: function() {
            return (
                <button onClick={this.removeNode} className='btn node-remove-button'>
                    {i18n('cluster_page.nodes_tab.node.remove')}
                </button>
            );
        },
        renderRoleList: function(roles) {
            return (
                <ul className='clearfix'>
                    {_.map(roles, function(role) {
                        return (
                            <li
                                key={this.props.node.id + role}
                                className={utils.classNames({'text-success': !this.props.node.get('roles').length})}
                            >
                                {role}
                            </li>
                        );
                    }, this)}
                </ul>
            );
        },
        showDeleteNodesDialog: function() {
            if (this.props.viewMode == 'compact') this.setState({extendedView: false});
            dialogs.DeleteNodesDialog.show({nodes: [this.props.node], cluster: this.props.cluster});
        },
        render: function() {
            var ns = 'cluster_page.nodes_tab.node.',
                node = this.props.node,
                deployedRoles = node.get('roles'),
                status = node.getStatusSummary(),
                roles = this.sortRoles(deployedRoles.length ? deployedRoles : node.get('pending_roles'));

            // compose classes
            var nodePanelClasses = {
                node: true,
                selected: this.props.checked,
                'col-xs-12': this.props.viewMode != 'compact'
            };
            nodePanelClasses[status] = status;

            var manufacturer = node.get('manufacturer'),
                logoClasses = {
                    'manufacturer-logo': true
                };
            logoClasses[manufacturer.toLowerCase()] = manufacturer;

            var statusClasses = {
                    'node-status': true
                },
                statusClass = {
                    pending_addition: 'text-success',
                    pending_deletion: 'text-warning',
                    error: 'text-danger',
                    ready: 'text-info',
                    provisioning: 'text-info',
                    deploying: 'text-success',
                    provisioned: 'text-info'
                }[status];
            statusClasses[statusClass] = true;

            if (this.props.viewMode == 'compact') return (
                <div className='compact-node'>
                    <div className={utils.classNames(nodePanelClasses)}>
                        <label className='node-box'>
                            <div className='node-box-inner clearfix' onClick={this.props.mode != 'edit' && node.isSelectable() && _.partial(this.props.onNodeSelection, null, !this.props.checked)}>
                                <div className='node-buttons'>
                                    {this.props.checked && <i className='glyphicon glyphicon-ok' />}
                                </div>
                                <div className='node-name'>
                                    <p>{node.get('name') || node.get('mac')}</p>
                                </div>
                                <div className={utils.classNames(statusClasses)}>
                                    {_.contains(['provisioning', 'deploying'], status) ?
                                        this.renderNodeProgress()
                                    :
                                        this.renderStatusLabel(status)
                                    }
                                </div>
                            </div>
                            <div className='node-hardware' onMouseEnter={_.partial(this.toggleExtendedPanelink, true)} onMouseLeave={_.partial(this.toggleExtendedPanelink, false)} onClick={this.state.onHoverHardwareInfo && this.toggleExtendedNodePanel}>
                            {this.state.onHoverHardwareInfo ?
                                <p className='btn btn-link'>{i18n(ns + 'show_details')}</p>
                            :
                                <p>
                                    <span>
                                        {node.resource('cores') || '0'} ({node.resource('ht_cores') || '?'})
                                    </span> / <span>
                                        {node.resource('hdd') ? utils.showDiskSize(node.resource('hdd')) : '?' + i18n('common.size.gb')}
                                    </span> / <span>
                                        {node.resource('ram') ? utils.showMemorySize(node.resource('ram')) : '?' + i18n('common.size.gb')}
                                    </span>
                                </p>
                            }
                            </div>
                        </label>
                    </div>
                    {this.state.extendedView &&
                        <controls.Popover className='node-popover' toggle={this.toggleExtendedNodePanel}>
                            <div>
                                <div className='node-name clearfix'>
                                    {this.renderNodeCheckbox()}
                                    <div className='name pull-left'>
                                        {this.renderNameControl()}
                                    </div>
                                </div>
                                <div className='node-stats'>
                                    {!!roles.length &&
                                        <div className='role-list'>
                                            <i className='glyphicon glyphicon-pushpin' />
                                            {this.renderRoleList(roles)}
                                        </div>
                                    }
                                    <div className={utils.classNames(statusClasses)}>
                                        <i className='glyphicon glyphicon-time' />
                                        {_.contains(['provisioning', 'deploying'], status) ?
                                            <div>
                                                {this.renderStatusLabel(status)}
                                                {this.renderLogsLink()}
                                                {this.renderNodeProgress(true)}
                                            </div>
                                        :
                                            <div>
                                                {this.renderStatusLabel(status)}
                                                {status == 'offline' && this.renderRemoveButton()}
                                                {!!node.get('cluster') &&
                                                    (node.hasChanges() ?
                                                        <button className='btn btn-discard' onClick={node.get('pending_addition') ? this.showDeleteNodesDialog : this.discardNodeChanges}>
                                                            {i18n(ns + (node.get('pending_addition') ? 'discard_addition' : 'discard_deletion'))}
                                                        </button>
                                                    :
                                                        this.renderLogsLink()
                                                    )
                                                }
                                            </div>
                                        }
                                    </div>
                                </div>
                                <div className='hardware-info clearfix'>
                                    <div className={utils.classNames(logoClasses)} />
                                    {this.renderNodeHardwareSummary()}
                                </div>
                                <div className='node-popover-buttons'>
                                    <button className='btn btn-default node-details' onClick={this.showNodeDetails}>Details</button>
                                </div>
                            </div>
                        </controls.Popover>
                    }
                </div>
            );

            return (
                <div className={utils.classNames(nodePanelClasses)}>
                    <label className='node-box'>
                        {this.renderNodeCheckbox()}
                        <div className={utils.classNames(logoClasses)} />
                        <div className='node-name'>
                            <div className='name'>
                                {this.renderNameControl()}
                            </div>
                            <div className='role-list'>
                                {this.renderRoleList(roles)}
                            </div>
                        </div>
                        <div className='node-action'>
                            {!!node.get('cluster') &&
                                ((this.props.locked || !node.hasChanges()) ?
                                    this.renderLogsLink(true)
                                :
                                    <div
                                        className='icon'
                                        title={i18n(ns + (node.get('pending_addition') ? 'discard_addition' : 'discard_deletion'))}
                                        onClick={node.get('pending_addition') ? this.showDeleteNodesDialog : this.discardNodeChanges}
                                    />
                                )
                            }
                        </div>
                        <div className={utils.classNames(statusClasses)}>
                            {_.contains(['provisioning', 'deploying'], status) ?
                                this.renderNodeProgress(true)
                            :
                                <div>
                                    {this.renderStatusLabel(status)}
                                    {status == 'offline' && this.renderRemoveButton()}
                                </div>
                            }
                        </div>
                        {this.renderNodeHardwareSummary()}
                        <div className='node-settings' onClick={this.showNodeDetails} />
                    </label>
                </div>
            );
        }
    });

    return NodeListScreen;
});
