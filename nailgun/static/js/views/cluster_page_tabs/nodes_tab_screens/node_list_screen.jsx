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
            var cluster = this.props.cluster,
                settings = cluster.get('settings'),
                roles = cluster.get('release').get('roles'),
                selectedRoles = this.props.nodes.length ? _.filter(roles, function(role) {
                    return !this.props.nodes.any(function(node) {return !node.hasRole(role);});
                }, this) : [];
            return {
                loading: this.props.mode == 'add',
                search: '',
                sorting: [this.getDefaultSorting()],
                filters: {},
                viewMode: cluster.get('view_mode'),
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
        changeSearch: _.debounce(function(value) {
            this.setState({search: value});
        }, 200, {leading: true}),
        clearSearchField: function() {
            this.setState({search: ''});
        },
        changeSorting: function(name, value) {
            var sorting = this.state.sorting;
            sorting[name] = {};
            sorting[name][value] = 'asc';
            this.setState({sorting: sorting});
        },
        addSorting: function() {
            var sorting = this.state.sorting;
            sorting.push(this.getDefaultSorting());
            this.setState({sorting: sorting});
        },
        removeSorting: function(index) {
            var sorting = this.state.sorting;
            sorting.splice(index, 1);
            this.setState({sorting: sorting});
        },
        resetSorters: function() {
            this.setState({sorting: [this.getDefaultSorting()]});
        },
        applyFilters: function(filtersData) {
            this.setState({filters: filtersData});
        },
        resetFilters: function() {
            this.setState({filters: {}});
        },
        changeViewMode: function(e) {
            var newMode = $(e.currentTarget).find('input:checked').val();
            this.setState({viewMode: newMode});
            this.props.cluster.save({view_mode: newMode}, {patch: true, wait: true});
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
                    var range = activeFilters.split('..'),
                        value;
                    if (_.contains(['hdd', 'ram']), filter) {
                        value = node.resource(filter) / Math.pow(1024, 3);
                    } else {
                        if (filter == 'cpu_real') {
                            value = node.resource('cores');
                        } else if (filter == 'cpu_total') {
                            value = node.resource('ht_cores');
                        } else {
                            value = node.resource(filter);
                        }
                    }
                    return value >= Number(range[0]) && value <= Number(range[1]);
                });
            }, this);

            return (
                <div>
                    {this.props.mode == 'edit' &&
                        <div className='alert alert-warning'>{i18n('cluster_page.nodes_tab.disk_configuration_reset_warning')}</div>
                    }
                    <ManagementPanel
                        mode={this.props.mode}
                        screenNodes={nodes}
                        filteredNodes={filteredNodes}
                        nodes={new models.Nodes(_.compact(_.map(this.state.selectedNodeIds, function(checked, id) {
                            if (checked) return nodes.get(id);
                        })))}
                        cluster={cluster}
                        sorting={this.state.sorting}
                        changeSorting={this.changeSorting}
                        addSorting={this.addSorting}
                        removeSorting={this.removeSorting}
                        resetSorters={this.resetSorters}
                        search={this.state.search}
                        filters={this.state.filters}
                        applyFilters={this.applyFilters}
                        resetFilters={this.resetFilters}
                        changeSearch={this.changeSearch}
                        clearSearchField={this.clearSearchField}
                        viewMode={this.state.viewMode}
                        changeViewMode={this.changeViewMode}
                        hasChanges={!this.isMounted() || this.hasChanges()}
                        locked={locked || this.state.loading}
                        revertChanges={this.revertChanges}
                    />
                    {this.state.loading ? <controls.ProgressBar /> :
                        <div>
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
                    }
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
            this.refs.search.getInputDOMNode().value = '';
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
            this.setState({key: _.now()});
        },
        updateQueryString: function(url) {
            url = url || '';
            app.navigate('#cluster/' + this.props.cluster.id + '/nodes/' + this.props.mode + '/' + url, {trigger: false, replace: true});
        },
        applyFilters: function() {
            var filtersData = {};
            _.each(this.state.visibleFilters, function(name) {
                var chosenOptions = _.uniq(this.refs[name].state.values);
                if (_.compact(chosenOptions).length) {
                    filtersData[name] = this.refs[name].props.type == 'range' ? chosenOptions.join('..') : chosenOptions;
                }
            }, this);

            // update url with query string
            var url = utils.serializeTabOptions(filtersData) + ';' + (_.map(this.props.sorting, function(sortObject) {
                return _.keys(sortObject)[0] + ':' + _.values(sortObject)[0];
            })).join(',');
            this.updateQueryString(url);

            this.props.applyFilters(filtersData);
            $(this.refs.filters.getDOMNode()).collapse('hide');
        },
        resetFilters: function() {
            this.setState({visibleFilters: _.pluck(_.filter(this.getFilters(), 'base'), 'name')});
            this.props.resetFilters();

            var url = ';' + (_.map(this.props.sorting, function(sortObject) {
                return _.keys(sortObject)[0] + ':' + _.values(sortObject)[0];
            })).join(',');
            this.updateQueryString(url);
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
        renderDeleteFilterButton: function(filter) {
            if (filter.base) return null;
            return (
                <button className='btn btn-link' onClick={_.partial(this.removeFilter, filter.name)}>
                    <i className='glyphicon glyphicon-minus-sign' />
                </button>
            );
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

            var sortingOptions = _.map(this.props.cluster.sorters(this.props.mode), function(sorter) {
                return <option key={sorter} value={sorter}>{i18n('cluster_page.nodes_tab.sorters.' + sorter)}</option>;
            });

            var filters = this.getFilters(),
                hiddenFilters = _.filter(filters, function(filter) {
                    return !_.contains(this.state.visibleFilters, filter.name);
                }, this);

            return (
                <div className='row' key={this.state.key}>
                    <div className='sticker node-management-panel'>
                        <div className='node-list-management-buttons col-xs-6'>
                            <div className='view-mode-switcher'>
                                <div className='btn-group' data-toggle='buttons'>
                                    {_.map(['standard', 'compact'], function(mode) {
                                        return (
                                            <label
                                                key={mode + '-view'}
                                                className={utils.classNames({'btn btn-default': true, active: mode == this.props.viewMode})}
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
                                    className='btn btn-default pull-left'
                                    disabled={!this.props.screenNodes.length}
                                    data-toggle='collapse'
                                    data-target='.sorters'
                                    onClick={_.bind(function() {
                                        $(this.refs.filters.getDOMNode()).collapse('hide');
                                    }, this)}
                                >
                                    <i className='glyphicon glyphicon-sort' />
                                </button>,
                                <button
                                    key='filters-btn'
                                    className='btn btn-default pull-left'
                                    disabled={!this.props.screenNodes.length}
                                    data-toggle='collapse'
                                    data-target='.filters'
                                    onClick={_.bind(function() {
                                        $(this.refs.sorters.getDOMNode()).collapse('hide');
                                    }, this)}
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
                                            disabled={this.props.locked || !this.props.nodes.length}
                                            onClick={_.bind(this.goToConfigurationScreen, this, 'disks', disksConflict)}
                                        >
                                            {disksConflict && <i className='glyphicon glyphicon-warning-sign text-danger' />}
                                            {i18n('dialog.show_node.disk_configuration_button')}
                                        </button>
                                        {!this.props.nodes.any({status: 'error'}) &&
                                            <button
                                                className='btn btn-default btn-configure-interfaces'
                                                disabled={this.props.locked || !this.props.nodes.length}
                                                onClick={_.bind(this.goToConfigurationScreen, this, 'interfaces', interfaceConflict)}
                                            >
                                                {interfaceConflict && <i className='glyphicon glyphicon-warning-sign text-danger' />}
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
                        {this.props.mode != 'edit' && !!this.props.screenNodes.length && [
                            <div className='col-xs-12 sorters collapse' key='sorters' ref='sorters'>
                                <div className='well clearfix'>
                                    <div className='well-heading'>
                                        <i className='glyphicon glyphicon-sort' /> {i18n(ns + 'sort_by')}
                                        <button className='btn btn-link pull-right' onClick={this.props.resetSorters}>
                                            <i className='glyphicon glyphicon-remove-sign' /> Clear All
                                        </button>
                                    </div>
                                    {this.props.sorting.map(function(sortObject, index) {
                                        return (
                                            <controls.Input
                                                key={'sort_by-' + index}
                                                type='select'
                                                name={index}
                                                children={sortingOptions}
                                                onChange={this.props.changeSorting}
                                                extraContent={this.renderDeleteSorterButton(index)}
                                                wrapperClassName='pull-left'
                                            />
                                        );
                                    }, this)}
                                    <button className='btn btn-link pull-left' onClick={this.props.addSorting}>More</button>
                                </div>
                            </div>,
                            <div className='col-xs-12 filters collapse' key='filters' ref='filters'>
                                <div className='well clearfix'>
                                    <div className='well-heading'>
                                        <i className='glyphicon glyphicon-filter' /> {i18n(ns + 'filter_by')}
                                        <button className='btn btn-link pull-right' onClick={this.resetFilters}>
                                            <i className='glyphicon glyphicon-remove-sign' /> Clear All
                                        </button>
                                    </div>
                                    {_.map(this.state.visibleFilters, function(filterName) {
                                        var filter = _.find(filters, {name: filterName}),
                                            Control = filter.type == 'range' ? controls.NumberRange : controls.MultiSelect;
                                        return <Control {...filter} key={filterName} ref={filterName} extraContent={this.renderDeleteFilterButton(filter)} />;
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
                                            <button className='btn btn-success' onClick={this.applyFilters}>
                                                {i18n('common.apply_button')}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ]}
                        {!!this.props.screenNodes.length && _.any(this.props.filters, function(values) {return values.length;}) &&
                            <div className='col-xs-12'>
                                <div className='active-filters clearfix'>
                                    <strong className='pull-left'>
                                        <i className='glyphicon glyphicon-filter' /> {i18n(ns + 'filter_by')}
                                    </strong>
                                    {_.map(this.props.filters, function(values, filterName) {
                                        var filter = _.find(filters, {name: filterName});
                                        return (
                                            <div className='pull-left' key={filterName}>
                                                <span>{filter.label}: </span>
                                                <strong>
                                                    {filter.type == 'range' ?
                                                        _.compact(values.split('..')).join(' - ') + ' ' + filter.prefix
                                                    :
                                                        _.map(values, function(value) {
                                                            return _.find(filter.options, {name: value}).label;
                                                        }).join(', ')
                                                    }
                                                </strong>
                                            </div>
                                        );
                                    })}
                                    <button className='btn btn-link pull-right' onClick={this.resetFilters}>
                                        <i className='glyphicon glyphicon-remove-sign' />
                                    </button>
                                </div>
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
                                    defaultChecked={_.contains(this.props.selectedRoles, name)}
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
        renderSelectAllCheckbox: function(label) {
            var availableNodesIds = _.compact(this.props.nodes.map(function(node) {if (node.isSelectable()) return node.id;})),
                checked = this.props.mode == 'edit' || (availableNodesIds.length && !_.any(availableNodesIds, function(id) {return !this.props.selectedNodeIds[id];}, this));

            var selectedNodes = _.compact(this.props.nodes.map(function(node) {return this.props.selectedNodeIds[node.id];}, this));
            return (
                <controls.Input
                    ref='select-all'
                    type='checkbox'
                    checked={checked}
                    disabled={
                        this.props.mode == 'edit' || this.props.locked || !availableNodesIds.length ||
                        !checked && !_.isNull(this.props.maxNumberOfNodes) && this.props.maxNumberOfNodes < availableNodesIds.length
                    }
                    label={label + i18n('cluster_page.nodes_tab.selected_nodes_amount', {selected: selectedNodes.length || 0, total: this.props.nodes.length})}
                    wrapperClassName='select-all'
                    onChange={_.bind(this.props.selectNodes, this.props, availableNodesIds)} />
            );
        }
    };

    NodeList = React.createClass({
        mixins: [SelectAllMixin],
        groupNodes: function() {
            var release = this.props.cluster.get('release'),
                releaseRoles = release.get('role_models'),
                os = release.get('operating_system') || i18n('node_details.os');

            var specialSorters = ['name', 'mac', 'ip'],
                usedSorters = _.uniq(_.flatten(_.map(this.props.sorting, _.keys))),
                usedNotSpecialSorters = _.difference(usedSorters, specialSorters);

            var groups;
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
                    })).join('; ');
                }, this);
                groups = _.pairs(_.groupBy(this.props.nodes, groupingMethod));
            } else {
                groups = [[this.props.cluster.get('name'), this.props.nodes]];
            }

            // sort grouped nodes by name, mac or ip
            var usedSpecialSorters = _.intersection(usedSorters, specialSorters);
            if (usedSpecialSorters.length) {
                var formattedSorters = _.map(usedSpecialSorters, function(sorter) {return {attr: sorter};});
                _.each(groups, function(group) {
                    group[1].sort(function(node1, node2) {
                        return utils.multiSort(node1, node2, formattedSorters);
                    });
                });
            }

            // TODO: sort node groups (natsort usage; roles by default)
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
            var groups = this.groupNodes(),
                rolesWithLimitReached = _.keys(_.omit(this.props.processedRoleLimits, function(roleLimit, roleName) {
                    return roleLimit.valid || !_.contains(this.props.selectedRoles, roleName);
                }, this));
            return (
                <div className='node-list row'>
                    {groups.length > 1 &&
                        <div className='col-xs-12 node-list-header'>
                            {this.renderSelectAllCheckbox(this.props.cluster.get('name'))}
                        </div>
                    }
                    <div className='col-xs-12'>
                        {groups.map(function(group, index) {
                            return <NodeGroup {...this.props}
                                key={group[0]}
                                index={index}
                                label={group[0]}
                                nodes={group[1]}
                                rolesWithLimitReached={rolesWithLimitReached}
                            />;
                        }, this)}
                        {!this.props.screenNodes.length &&
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
                        <div className='col-xs-11'>
                            {this.renderSelectAllCheckbox(this.props.label)}
                        </div>
                        <div className='col-xs-1 text-right'>
                            <i
                                className={'glyphicon glyphicon-chevron-' + (this.state.collapsed ? 'down' : 'up')}
                                onClick={this.toggleIcon}
                                data-toggle='collapse'
                                data-target={'.node-group-content.' + this.props.index}
                            />
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
                                onNodeSelection={this.props.mode != 'edit' && _.bind(this.props.selectNodes, this.props, [node.id])}
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
                extendedView: false
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
            dialogs.ShowNodeInfoDialog.show({node: this.props.node});
        },
        sortRoles: function(roles) {
            var preferredOrder = this.props.cluster.get('release').get('roles');
            return roles.sort(function(a, b) {
                return _.indexOf(preferredOrder, a) - _.indexOf(preferredOrder, b);
            });
        },
        showCompactNodePopover: function() {
            this.timer = setTimeout(function() {
                this.setState({extendedView: !this.state.extendedView});
            }.bind(this), 500);
        },
        clearNodeExtendedViewTimeout: function() {
            if (this.timer) clearTimeout(this.timer);
            if (this.state.extendedView) this.setState({extendedView: false});
        },
        onNodeSelection: function(name, value) {
            if (this.timer) clearTimeout(this.timer);
            this.props.onNodeSelection(name, value);
        },
        render: function() {
            var ns = 'cluster_page.nodes_tab.node.',
                node = this.props.node,
                disabled = this.props.locked || !node.isSelectable() || this.state.actionInProgress,
                deployedRoles = node.get('roles'),
                nodeProgress = _.max([node.get('progress'), 3]),
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

            var roleClasses = {'text-success': !deployedRoles.length};

            var statusClasses = {
                    'node-status font-semibold text-center': true
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
                    <div
                        className={utils.classNames(nodePanelClasses)}
                        onMouseEnter={this.showCompactNodePopover}
                        onMouseLeave={!this.state.extendedView && this.clearNodeExtendedViewTimeout}
                    >
                        <label className='node-box' onClick={!disabled && this.onNodeSelection.bind(this, null, !this.props.checked)}>
                            <div className='node-box-inner clearfix'>
                                <div className='node-buttons'>
                                    {this.props.checked && <i className='glyphicon glyphicon-ok text-success' />}
                                </div>
                                <div className='node-name'>
                                    <p>{node.get('name') || node.get('mac')}</p>
                                </div>
                                <div className={utils.classNames(statusClasses)}>
                                    {_.contains(['provisioning', 'deploying'], status) ?
                                        <div className='progress'>
                                            <div
                                                className='progress-bar'
                                                role='progressbar'
                                                style={{width: nodeProgress + '%'}}
                                            />
                                        </div>
                                    :
                                        <div>
                                            <span>{i18n(ns + 'status.' + status, {os: this.props.cluster.get('release').get('operating_system') || 'OS'})}</span>
                                        </div>
                                    }
                                </div>
                            </div>
                            <div className='node-hardware'>
                                <span>{node.resource('cores') || '0'} ({node.resource('ht_cores') || '?'})</span>/
                                <span>{node.resource('hdd') ? utils.showDiskSize(node.resource('hdd')) : '?' + i18n('common.size.gb')}</span>/
                                <span>{node.resource('ram') ? utils.showMemorySize(node.resource('ram')) : '?' + i18n('common.size.gb')}</span>
                            </div>
                        </label>
                    </div>
                    {this.state.extendedView &&
                        <div className='node-popover' onMouseLeave={this.clearNodeExtendedViewTimeout}>
                            <div className='node-name clearfix'>
                                <controls.Input
                                    type='checkbox'
                                    name={node.id}
                                    checked={this.props.checked}
                                    disabled={disabled}
                                    onChange={this.props.onNodeSelection}
                                    wrapperClassName='pull-left'
                                />
                                <div className='name'>
                                    {this.state.renaming ?
                                        <controls.Input
                                            ref='name'
                                            type='text'
                                            defaultValue={node.get('name')}
                                            inputClassName='form-control node-name-input'
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
                            </div>
                            <div className='node-stats font-semibold'>
                                {!!roles.length &&
                                    <div className='role-list'>
                                        <i className='glyphicon glyphicon-pushpin' />
                                        <ul className='clearfix'>
                                            {_.map(roles, function(role) {
                                                return <li key={node.id + role} className={utils.classNames(roleClasses)}>{role}</li>;
                                            })}
                                        </ul>
                                    </div>
                                }
                                <div className={utils.classNames(statusClasses)}>
                                    {_.contains(['provisioning', 'deploying'], status) ?
                                        <div>
                                            <p>{i18n(ns + 'status.' + status, {os: this.props.cluster.get('release').get('operating_system') || 'OS'})}:</p>
                                            <div className='progress'>
                                                <div
                                                    className='progress-bar'
                                                    role='progressbar'
                                                    style={{width: nodeProgress + '%'}}
                                                >
                                                    {nodeProgress + '%'}
                                                </div>
                                            </div>
                                        </div>
                                    :
                                        <div>
                                            <i className='glyphicon glyphicon-time' />
                                            <span>{i18n(ns + 'status.' + status, {os: this.props.cluster.get('release').get('operating_system') || 'OS'})}</span>
                                            {status == 'offline' &&
                                                <button onClick={this.removeNode} className='btn node-remove-button'>{i18n(ns + 'remove')}</button>
                                            }
                                            {!!node.get('cluster') &&
                                                ((this.props.locked || !node.hasChanges()) ?
                                                    <a className='btn' href={this.getNodeLogsLink()}>Show Logs</a>
                                                :
                                                    <button className='btn' onClick={this.discardNodeChanges}>
                                                        {i18n(ns + (node.get('pending_addition') ? 'discard_addition' : 'discard_deletion'))}
                                                    </button>
                                                )
                                            }
                                        </div>
                                    }
                                </div>
                            </div>
                            <div className='hardware-info clearfix'>
                                <div className={utils.classNames(logoClasses)} />
                                <div className='node-hardware'>
                                    <span>{i18n('node_details.cpu')}: {node.resource('cores') || '0'} ({node.resource('ht_cores') || '?'})</span>
                                    <span>{i18n('node_details.hdd')}: {node.resource('hdd') ? utils.showDiskSize(node.resource('hdd')) : '?' + i18n('common.size.gb')}</span>
                                    <span>{i18n('node_details.ram')}: {node.resource('ram') ? utils.showMemorySize(node.resource('ram')) : '?' + i18n('common.size.gb')}</span>
                                </div>
                            </div>
                            <div className='node-popover-buttons'>
                                <button className='btn btn-default' onClick={this.showNodeDetails}>Details</button>
                            </div>
                        </div>
                    }
                </div>
            );

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
                            <div className='name'>
                                {this.state.renaming ?
                                    <controls.Input
                                        ref='name'
                                        type='text'
                                        defaultValue={node.get('name')}
                                        inputClassName='form-control node-name-input'
                                        disabled={this.state.actionInProgress}
                                        onKeyDown={this.onNodeNameInputKeydown}
                                        autoFocus
                                    />
                                :
                                    <p title={i18n(ns + 'edit_name')} onClick={!this.state.actionInProgress && this.startNodeRenaming}>
                                        {node.get('name') || node.get('mac')}
                                    </p>
                                }
                            </div>
                            <div className='role-list font-semibold'>
                                {!!roles.length &&
                                    <ul>
                                        {_.map(roles, function(role) {
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
                                        className='icon'
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
                                        style={{width: nodeProgress + '%'}}
                                    >
                                        {nodeProgress + '%'}
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
