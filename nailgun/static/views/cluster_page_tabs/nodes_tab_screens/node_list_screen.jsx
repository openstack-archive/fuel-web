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
    'jsx!component_mixins',
    'jsx!views/cluster_page_tabs/nodes_tab_screens/node'
],
function($, _, i18n, Backbone, React, utils, models, dispatcher, controls, dialogs, componentMixins, Node) {
    'use strict';
    var NodeListScreen, MultiSelectControl, NumberRangeControl, ManagementPanel, RolePanel, SelectAllMixin, NodeList, NodeGroup;

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
                search: this.props.mode == 'add' ? '' : uiSettings.search,
                activeSorters: this.props.mode == 'add' ? _.clone(this.props.defaultSorting) : uiSettings.sort,
                activeFilters: this.props.mode == 'add' ? {} : uiSettings.filter,
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

            if (this.props.mode != 'list') {
                // hack to prevent node roles update after node polling
                this.props.nodes.on('change:pending_roles', this.checkRoleAssignment, this);
            }
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

            cluster.get('roles').map(function(role) {
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
            this.updateSearch(value);
        }, 200, {leading: true}),
        clearSearchField: function() {
            this.updateSearch('');
        },
        updateSearch: function(value) {
            this.setState({search: value});
            if (this.props.mode != 'add') this.changeUISettings('search', value);
        },
        addSorting: function(sorterName) {
            var activeSorters = this.state.activeSorters,
                newSorter = {};
            newSorter[sorterName] = 'asc';
            activeSorters.push(newSorter);
            this.updateSorting(activeSorters);
        },
        removeSorting: function(sorter) {
            this.updateSorting(_.difference(this.state.activeSorters, [sorter]));
        },
        resetSorters: function() {
            this.updateSorting(this.props.defaultSorting);
        },
        changeSortingOrder: function(sorterName) {
            var activeSorters = this.state.activeSorters,
                sorter = _.find(activeSorters, function(sorter) {
                    return sorter[sorterName];
                });
            sorter[sorterName] = sorter[sorterName] == 'asc' ? 'desc' : 'asc';
            this.updateSorting(activeSorters);
        },
        updateSorting: function(sorters) {
            this.setState({activeSorters: sorters});
            if (this.props.mode != 'add') this.changeUISettings('sort', sorters);
        },
        updateFilters: function(filters) {
            this.setState({activeFilters: filters});
            if (this.props.mode != 'add') this.changeUISettings('filter', filters);
        },
        addFilter: function(filterName) {
            var activeFilters = this.state.activeFilters;
            activeFilters[filterName] = [];
            this.updateFilters(activeFilters);
        },
        changeFilter: function(filterName, values) {
            var activeFilters = this.state.activeFilters;
            activeFilters[filterName] = values;
            this.updateFilters(activeFilters);
        },
        removeFilter: function(filterName) {
            var activeFilters = this.state.activeFilters;
            delete activeFilters[filterName];
            this.updateFilters(activeFilters);
        },
        resetFilters: function() {
            this.updateFilters({});
        },
        changeViewMode: function(name, value) {
            this.setState({viewMode: value});
            this.changeUISettings('view_mode', value);
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
                if (this.state.search) {
                    var search = this.state.search.toLowerCase();
                    if (!_.any(node.pick('name', 'mac', 'ip'), function(attribute) {
                        return _.contains(attribute.toLowerCase(), search);
                    })) {
                        return false;
                    }
                }

                // filters
                return _.all(this.state.activeFilters, function(values, filter) {
                    if (!_.contains(this.props.filters, filter) || !values.length) {
                        return true;
                    }

                    if (filter == 'roles') {
                        return _.any(values, function(role) {return node.hasRole(role);});
                    }
                    if (filter == 'status') {
                        return _.contains(values, node.getStatusSummary());
                    }
                    if (filter == 'manufacturer') {
                        return _.contains(values, node.get('manufacturer'));
                    }

                    // handle number ranges
                    var currentValue = node.resource(filter);
                    if (filter == 'hdd' || filter == 'ram') {
                        currentValue = currentValue / Math.pow(1024, 3);
                    }
                    return currentValue >= values[0] && (_.isUndefined(values[1]) || currentValue <= values[1]);
                }, this);
            }, this);

            return (
                <div>
                    {this.props.mode == 'edit' &&
                        <div className='alert alert-warning'>
                            {i18n('cluster_page.nodes_tab.disk_configuration_reset_warning')}
                        </div>
                    }
                    <ManagementPanel
                        {... _.pick(this.state, 'viewMode', 'search', 'activeSorters', 'activeFilters')}
                        {... _.pick(this.props, 'cluster', 'mode', 'sorters', 'defaultSorting', 'filters', 'statusesToFilter', 'defaultFilters')}
                        {... _.pick(this, 'addSorting', 'removeSorting', 'resetSorters', 'changeSortingOrder')}
                        {... _.pick(this, 'addFilter', 'changeFilter', 'removeFilter', 'resetFilters')}
                        {... _.pick(this, 'changeSearch', 'clearSearchField')}
                        {... _.pick(this, 'changeViewMode')}
                        nodes={new models.Nodes(_.compact(_.map(this.state.selectedNodeIds, function(checked, id) {
                            if (checked) return nodes.get(id);
                        })))}
                        screenNodes={nodes}
                        filteredNodesLength={filteredNodes.length}
                        hasChanges={this.hasChanges()}
                        locked={locked}
                        revertChanges={this.revertChanges}
                    />
                    {this.props.mode != 'list' &&
                        <RolePanel
                            {... _.pick(this.state, 'selectedNodeIds', 'selectedRoles', 'indeterminateRoles', 'configModels')}
                            {... _.pick(this.props, 'cluster', 'mode', 'nodes')}
                            {... _.pick(processedRoleData, 'processedRoleLimits')}
                            selectRoles={this.selectRoles}
                        />
                    }
                    <NodeList
                        {... _.pick(this.state, 'viewMode', 'activeSorters', 'selectedNodeIds', 'selectedRoles')}
                        {... _.pick(this.props, 'cluster', 'mode', 'statusesToFilter')}
                        {... _.pick(processedRoleData, 'maxNumberOfNodes', 'processedRoleLimits')}
                        nodes={filteredNodes}
                        totalNodesLength={nodes.length}
                        locked={locked}
                        selectNodes={this.selectNodes}
                    />
                </div>
            );
        }
    });

    MultiSelectControl = React.createClass({
        propTypes: {
            name: React.PropTypes.string,
            options: React.PropTypes.arrayOf(React.PropTypes.object).isRequired,
            values: React.PropTypes.arrayOf(React.PropTypes.string),
            label: React.PropTypes.node.isRequired,
            dynamicValues: React.PropTypes.bool,
            onChange: React.PropTypes.func,
            extraContent: React.PropTypes.node
        },
        getInitialState: function() {
            return {isOpen: false};
        },
        getDefaultProps: function() {
            return {values: []};
        },
        toggle: function(visible) {
            this.setState({
                isOpen: _.isBoolean(visible) ? visible : !this.state.isOpen
            });
        },
        onChange: function(name, checked) {
            if (!this.props.dynamicValues) {
                var values = name == 'all' ?
                        checked ? _.pluck(this.props.options, 'name') : []
                    :
                        checked ? _.union(this.props.values, [name]) : _.difference(this.props.values, [name]);
                this.props.onChange(values);
            } else {
                this.props.onChange(checked && name);
            }
        },
        render: function() {
            var valuesAmount = this.props.values.length,
                label = (this.props.dynamicValues || !valuesAmount) ? this.props.label : valuesAmount > 3 ?
                        i18n('cluster_page.nodes_tab.node_management_panel.selected_options', {label: this.props.label, count: valuesAmount})
                    :
                        _.map(this.props.values, function(itemName) {
                        return _.find(this.props.options, {name: itemName}).label;
                    }, this).join(', ');

            this.props.options.sort(function(option1, option2) {
                return utils.natsort(option1.label, option2.label);
            });

            return (
                <div className={utils.classNames({'btn-group multiselect': true, open: this.state.isOpen})}>
                    <button
                        className={'btn dropdown-toggle ' + ((this.props.dynamicValues && !this.state.isOpen) ? 'btn-link' : 'btn-default')}
                        onClick={this.toggle}
                    >
                        {label} <span className='caret'></span>
                    </button>
                    {this.state.isOpen &&
                        <controls.Popover toggle={this.toggle}>
                            {!this.props.dynamicValues && [
                                    <div key='all'>
                                        <controls.Input
                                            type='checkbox'
                                            label={i18n('cluster_page.nodes_tab.node_management_panel.select_all')}
                                            name='all'
                                            checked={valuesAmount == this.props.options.length}
                                            onChange={this.onChange}
                                        />
                                    </div>,
                                    <div key='divider' className='divider' />
                                ]
                            }
                            {_.map(this.props.options, function(option, index) {
                                return (
                                    <controls.Input {...option}
                                        key={index}
                                        type='checkbox'
                                        checked={_.contains(this.props.values, option.name)}
                                        onChange={this.onChange}
                                    />
                                );
                            }, this)}
                        </controls.Popover>
                    }
                    {this.props.extraContent}
                </div>
            );
        }
    });

    NumberRangeControl = React.createClass({
        propTypes: {
            name: React.PropTypes.string,
            label: React.PropTypes.node.isRequired,
            values: React.PropTypes.array,
            onChange: React.PropTypes.func,
            extraContent: React.PropTypes.node,
            prefix: React.PropTypes.string
        },
        getInitialState: function() {
            return {isOpen: false};
        },
        getDefaultProps: function() {
            return {values: []};
        },
        toggle: function(visible) {
            this.setState({
                isOpen: _.isBoolean(visible) ? visible : !this.state.isOpen
            });
        },
        changeStartValue: function(name, value) {
            value = Number(value);
            if (!_.isNaN(value)) {
                var values = this.props.values;
                // 0 is minimum for start value
                values[0] = value || 0;
                this.props.onChange(values);
            }
        },
        changeEndValue: function(name, value) {
            value = Number(value);
            if (!_.isNaN(value)) {
                var values = this.props.values;
                // set undefined value if user enters an epmty string
                values[1] = value || undefined;
                this.props.onChange(values);
            }
        },
        render: function() {
            var values = this.props.values;
            var props = {
                    type: 'number',
                    inputClassName: 'pull-left',
                    error: values[0] < 0 || values[1] < 0 || values[0] > values[1] || null,
                    min: 0
                };
            var ns = 'cluster_page.nodes_tab.node_management_panel.',
                label = _.isEmpty(values) ?
                    this.props.label
                :
                    this.props.label + ': ' + (
                        !_.isUndefined(values[0]) && !_.isUndefined(values[1]) ?
                            _.uniq(values).join(' - ')
                        :
                            !_.isUndefined(values[0]) ?
                                    i18n(ns + 'more_than') + values[0]
                                :
                                    i18n(ns + 'less_than') + values[1] + ' ' + this.props.prefix
                    );

            return (
                <div className={utils.classNames({'btn-group number-range': true, open: this.state.isOpen})}>
                    <button className='btn btn-default dropdown-toggle' onClick={this.toggle}>
                        {label} <span className='caret'></span>
                    </button>
                    {this.state.isOpen &&
                        <controls.Popover toggle={this.toggle}>
                            <div className='clearfix'>
                                <controls.Input {...props}
                                    name={this.props.name + '-start'}
                                    value={values[0]}
                                    onChange={this.changeStartValue}
                                />
                                <span className='pull-left'> &mdash; </span>
                                <controls.Input {...props}
                                    name={this.props.name + '-end'}
                                    value={values[1]}
                                    onChange={this.changeEndValue}
                                />
                            </div>
                        </controls.Popover>
                    }
                    {this.props.extraContent}
                </div>
            );
        }
    });

    ManagementPanel = React.createClass({
        getInitialState: function() {
            return {
                actionInProgress: false,
                isSearchButtonVisible: !!this.props.search,
                activeSearch: !!this.props.search
            };
        },
        getFilterOptions: function(filter) {
            var options;
            switch (filter) {
                case 'status':
                    var os = this.props.cluster.get('release').get('operating_system') || 'OS';
                    options = this.props.statusesToFilter.map(function(status) {
                        return {
                            name: status,
                            label: i18n('cluster_page.nodes_tab.node.status.' + status, {os: os})
                        };
                    });
                    break;
                case 'manufacturer':
                    options = _.uniq(this.props.screenNodes.pluck('manufacturer')).map(function(manufacturer) {
                        return {
                            name: manufacturer.replace(/\s/g, '_'),
                            label: manufacturer
                        };
                    });
                    break;
                case 'roles':
                    options = this.props.cluster.get('roles').invoke('pick', 'name', 'label');
                    break;
            }
            return options;
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
        searchNodes: function(name, value) {
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
        removeSorting: function(sorter) {
            this.props.removeSorting(sorter);
            this.setState({sortersKey: _.now()});
        },
        resetSorters: function(e) {
            e.stopPropagation();
            this.props.resetSorters();
            this.setState({sortersKey: _.now()});
        },
        removeFilter: function(name) {
            this.props.removeFilter(name);
            this.setState({filtersKey: _.now()});
        },
        resetFilters: function(e) {
            e.stopPropagation();
            this.props.resetFilters();
            this.setState({filtersKey: _.now()});
        },
        toggleSorters: function() {
            this.setState({
                areSortersVisible: !this.state.areSortersVisible,
                areFiltersVisible: false
            });
        },
        toggleFilters: function() {
            this.setState({
                areFiltersVisible: !this.state.areFiltersVisible,
                areSortersVisible: false
            });
        },
        renderDeleteFilterButton: function(filter) {
            if (_.contains(this.props.defaultFilters, filter)) return null;
            return (
                <i className='btn btn-link glyphicon glyphicon-minus-sign' onClick={_.partial(this.removeFilter, filter)} />
            );
        },
        renderDeleteSorterButton: function(sorter) {
            var isDefaultSorter = _.any(this.props.defaultSorting, function(defaultSorter) {
                return _.isEqual(defaultSorter, sorter);
            });
            if (isDefaultSorter) return null;
            return (
                <i className='btn btn-link glyphicon glyphicon-minus-sign' onClick={_.partial(this.removeSorting, sorter)} />
            );
        },
        render: function() {
            var ns = 'cluster_page.nodes_tab.node_management_panel.';

            var sampleNode, disksConflict, interfaceConflict;
            if (this.props.mode == 'list') {
                sampleNode = this.props.nodes.at(0);
                disksConflict = this.props.nodes.any(function(node) {
                    var roleConflict = _.difference(_.union(sampleNode.get('roles'), sampleNode.get('pending_roles')), _.union(node.get('roles'), node.get('pending_roles'))).length;
                    return roleConflict || !_.isEqual(sampleNode.resource('disks'), node.resource('disks'));
                });
                interfaceConflict = _.uniq(this.props.nodes.map(function(node) {return node.resource('interfaces');})).length > 1;
            }

            var managementButtonClasses = _.bind(function(isActive, className) {
                var classes = {
                    'btn btn-default pull-left': true,
                    active: isActive
                };
                classes[className] = true;
                return classes;
            }, this);

            var activeSorters, inactiveSorters;
            var filtersToDisplay, inactiveFilters, filtersWithChosenValues;
            if (this.props.mode != 'edit') {
                activeSorters = _.flatten(_.map(this.props.activeSorters, _.keys));
                inactiveSorters = _.difference(this.props.sorters, activeSorters);
                filtersToDisplay = _.extend(_.zipObject(this.props.defaultFilters, _.times(this.props.defaultFilters.length, function() {return [];})), this.props.activeFilters);
                inactiveFilters = _.difference(this.props.filters, _.keys(filtersToDisplay));
                filtersWithChosenValues = _.omit(this.props.activeFilters, function(values) {return !values.length;});
            }

            return (
                <div className='row'>
                    <div className='sticker node-management-panel'>
                        <div className='node-list-management-buttons col-xs-6'>
                            <div className='view-mode-switcher'>
                                <div className='btn-group' data-toggle='buttons'>
                                    {_.map(this.props.cluster.viewModes(), function(mode) {
                                        return (
                                            <label
                                                key={mode + '-view'}
                                                className={utils.classNames(managementButtonClasses(mode == this.props.viewMode, mode))}
                                                onClick={mode != this.props.viewMode && _.partial(this.props.changeViewMode, 'view_mode', mode)}
                                            >
                                                <input type='radio' name='view_mode' value={mode} />
                                                <i className={utils.classNames({
                                                    glyphicon: true,
                                                    'glyphicon-th-list': mode == 'standard',
                                                    'glyphicon-th': mode == 'compact'
                                                })} />
                                            </label>
                                        );
                                    }, this)}
                                </div>
                            </div>
                            {this.props.mode != 'edit' && [
                                <button
                                    key='sorters-btn'
                                    disabled={!this.props.screenNodes.length}
                                    onClick={this.toggleSorters}
                                    className={utils.classNames(managementButtonClasses(this.state.areSortersVisible))}
                                >
                                    <i className='glyphicon glyphicon-sort' />
                                </button>,
                                <button
                                    key='filters-btn'
                                    disabled={!this.props.screenNodes.length}
                                    onClick={this.toggleFilters}
                                    className={utils.classNames(managementButtonClasses(this.state.areFiltersVisible))}
                                >
                                    <i className='glyphicon glyphicon-filter' />
                                </button>,
                                !this.state.activeSearch && (
                                    <button
                                        key='search-btn'
                                        disabled={!this.props.screenNodes.length}
                                        onClick={this.activateSearch}
                                        className={utils.classNames(managementButtonClasses(false, 'btn-search'))}
                                    >
                                        <i className='glyphicon glyphicon-search' />
                                    </button>
                                ),
                                this.state.activeSearch && (
                                    <div className='search pull-left' key='search'>
                                        <controls.Input
                                            type='text'
                                            name='search'
                                            ref='search'
                                            defaultValue={this.props.search}
                                            placeholder={i18n(ns + 'search_placeholder')}
                                            disabled={!this.props.screenNodes.length}
                                            onChange={this.searchNodes}
                                            autoFocus
                                        />
                                        {this.state.isSearchButtonVisible &&
                                            <button className='close btn-clear-search' onClick={this.clearSearchField}>&times;</button>
                                        }
                                    </div>
                                )
                            ]}
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
                            this.state.areSortersVisible && (
                                <div className='col-xs-12 sorters' key='sorters'>
                                    <div className='well clearfix' key={this.state.sortersKey}>
                                        <div className='well-heading'>
                                            <i className='glyphicon glyphicon-sort' /> {i18n(ns + 'sort_by')}
                                            {!_.isEqual(this.props.activeSorters, this.props.defaultSorting) &&
                                                <button className='btn btn-link pull-right' onClick={this.resetSorters}>
                                                    <i className='glyphicon glyphicon-remove-sign' /> {i18n(ns + 'clear_all')}
                                                </button>
                                            }
                                        </div>
                                        {this.props.activeSorters.map(function(sortObject) {
                                            var sorterName = _.keys(sortObject)[0];
                                            if (!_.contains(this.props.sorters, sorterName)) return null;
                                            var asc = sortObject[sorterName] == 'asc';
                                            return (
                                                <div key={'sort_by-' + sorterName} className='pull-left'>
                                                    <button className='btn btn-default' onClick={_.partial(this.props.changeSortingOrder, sorterName)}>
                                                        {i18n('cluster_page.nodes_tab.sorters.' + sorterName)}
                                                        <i
                                                            className={utils.classNames({
                                                                glyphicon: true,
                                                                'glyphicon-arrow-down': asc,
                                                                'glyphicon-arrow-up': !asc
                                                            })}
                                                        />
                                                    </button>
                                                    {this.renderDeleteSorterButton(sortObject)}
                                                </div>
                                            );
                                        }, this)}
                                        {!!inactiveSorters.length &&
                                            <MultiSelectControl
                                                name='sorter-more'
                                                label={i18n(ns + 'more')}
                                                options={inactiveSorters.map(function(sorterName) {
                                                    return {
                                                        name: sorterName,
                                                        label: i18n('cluster_page.nodes_tab.sorters.' + sorterName)
                                                    };
                                                })}
                                                onChange={this.props.addSorting}
                                                dynamicValues={true}
                                            />
                                        }
                                    </div>
                                </div>
                            ),
                            this.state.areFiltersVisible && (
                                <div className='col-xs-12 filters' key='filters'>
                                    <div className='well clearfix' key={this.state.filtersKey}>
                                        <div className='well-heading'>
                                            <i className='glyphicon glyphicon-filter' /> {i18n(ns + 'filter_by')}
                                            {!_.isEmpty(this.props.activeFilters) &&
                                                <button className='btn btn-link pull-right' onClick={this.resetFilters}>
                                                    <i className='glyphicon glyphicon-remove-sign' /> {i18n(ns + 'clear_all')}
                                                </button>
                                            }
                                        </div>
                                        {_.map(filtersToDisplay, function(values, filterName) {
                                            var options = this.getFilterOptions(filterName),
                                                Control = options ? MultiSelectControl : NumberRangeControl;
                                            return (
                                                <Control
                                                    key={filterName}
                                                    ref={filterName}
                                                    name={filterName}
                                                    label={i18n('cluster_page.nodes_tab.filters.' + filterName)}
                                                    options={options}
                                                    values={values}
                                                    extraContent={this.renderDeleteFilterButton(filterName)}
                                                    onChange={_.partial(this.props.changeFilter, filterName)}
                                                    prefix={i18n('cluster_page.nodes_tab.filters.prefixes.' + filterName, {defaultValue: ''})}
                                                />
                                            );
                                        }, this)}
                                        {!!inactiveFilters.length &&
                                            <MultiSelectControl
                                                name='filter-more'
                                                label={i18n(ns + 'more')}
                                                options={inactiveFilters.map(function(filterName) {
                                                    return {
                                                        name: filterName,
                                                        label: i18n('cluster_page.nodes_tab.filters.' + filterName)
                                                    };
                                                })}
                                                onChange={this.props.addFilter}
                                                dynamicValues={true}
                                            />
                                        }
                                    </div>
                                </div>
                            )
                        ]}
                        {this.props.mode != 'edit' && !!this.props.screenNodes.length &&
                            <div className='col-xs-12'>
                                {(!this.state.areSortersVisible || !this.state.areFiltersVisible && !_.isEmpty(filtersWithChosenValues)) &&
                                    <div className='active-sorters-filters'>
                                        {!this.state.areFiltersVisible && !_.isEmpty(filtersWithChosenValues) &&
                                            <div className='active-filters row' onClick={this.toggleFilters}>
                                                <strong className='col-xs-1'>{i18n(ns + 'filter_by')}</strong>
                                                <div className='col-xs-11'>
                                                    {i18n('cluster_page.nodes_tab.filter_results_amount', {count: this.props.filteredNodesLength})}
                                                    {_.map(this.props.activeFilters, function(values, filterName) {
                                                        if (!values.length) return null;
                                                        var options = this.getFilterOptions(filterName);
                                                        return (
                                                            <div key={filterName}>
                                                                <span>{i18n('cluster_page.nodes_tab.filters.' + filterName)}: </span>
                                                                <strong>
                                                                    {options ?
                                                                        _.map(values, function(value) {
                                                                            return _.find(options, {name: value}).label;
                                                                        }).join(', ')
                                                                    :
                                                                        !_.isUndefined(values[0]) && !_.isUndefined(values[1]) ?
                                                                            _.uniq(values).join(' - ')
                                                                        :
                                                                            !_.isUndefined(values[0]) ? i18n(ns + 'more_than') + values[0] : i18n(ns + 'less_than') + values[1]
                                                                    }
                                                                </strong>
                                                            </div>
                                                        );
                                                    }, this)}
                                                </div>
                                                <button className='btn btn-link' onClick={this.resetFilters}>
                                                    <i className='glyphicon glyphicon-remove-sign' />
                                                </button>
                                            </div>
                                        }
                                        {!this.state.areSortersVisible &&
                                            <div className='active-sorters row' onClick={this.toggleSorters}>
                                                <strong className='col-xs-1'>{i18n(ns + 'sort_by')}</strong>
                                                <div className='col-xs-11'>
                                                    {_.map(this.props.activeSorters, function(sortObject, index) {
                                                        var sorterName = _.keys(sortObject)[0];
                                                        var asc = sortObject[sorterName] == 'asc';
                                                        if (!_.contains(this.props.sorters, sorterName)) return null;
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
                                                                {!!this.props.activeSorters[index + 1] && ' + '}
                                                            </span>
                                                        );
                                                    }, this)}
                                                </div>
                                                {!_.isEqual(this.props.activeSorters, this.props.defaultSorting) &&
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
            var roles = this.props.cluster.get('roles');
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
                roles = this.props.cluster.get('roles'),
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
                    {this.props.cluster.get('roles').map(function(role) {
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
            var roles = this.props.cluster.get('roles');
            var uniqValueSorters = ['name', 'mac', 'ip'],
                activeSorters = _.uniq(_.flatten(_.map(this.props.activeSorters, _.keys)));

            var groupingMethod = _.bind(function(node) {
                return (_.map(_.difference(activeSorters, uniqValueSorters), function(sorter) {
                    if (sorter == 'roles') {
                        return node.getRolesSummary(roles);
                    }
                    if (sorter == 'status') {
                        return i18n('cluster_page.nodes_tab.node.status.' + node.getStatusSummary(), {
                            os: this.props.cluster.get('release').get('operating_system') || 'OS'
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
                    return i18n('node_details.' + (sorter == 'interfaces' ? 'interfaces_amount' : sorter), {count: node.resource(sorter)});
                }, this)).join('; ');
            }, this);
            var groups = _.pairs(_.groupBy(this.props.nodes, groupingMethod));

            // sort grouped nodes by name, mac or ip
            if (_.intersection(activeSorters, uniqValueSorters).length) {
                var formattedSorters = _.compact(_.map(this.props.activeSorters, function(sorter) {
                    var sorterName = _.keys(sorter)[0];
                    if (_.contains(uniqValueSorters, sorterName)) {
                        return {attr: sorterName, desc: sorter[sorterName] == 'desc'};
                    }
                }));
                _.each(groups, function(group) {
                    group[1].sort(function(node1, node2) {
                        return utils.multiSort(node1, node2, formattedSorters);
                    });
                });
            }

            // sort grouped nodes by other applied sorters
            var preferredRolesOrder = roles.pluck('name');
            return groups.sort(_.bind(function(group1, group2) {
                var result;
                _.each(this.props.activeSorters, function(sorter) {
                    var node1 = group1[1][0], node2 = group2[1][0];
                    var sorterName = _.keys(sorter)[0];
                    switch (sorterName) {
                        case 'roles':
                            var roles1 = node1.sortedRoles(preferredRolesOrder),
                                roles2 = node2.sortedRoles(preferredRolesOrder),
                                order;
                            while (!order && roles1.length && roles2.length) {
                                order = _.indexOf(preferredRolesOrder, roles1.shift()) - _.indexOf(preferredRolesOrder, roles2.shift());
                            }
                            result = order || roles1.length - roles2.length;
                            break;
                        case 'status':
                            result = _.indexOf(this.props.statusesToFilter, node1.getStatusSummary()) - _.indexOf(this.props.statusesToFilter, node2.getStatusSummary());
                            break;
                        case 'manufacturer':
                            result = utils.natsort(node1.get('manufacturer'), node2.get('manufacturer'));
                            break;
                        case 'disks':
                            result = utils.natsort(node1.resource('disks'), node2.resource('disks'));
                            break;
                        default:
                            result = node1.resource(sorterName) - node2.resource(sorterName);
                            break;
                    }
                    if (sorter[sorterName] == 'desc') {
                        result = result * -1;
                    }
                    return !_.isUndefined(result) && !result;
                }, this);
                return result;
            }, this));
        },
        render: function() {
            var groups = this.groupNodes(),
                rolesWithLimitReached = _.keys(_.omit(this.props.processedRoleLimits, function(roleLimit, roleName) {
                    return roleLimit.valid || !_.contains(this.props.selectedRoles, roleName);
                }, this));
            return (
                <div className={utils.classNames({'node-list row': true, compact: this.props.viewMode == 'compact'})}>
                    {groups.length > 1 &&
                        <div className='col-xs-12 node-list-header'>
                            {this.renderSelectAllCheckbox()}
                        </div>
                    }
                    <div className='col-xs-12 content-elements'>
                        {groups.map(function(group) {
                            return <NodeGroup {...this.props}
                                key={group[0]}
                                label={group[0]}
                                nodes={group[1]}
                                rolesWithLimitReached={rolesWithLimitReached}
                            />;
                        }, this)}
                        {this.props.totalNodesLength ?
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
                    <div className='row'>
                        {this.props.nodes.map(function(node) {
                            return <Node
                                {... _.pick(this.props, 'cluster', 'mode', 'viewMode')}
                                key={node.id}
                                node={node}
                                checked={this.props.mode == 'edit' || this.props.selectedNodeIds[node.id]}
                                locked={this.props.locked || _.contains(nodesWithRestrictionsIds, node.id)}
                                onNodeSelection={_.bind(this.props.selectNodes, this.props, [node.id])}
                            />;
                        }, this)}
                    </div>
                </div>
            );
        }
    });

    return NodeListScreen;
});
