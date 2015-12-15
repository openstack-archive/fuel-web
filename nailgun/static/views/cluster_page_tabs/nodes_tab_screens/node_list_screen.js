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
    'views/controls',
    'views/dialogs',
    'component_mixins',
    'views/cluster_page_tabs/nodes_tab_screens/node'
],
function($, _, i18n, Backbone, React, utils, models, dispatcher, controls, dialogs, componentMixins, Node) {
    'use strict';
    var NodeListScreen, MultiSelectControl, NumberRangeControl, ManagementPanel, NodeLabelsPanel, RolePanel, SelectAllMixin, NodeList, NodeGroup;

    class Sorter {
        constructor(name, order, isLabel) {
            this.name = name;
            this.order = order;
            this.title = isLabel ? name : i18n('cluster_page.nodes_tab.sorters.' + name, {defaultValue: name});
            this.isLabel = isLabel;
            return this;
        }

        static fromObject(sorterObject, isLabel) {
            var sorterName = _.keys(sorterObject)[0];
            return new Sorter(sorterName, sorterObject[sorterName], isLabel);
        }

        static toObject(sorter) {
            return {[sorter.name]: sorter.order};
        }
    }

    class Filter {
        constructor(name, values, isLabel) {
            this.name = name;
            this.values = values;
            this.title = isLabel ? name : i18n('cluster_page.nodes_tab.filters.' + name, {defaultValue: name});
            this.isLabel = isLabel;
            this.isNumberRange = !isLabel && !_.contains(['roles', 'status', 'manufacturer', 'group_id', 'cluster'], name);
            return this;
        }

        static fromObject(filters, isLabel) {
            return _.map(filters, (values, name) => new Filter(name, values, isLabel));
        }

        static toObject(filters) {
            return _.reduce(filters, (result, filter) => {
                result[filter.name] = filter.values;
                return result;
            }, {});
        }

        updateLimits(nodes, updateValues) {
            if (this.isNumberRange) {
                var limits = [0, 0];
                if (nodes.length) {
                    var resources = nodes.invoke('resource', this.name);
                    limits = [_.min(resources), _.max(resources)];
                    if (this.name == 'hdd' || this.name == 'ram') {
                        limits = [Math.floor(limits[0] / Math.pow(1024, 3)), Math.ceil(limits[1] / Math.pow(1024, 3))];
                    }
                }
                this.limits = limits;
                if (updateValues) this.values = _.clone(limits);
            }
        }
    }

    NodeListScreen = React.createClass({
        mixins: [
            componentMixins.pollingMixin(20, true),
            componentMixins.backboneMixin('cluster', 'change:status'),
            componentMixins.backboneMixin('nodes', 'update change'),
            componentMixins.backboneMixin({
                modelOrCollection: function(props) {return props.cluster && props.cluster.get('tasks');},
                renderOn: 'update change:status'
            }),
            componentMixins.dispatcherMixin('labelsConfigurationUpdated', 'normalizeAppliedFilters')
        ],
        getDefaultProps: function() {
            return {
                sorters: [],
                filters: []
            };
        },
        getInitialState: function() {
            var cluster = this.props.cluster,
                nodes = this.props.nodes,
                uiSettings = (cluster || this.props.fuelSettings).get('ui_settings');

            var availableFilters = this.props.filters.map((name) => {
                    var filter = new Filter(name, [], false);
                    filter.updateLimits(nodes, true);
                    return filter;
                }),
                activeFilters = cluster && this.props.mode == 'add' ?
                    Filter.fromObject(this.props.defaultFilters, false)
                :
                    _.union(
                        Filter.fromObject(_.extend({}, this.props.defaultFilters, uiSettings.filter), false),
                        Filter.fromObject(uiSettings.filter_by_labels, true)
                    );
            _.invoke(activeFilters, 'updateLimits', nodes, false);

            var availableSorters = this.props.sorters.map((name) => new Sorter(name, 'asc', false)),
                activeSorters = cluster && this.props.mode == 'add' ?
                    _.map(this.props.defaultSorting, _.partial(Sorter.fromObject, _, false))
                :
                    _.union(
                        _.map(uiSettings.sort, _.partial(Sorter.fromObject, _, false)),
                        _.map(uiSettings.sort_by_labels, _.partial(Sorter.fromObject, _, true))
                    );

            var search = cluster && this.props.mode == 'add' ? '' : uiSettings.search,
                viewMode = uiSettings.view_mode,
                isLabelsPanelOpen = false;

            var states = {search, activeSorters, activeFilters, availableSorters, availableFilters, viewMode, isLabelsPanelOpen};

            // Equipment page
            if (!cluster) return states;

            // additonal Nodes tab states (Cluster page)
            var roles = cluster.get('roles').pluck('name'),
                selectedRoles = nodes.length ? _.filter(roles, (role) => !nodes.any((node) => !node.hasRole(role))) : [],
                indeterminateRoles = nodes.length ? _.filter(roles, (role) => !_.contains(selectedRoles, role) && nodes.any((node) => node.hasRole(role))) : [];

            var configModels = {
                    cluster: cluster,
                    settings: cluster.get('settings'),
                    version: app.version,
                    default: cluster.get('settings')
                };

            return _.extend(states, {selectedRoles, indeterminateRoles, configModels});
        },
        selectNodes: function(ids, name, checked) {
            this.props.selectNodes(ids, checked);
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
        calculateFilterLimits: function() {
            _.invoke(this.state.availableFilters, 'updateLimits', this.props.nodes, true);
            _.invoke(this.state.activeFilters, 'updateLimits', this.props.nodes, false);
        },
        normalizeAppliedFilters: function(checkStandardNodeFilters = false) {
            if (!this.props.cluster || this.props.mode != 'add') {
                var normalizedFilters = _.map(this.state.activeFilters, (activeFilter) => {
                    var filter = _.clone(activeFilter);
                    if (filter.values.length) {
                        if (filter.isLabel) {
                            filter.values = _.intersection(filter.values, this.props.nodes.getLabelValues(filter.name));
                        } else if (checkStandardNodeFilters && _.contains(['manufacturer', 'group_id', 'cluster'], filter.name)) {
                            filter.values = _.filter(filter.values, (value) => {
                                return this.props.nodes.any((node) => node.get(filter.name) == value);
                            }, this);
                        }
                    }
                    return filter;
                }, this);
                if (!_.isEqual(_.pluck(normalizedFilters, 'values'), _.pluck(this.state.activeFilters, 'values'))) {
                    this.updateFilters(normalizedFilters);
                }
            }
        },
        componentWillMount: function() {
            this.updateInitialRoles();
            this.props.nodes.on('update reset', this.updateInitialRoles, this);
            this.props.nodes.on('update reset', this.calculateFilterLimits, this);
            this.normalizeAppliedFilters(true);

            this.changeSearch = _.debounce(this.changeSearch, 200, {leading: true});

            if (this.props.mode != 'list') {
                // hack to prevent node roles update after node polling
                this.props.nodes.on('change:pending_roles', this.checkRoleAssignment, this);
            }
        },
        componentWillUnmount: function() {
            this.props.nodes.off('update reset', this.updateInitialRoles, this);
            this.props.nodes.off('update reset', this.calculateFilterLimits, this);
            this.props.nodes.off('change:pending_roles', this.checkRoleAssignment, this);
        },
        processRoleLimits: function() {
            var cluster = this.props.cluster,
                maxNumberOfNodes = [],
                processedRoleLimits = {};

            var selectedNodes = this.props.nodes.filter((node) => this.props.selectedNodeIds[node.id]),
                clusterNodes = this.props.cluster.get('nodes').filter((node) => !_.contains(this.props.selectedNodeIds, node.id)),
                nodesForLimitCheck = new models.Nodes(_.union(selectedNodes, clusterNodes));

            cluster.get('roles').each(function(role) {
                if ((role.get('limits') || {}).max) {
                    var roleName = role.get('name'),
                        isRoleAlreadyAssigned = nodesForLimitCheck.any((node) => node.hasRole(roleName));
                    processedRoleLimits[roleName] = role.checkLimits(this.state.configModels, nodesForLimitCheck, !isRoleAlreadyAssigned, ['max']);
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
                maxNumberOfNodes: maxNumberOfNodes.length ? _.min(maxNumberOfNodes) - _.size(this.props.selectedNodeIds) : null
            };
        },
        updateInitialRoles: function() {
            this.initialRoles = _.zipObject(this.props.nodes.pluck('id'), this.props.nodes.pluck('pending_roles'));
        },
        checkRoleAssignment: function(node, roles, options) {
            if (!options.assign) node.set({pending_roles: node.previous('pending_roles')}, {assign: true});
        },
        hasChanges: function() {
            return this.props.mode != 'list' && this.props.nodes.any(function(node) {
                return !_.isEqual(node.get('pending_roles'), this.initialRoles[node.id]);
            }, this);
        },
        changeSearch: function(value) {
            this.updateSearch(_.trim(value));
        },
        clearSearchField: function() {
            this.changeSearch.cancel();
            this.updateSearch('');
        },
        updateSearch: function(value) {
            this.setState({search: value});
            if (!this.props.cluster || this.props.mode != 'add') {
                this.changeUISettings({search: value});
            }
        },
        addSorting: function(sorter) {
            this.updateSorting(this.state.activeSorters.concat(sorter));
        },
        removeSorting: function(sorter) {
            this.updateSorting(_.difference(this.state.activeSorters, [sorter]));
        },
        resetSorters: function() {
            this.updateSorting(_.map(this.props.defaultSorting, _.partial(Sorter.fromObject, _, false)));
        },
        changeSortingOrder: function(sorterToChange) {
            this.updateSorting(this.state.activeSorters.map(function(sorter) {
                if (sorter.name == sorterToChange.name && sorter.isLabel == sorterToChange.isLabel) {
                    return new Sorter(sorter.name, sorter.order == 'asc' ? 'desc' : 'asc', sorter.isLabel);
                }
                return sorter;
            }));
        },
        updateSorting: function(sorters) {
            this.setState({activeSorters: sorters});
            if (!this.props.cluster || this.props.mode != 'add') {
                var groupedSorters = _.groupBy(sorters, 'isLabel');
                this.changeUISettings({
                    sort: _.map(groupedSorters.false, Sorter.toObject),
                    sort_by_labels: _.map(groupedSorters.true, Sorter.toObject)
                });
            }
        },
        updateFilters: function(filters) {
            this.setState({activeFilters: filters});
            if (!this.props.cluster || this.props.mode != 'add') {
                var groupedFilters = _.groupBy(filters, 'isLabel');
                this.changeUISettings({
                    filter: Filter.toObject(groupedFilters.false),
                    filter_by_labels: Filter.toObject(groupedFilters.true)
                });
            }
        },
        getFilterOptions: function(filter) {
            if (filter.isLabel) {
                var values = _.uniq(this.props.nodes.getLabelValues(filter.name)),
                    ns = 'cluster_page.nodes_tab.node_management_panel.';
                return values.map((value) => {
                    return {
                        name: value,
                        label: _.isNull(value) ? i18n(ns + 'label_value_not_specified') : value === false ? i18n(ns + 'label_not_assigned') : value
                    };
                });
            }

            var options;
            switch (filter.name) {
                case 'status':
                    var os = this.props.cluster && this.props.cluster.get('release').get('operating_system') || 'OS';
                    options = this.props.statusesToFilter.map(function(status) {
                        return {
                            name: status,
                            label: i18n('cluster_page.nodes_tab.node.status.' + status, {os: os})
                        };
                    });
                    break;
                case 'manufacturer':
                    options = _.uniq(this.props.nodes.pluck('manufacturer')).map(function(manufacturer) {
                        manufacturer = manufacturer || '';
                        return {
                            name: manufacturer.replace(/\s/g, '_'),
                            label: manufacturer
                        };
                    });
                    break;
                case 'roles':
                    options = this.props.roles.invoke('pick', 'name', 'label');
                    break;
                case 'group_id':
                    options = _.uniq(this.props.nodes.pluck('group_id')).map(function(groupId) {
                        var nodeNetworkGroup = this.props.nodeNetworkGroups.get(groupId);
                        return {
                            name: groupId,
                            label: nodeNetworkGroup ?
                                    nodeNetworkGroup.get('name') + (this.props.cluster ? '' : ' (' + this.props.clusters.get(nodeNetworkGroup.get('cluster_id')).get('name') + ')')
                                :
                                    i18n('common.not_specified')
                        };
                    }, this);
                    break;
                case 'cluster':
                    options = _.uniq(this.props.nodes.pluck('cluster')).map(function(clusterId) {
                        return {
                            name: clusterId,
                            label: clusterId ? this.props.clusters.get(clusterId).get('name') : i18n('cluster_page.nodes_tab.node.unallocated')
                        };
                    }, this);
                    break;
            }

            // sort option list
            options.sort(_.bind(function(option1, option2) {
                // sort Node Network Group filter options by node network group id
                if (this.props.name == 'group_id') return option1.name - option2.name;
                return utils.natsort(option1.label, option2.label, {insensitive: true});
            }, this));

            return options;
        },
        addFilter: function(filter) {
            this.updateFilters(this.state.activeFilters.concat(filter));
        },
        changeFilter: function(filterToChange, values) {
            this.updateFilters(this.state.activeFilters.map(function(filter) {
                if (filter.name == filterToChange.name && filter.isLabel == filterToChange.isLabel) {
                    var changedFilter = new Filter(filter.name, values, filter.isLabel);
                    changedFilter.limits = filter.limits;
                    return changedFilter;
                }
                return filter;
            }));
        },
        removeFilter: function(filter) {
            this.updateFilters(_.difference(this.state.activeFilters, [filter]));
        },
        resetFilters: function() {
            this.updateFilters(Filter.fromObject(this.props.defaultFilters, false));
        },
        changeViewMode: function(name, value) {
            this.setState({viewMode: value});
            if (!this.props.cluster || this.props.mode != 'add') {
                this.changeUISettings({view_mode: value});
            }
        },
        changeUISettings: function(newSettings) {
            var uiSettings = (this.props.cluster || this.props.fuelSettings).get('ui_settings'),
                options = {patch: true, wait: true, validate: false};
            _.extend(uiSettings, newSettings);
            if (this.props.cluster) {
                this.props.cluster.save({ui_settings: uiSettings}, options);
            } else {
                this.props.fuelSettings.save(null, options);
            }
        },
        revertChanges: function() {
            this.props.nodes.each(function(node) {
                node.set({pending_roles: this.initialRoles[node.id]}, {silent: true});
            }, this);
        },
        toggleLabelsPanel: function(value) {
            this.setState({
                isLabelsPanelOpen: _.isUndefined(value) ? !this.state.isLabelsPanelOpen : value
            });
        },
        getNodeLabels: function() {
            return _.chain(this.props.nodes.pluck('labels')).flatten().map(_.keys).flatten().uniq().value();
        },
        render: function() {
            var cluster = this.props.cluster,
                locked = !!cluster && !!cluster.task({group: 'deployment', active: true}),
                nodes = this.props.nodes,
                processedRoleData = cluster ? this.processRoleLimits() : {};

            // labels to manage in labels panel
            var selectedNodes = new models.Nodes(this.props.nodes.filter(function(node) {
                    return this.props.selectedNodeIds[node.id];
                }, this)),
                selectedNodeLabels = _.chain(selectedNodes.pluck('labels')).flatten().map(_.keys).flatten().uniq().value();

            // filter nodes
            var filteredNodes = nodes.filter(function(node) {
                // search field
                if (this.state.search) {
                    var search = this.state.search.toLowerCase();
                    if (!_.any(node.pick('name', 'mac', 'ip'), function(attribute) {
                        return _.contains((attribute || '').toLowerCase(), search);
                    })) {
                        return false;
                    }
                }

                // filters
                return _.all(this.state.activeFilters, function(filter) {
                    if (!filter.values.length) return true;

                    if (filter.isLabel) {
                        return _.contains(filter.values, node.getLabel(filter.name));
                    }

                    var result;
                    switch (filter.name) {
                        case 'roles':
                            result = _.any(filter.values, function(role) {return node.hasRole(role);});
                            break;
                        case 'status':
                            result = _.contains(filter.values, node.getStatusSummary());
                            break;
                        case 'manufacturer':
                        case 'cluster':
                        case 'group_id':
                            result = _.contains(filter.values, node.get(filter.name));
                            break;
                        default:
                            // handle number ranges
                            var currentValue = node.resource(filter.name);
                            if (filter.name == 'hdd' || filter.name == 'ram') currentValue = currentValue / Math.pow(1024, 3);
                            result = currentValue >= filter.values[0] && (_.isUndefined(filter.values[1]) || currentValue <= filter.values[1]);
                            break;
                    }
                    return result;
                }, this);
            }, this);

            var screenNodesLabels = this.getNodeLabels();
            return (
                <div>
                    {this.props.mode == 'edit' &&
                        <div className='alert alert-warning'>
                            {i18n('cluster_page.nodes_tab.disk_configuration_reset_warning')}
                        </div>
                    }
                    <ManagementPanel
                        {... _.pick(this.state, 'viewMode', 'search', 'activeSorters', 'activeFilters', 'availableSorters', 'availableFilters', 'isLabelsPanelOpen')}
                        {... _.pick(this.props, 'cluster', 'mode', 'defaultSorting', 'statusesToFilter', 'defaultFilters')}
                        {... _.pick(this, 'addSorting', 'removeSorting', 'resetSorters', 'changeSortingOrder')}
                        {... _.pick(this, 'addFilter', 'changeFilter', 'removeFilter', 'resetFilters', 'getFilterOptions')}
                        {... _.pick(this, 'toggleLabelsPanel')}
                        {... _.pick(this, 'changeSearch', 'clearSearchField')}
                        {... _.pick(this, 'changeViewMode')}
                        labelSorters={screenNodesLabels.map(function(name) {return new Sorter(name, 'asc', true);})}
                        labelFilters={screenNodesLabels.map(function(name) {return new Filter(name, [], true);})}
                        nodes={selectedNodes}
                        screenNodes={nodes}
                        filteredNodes={filteredNodes}
                        selectedNodeLabels={selectedNodeLabels}
                        hasChanges={this.hasChanges()}
                        locked={locked}
                        revertChanges={this.revertChanges}
                        selectNodes={this.selectNodes}
                    />
                    {!!this.props.cluster && this.props.mode != 'list' &&
                        <RolePanel
                            {... _.pick(this.state, 'selectedRoles', 'indeterminateRoles', 'configModels')}
                            {... _.pick(this.props, 'cluster', 'mode', 'nodes', 'selectedNodeIds')}
                            {... _.pick(processedRoleData, 'processedRoleLimits')}
                            selectRoles={this.selectRoles}
                        />
                    }
                    <NodeList
                        {... _.pick(this.state, 'viewMode', 'activeSorters', 'selectedRoles')}
                        {... _.pick(this.props, 'cluster', 'mode', 'statusesToFilter', 'selectedNodeIds', 'clusters', 'roles', 'nodeNetworkGroups')}
                        {... _.pick(processedRoleData, 'maxNumberOfNodes', 'processedRoleLimits')}
                        nodes={filteredNodes}
                        totalNodesLength={nodes.length}
                        locked={this.state.isLabelsPanelOpen}
                        selectNodes={this.selectNodes}
                    />
                </div>
            );
        }
    });

    MultiSelectControl = React.createClass({
        propTypes: {
            name: React.PropTypes.oneOfType([React.PropTypes.string, React.PropTypes.bool]),
            options: React.PropTypes.arrayOf(React.PropTypes.object).isRequired,
            values: React.PropTypes.arrayOf(React.PropTypes.oneOfType([React.PropTypes.string, React.PropTypes.bool])),
            label: React.PropTypes.node.isRequired,
            dynamicValues: React.PropTypes.bool,
            onChange: React.PropTypes.func,
            extraContent: React.PropTypes.node,
            toggle: React.PropTypes.func.isRequired,
            isOpen: React.PropTypes.bool.isRequired
        },
        getDefaultProps: function() {
            return {
                values: [],
                isOpen: false
            };
        },
        onChange: function(name, checked, isLabel) {
            if (!this.props.dynamicValues) {
                var values = name == 'all' ?
                        checked ? _.pluck(this.props.options, 'name') : []
                    :
                        checked ? _.union(this.props.values, [name]) : _.difference(this.props.values, [name]);
                this.props.onChange(values);
            } else {
                this.props.onChange(_.find(this.props.options, {name: name, isLabel: isLabel}));
            }
        },
        closeOnEscapeKey: function(e) {
            if (e.key == 'Escape') this.props.toggle(false);
        },
        render: function() {
            if (!this.props.options.length) return null;

            var valuesAmount = this.props.values.length;
            var label = this.props.label;
            if (!this.props.dynamicValues && valuesAmount) {
                label = this.props.label + ': ' + (valuesAmount > 3 ?
                        i18n('cluster_page.nodes_tab.node_management_panel.selected_options', {label: this.props.label, count: valuesAmount})
                    :
                        _.map(this.props.values, function(itemName) {
                        return _.find(this.props.options, {name: itemName}).label;
                    }, this).join(', '));
            }

            var attributes, labels;
            if (this.props.dynamicValues) {
                var groupedOptions = _.groupBy(this.props.options, 'isLabel');
                attributes = groupedOptions.false || [];
                labels = groupedOptions.true || [];
            }

            var optionProps = _.bind(function(option) {
                return {
                    key: option.name,
                    type: 'checkbox',
                    name: option.name,
                    label: option.title
                };
            }, this);

            var classNames = {
                'btn-group multiselect': true,
                open: this.props.isOpen,
                'more-control': this.props.dynamicValues
            };
            if (this.props.className) classNames[this.props.className] = true;

            return (
                <div className={utils.classNames(classNames)} tabIndex='-1' onKeyDown={this.closeOnEscapeKey}>
                    <button
                        className={'btn dropdown-toggle ' + ((this.props.dynamicValues && !this.props.isOpen) ? 'btn-link' : 'btn-default')}
                        onClick={this.props.toggle}
                    >
                        {label} <span className='caret'></span>
                    </button>
                    {this.props.isOpen &&
                        <controls.Popover toggle={this.props.toggle}>
                            {!this.props.dynamicValues ?
                                <div>
                                    <div key='all'>
                                        <controls.Input
                                            type='checkbox'
                                            label={i18n('cluster_page.nodes_tab.node_management_panel.select_all')}
                                            name='all'
                                            checked={valuesAmount == this.props.options.length}
                                            onChange={this.onChange}
                                        />
                                    </div>
                                    <div key='divider' className='divider' />
                                    {_.map(this.props.options, function(option) {
                                        return <controls.Input {...optionProps(option)}
                                            label={option.label}
                                            checked={_.contains(this.props.values, option.name)}
                                            onChange={this.onChange}
                                        />;
                                    }, this)}
                                </div>
                            :
                                <div>
                                    {_.map(attributes, function(option) {
                                        return <controls.Input {...optionProps(option)}
                                            checked={_.contains(this.props.values, option.name)}
                                            onChange={_.partialRight(this.onChange, false)}
                                        />;
                                    }, this)}
                                    {!!attributes.length && !!labels.length && <div key='divider' className='divider' />}
                                    {_.map(labels, function(option) {
                                        return <controls.Input {...optionProps(option)}
                                            key={'label-' + option.name}
                                            onChange={_.partialRight(this.onChange, true)}
                                        />;
                                    }, this)}
                                </div>
                            }
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
            prefix: React.PropTypes.string,
            min: React.PropTypes.number,
            max: React.PropTypes.number,
            toggle: React.PropTypes.func.isRequired,
            isOpen: React.PropTypes.bool.isRequired
        },
        getDefaultProps: function() {
            return {
                values: [],
                isOpen: false,
                min: 0,
                max: 0
            };
        },
        changeValue: function(name, value, index) {
            var values = this.props.values;
            values[index] = _.max([Number(value), 0]);
            this.props.onChange(values);
        },
        closeOnEscapeKey: function(e) {
            if (e.key == 'Escape') this.props.toggle(this.props.name, false);
        },
        render: function() {
            var classNames = {'btn-group number-range': true, open: this.props.isOpen};
            if (this.props.className) classNames[this.props.className] = true;
            var props = {
                    type: 'number',
                    inputClassName: 'pull-left',
                    min: this.props.min,
                    max: this.props.max,
                    error: this.props.values[0] > this.props.values[1] || null
                };

            return (
                <div className={utils.classNames(classNames)} tabIndex='-1' onKeyDown={this.closeOnEscapeKey}>
                    <button className='btn btn-default dropdown-toggle' onClick={this.props.toggle}>
                        {this.props.label + ': ' + _.uniq(this.props.values).join(' - ')} <span className='caret'></span>
                    </button>
                    {this.props.isOpen &&
                        <controls.Popover toggle={this.props.toggle}>
                            <div className='clearfix'>
                                <controls.Input {...props}
                                    name='start'
                                    value={this.props.values[0]}
                                    onChange={_.partialRight(this.changeValue, 0)}
                                    autoFocus
                                />
                                <span className='pull-left'> &mdash; </span>
                                <controls.Input {...props}
                                    name='end'
                                    value={this.props.values[1]}
                                    onChange={_.partialRight(this.changeValue, 1)}
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
        mixins: [componentMixins.unsavedChangesMixin],
        getInitialState: function() {
            return {
                actionInProgress: false,
                isSearchButtonVisible: !!this.props.search,
                activeSearch: !!this.props.search,
                openFilter: null,
                isMoreFilterControlVisible: false,
                isMoreSorterControlVisible: false
            };
        },
        changeScreen: function(url, passNodeIds) {
            url = url ? '/' + url : '';
            if (passNodeIds) url += '/' + utils.serializeTabOptions({nodes: this.props.nodes.pluck('id')});
            app.navigate('#cluster/' + this.props.cluster.id + '/nodes' + url, {trigger: true});
        },
        goToConfigurationScreen: function(action, conflict) {
            if (conflict) {
                var ns = 'cluster_page.nodes_tab.node_management_panel.node_management_error.';
                utils.showErrorDialog({
                    title: i18n(ns + 'title'),
                    message: <div><i className='glyphicon glyphicon-danger-sign' /> {i18n(ns + action + '_configuration_warning')}</div>
                });
                return;
            }
            this.changeScreen(action, true);
        },
        showDeleteNodesDialog: function() {
            dialogs.DeleteNodesDialog.show({nodes: this.props.nodes, cluster: this.props.cluster})
                .done(_.partial(this.props.selectNodes, _.pluck(this.props.nodes.where({status: 'ready'}), 'id'), null, true));
        },
        hasChanges: function() {
            return this.props.hasChanges;
        },
        isSavingPossible: function() {
            return !this.state.actionInProgress && this.hasChanges();
        },
        revertChanges: function() {
            return this.props.revertChanges();
        },
        applyChanges: function() {
            if (!this.isSavingPossible()) return $.Deferred().reject();

            this.setState({actionInProgress: true});
            var nodes = new models.Nodes(this.props.nodes.map(function(node) {
                var data = {id: node.id, pending_roles: node.get('pending_roles')};
                if (node.get('pending_roles').length) {
                    if (this.props.mode == 'add') return _.extend(data, {cluster_id: this.props.cluster.id, pending_addition: true});
                } else if (node.get('pending_addition')) {
                    return _.extend(data, {cluster_id: null, pending_addition: false});
                }
                return data;
            }, this));
            return Backbone.sync('update', nodes)
                .done(_.bind(function() {
                    $.when(this.props.cluster.fetch(), this.props.cluster.fetchRelated('nodes')).always(_.bind(function() {
                        if (this.props.mode == 'add') {
                            dispatcher.trigger('updateNodeStats networkConfigurationUpdated labelsConfigurationUpdated');
                            this.props.selectNodes();
                        }
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
        applyAndRedirect: function() {
            this.applyChanges().done(this.changeScreen);
        },
        searchNodes: function(name, value) {
            this.setState({isSearchButtonVisible: !!value});
            this.props.changeSearch(value);
        },
        clearSearchField: function() {
            this.setState({isSearchButtonVisible: false});
            this.refs.search.getInputDOMNode().value = '';
            this.refs.search.getInputDOMNode().focus();
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
        onSearchKeyDown: function(e) {
            if (e.key == 'Escape') {
                this.clearSearchField();
                this.setState({activeSearch: false});
            }
        },
        componentWillUnmount: function() {
            $('html').off('click.search');
        },
        removeSorting: function(sorter) {
            this.props.removeSorting(sorter);
            this.setState({
                sortersKey: _.now(),
                isMoreSorterControlVisible: false
            });
        },
        resetSorters: function(e) {
            e.stopPropagation();
            this.props.resetSorters();
            this.setState({
                sortersKey: _.now(),
                isMoreSorterControlVisible: false
            });
        },
        toggleFilter: function(filter, visible) {
            var isFilterOpen = this.isFilterOpen(filter);
            visible = _.isBoolean(visible) ? visible : !isFilterOpen;
            this.setState({
                openFilter: visible ? filter : isFilterOpen ? null : this.state.openFilter
            });
        },
        toggleMoreFilterControl: function(visible) {
            this.setState({
                isMoreFilterControlVisible: _.isBoolean(visible) ? visible : !this.state.isMoreFilterControlVisible,
                openFilter: null
            });
        },
        toggleMoreSorterControl: function(visible) {
            this.setState({
                isMoreSorterControlVisible: _.isBoolean(visible) ? visible : !this.state.isMoreSorterControlVisible
            });
        },
        isFilterOpen: function(filter) {
            return !_.isNull(this.state.openFilter) && this.state.openFilter.name == filter.name && this.state.openFilter.isLabel == filter.isLabel;
        },
        addFilter: function(filter) {
            this.props.addFilter(filter);
            this.toggleMoreFilterControl();
            this.toggleFilter(filter, true);
        },
        removeFilter: function(filter) {
            this.props.removeFilter(filter);
            this.setState({filtersKey: _.now()});
            this.toggleFilter(filter, false);
        },
        resetFilters: function(e) {
            e.stopPropagation();
            this.props.resetFilters();
            this.setState({
                filtersKey: _.now(),
                openFilter: null
            });
        },
        toggleSorters: function() {
            this.setState({
                newLabels: [],
                areSortersVisible: !this.state.areSortersVisible,
                isMoreSorterControlVisible: false,
                areFiltersVisible: false
            });
            this.props.toggleLabelsPanel(false);
        },
        toggleFilters: function() {
            this.setState({
                newLabels: [],
                areFiltersVisible: !this.state.areFiltersVisible,
                openFilter: null,
                areSortersVisible: false
            });
            this.props.toggleLabelsPanel(false);
        },
        renderDeleteFilterButton: function(filter) {
            if (!filter.isLabel && _.contains(_.keys(this.props.defaultFilters), filter.name)) return null;
            return (
                <i className='btn btn-link glyphicon glyphicon-minus-sign btn-remove-filter' onClick={_.partial(this.removeFilter, filter)} />
            );
        },
        toggleLabelsPanel: function() {
            this.setState({
                newLabels: [],
                areFiltersVisible: false,
                areSortersVisible: false
            });
            this.props.toggleLabelsPanel();
        },
        renderDeleteSorterButton: function(sorter) {
            return (
                <i className='btn btn-link glyphicon glyphicon-minus-sign btn-remove-sorting' onClick={_.partial(this.removeSorting, sorter)} />
            );
        },
        render: function() {
            var ns = 'cluster_page.nodes_tab.node_management_panel.';

            var disksConflict, interfaceConflict;
            if (this.props.mode == 'list' && this.props.nodes.length) {
                disksConflict = !this.props.nodes.areDisksConfigurable();
                interfaceConflict = !this.props.nodes.areInterfacesConfigurable();
            }

            var managementButtonClasses = _.bind(function(isActive, className) {
                var classes = {
                    'btn btn-default pull-left': true,
                    active: isActive
                };
                classes[className] = true;
                return classes;
            }, this);

            var inactiveSorters, canResetSorters;
            var inactiveFilters, appliedFilters;
            if (this.props.mode != 'edit') {
                var checkSorter = _.bind(function(sorter, isLabel) {
                    return !_.any(this.props.activeSorters, {name: sorter.name, isLabel: isLabel});
                }, this);
                inactiveSorters = _.union(_.filter(this.props.availableSorters, _.partial(checkSorter, _, false)), _.filter(this.props.labelSorters, _.partial(checkSorter, _, true)))
                    .sort(function(sorter1, sorter2) {
                        return utils.natsort(sorter1.title, sorter2.title, {insensitive: true});
                    });
                canResetSorters = _.any(this.props.activeSorters, {isLabel: true}) || !_(this.props.activeSorters).where({isLabel: false}).map(Sorter.toObject).isEqual(this.props.defaultSorting);

                var checkFilter = _.bind(function(filter, isLabel) {
                    return !_.any(this.props.activeFilters, {name: filter.name, isLabel: isLabel});
                }, this);
                inactiveFilters = _.union(_.filter(this.props.availableFilters, _.partial(checkFilter, _, false)), _.filter(this.props.labelFilters, _.partial(checkFilter, _, true)))
                    .sort(function(filter1, filter2) {
                        return utils.natsort(filter1.title, filter2.title, {insensitive: true});
                    });
                appliedFilters = _.reject(this.props.activeFilters, (filter) => !filter.values.length);
            }

            this.props.selectedNodeLabels.sort(_.partialRight(utils.natsort, {insensitive: true}));

            return (
                <div className='row'>
                    <div className='sticker node-management-panel'>
                        <div className='node-list-management-buttons col-xs-5'>
                            <div className='view-mode-switcher'>
                                <div className='btn-group' data-toggle='buttons'>
                                    {_.map(models.Nodes.prototype.viewModes, function(mode) {
                                        return (
                                            <controls.Tooltip key={mode + '-view'} text={i18n(ns + mode + '_mode_tooltip')}>
                                                <label
                                                    className={utils.classNames(managementButtonClasses(mode == this.props.viewMode, mode))}
                                                    onClick={mode != this.props.viewMode && _.partial(this.props.changeViewMode, 'view_mode', mode)}
                                                >
                                                    <input type='radio' name='view_mode' value={mode} />
                                                    <i
                                                        className={utils.classNames({
                                                            glyphicon: true,
                                                            'glyphicon-th-list': mode == 'standard',
                                                            'glyphicon-th': mode == 'compact'
                                                        })}
                                                    />
                                                </label>
                                            </controls.Tooltip>
                                        );
                                    }, this)}
                                </div>
                            </div>
                            {this.props.mode != 'edit' && [
                                <controls.Tooltip wrap key='labels-btn' text={i18n(ns + 'labels_tooltip')}>
                                    <button
                                        disabled={!this.props.nodes.length}
                                        onClick={this.props.nodes.length && this.toggleLabelsPanel}
                                        className={utils.classNames(managementButtonClasses(this.props.isLabelsPanelOpen, 'btn-labels'))}
                                    >
                                        <i className='glyphicon glyphicon-tag' />
                                    </button>
                                </controls.Tooltip>,
                                <controls.Tooltip wrap key='sorters-btn' text={i18n(ns + 'sort_tooltip')}>
                                    <button
                                        disabled={!this.props.screenNodes.length}
                                        onClick={this.toggleSorters}
                                        className={utils.classNames(managementButtonClasses(this.state.areSortersVisible, 'btn-sorters'))}
                                    >
                                        <i className='glyphicon glyphicon-sort' />
                                    </button>
                                </controls.Tooltip>,
                                <controls.Tooltip wrap key='filters-btn' text={i18n(ns + 'filter_tooltip')}>
                                    <button
                                        disabled={!this.props.screenNodes.length}
                                        onClick={this.toggleFilters}
                                        className={utils.classNames(managementButtonClasses(this.state.areFiltersVisible, 'btn-filters'))}
                                    >
                                        <i className='glyphicon glyphicon-filter' />
                                    </button>
                                </controls.Tooltip>,
                                !this.state.activeSearch && (
                                    <controls.Tooltip wrap key='search-btn' text={i18n(ns + 'search_tooltip')}>
                                        <button
                                            disabled={!this.props.screenNodes.length}
                                            onClick={this.activateSearch}
                                            className={utils.classNames(managementButtonClasses(false, 'btn-search'))}
                                        >
                                            <i className='glyphicon glyphicon-search' />
                                        </button>
                                    </controls.Tooltip>
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
                                            onKeyDown={this.onSearchKeyDown}
                                            autoFocus
                                        />
                                        {this.state.isSearchButtonVisible &&
                                            <button className='close btn-clear-search' onClick={this.clearSearchField}>&times;</button>
                                        }
                                    </div>
                                )
                            ]}
                        </div>
                        <div className='control-buttons-box col-xs-7 text-right'>
                            {!!this.props.cluster && (
                                this.props.mode != 'list' ?
                                    <div className='btn-group' role='group'>
                                        <button
                                            className='btn btn-default'
                                            disabled={this.state.actionInProgress}
                                            onClick={_.bind(function() {
                                                this.props.revertChanges();
                                                this.changeScreen();
                                            }, this)}
                                        >
                                            {i18n('common.cancel_button')}
                                        </button>
                                        <button
                                            className='btn btn-success btn-apply'
                                            disabled={!this.isSavingPossible()}
                                            onClick={this.applyAndRedirect}
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
                                            {disksConflict && <i className='glyphicon glyphicon-danger-sign' />}
                                            {i18n('dialog.show_node.disk_configuration' + (_.all(this.props.nodes.invoke('areDisksConfigurable')) ? '_action' : ''))}
                                        </button>
                                        <button
                                            className='btn btn-default btn-configure-interfaces'
                                            disabled={!this.props.nodes.length}
                                            onClick={_.bind(this.goToConfigurationScreen, this, 'interfaces', interfaceConflict)}
                                        >
                                            {interfaceConflict && <i className='glyphicon glyphicon-danger-sign' />}
                                            {i18n('dialog.show_node.network_configuration' + (_.all(this.props.nodes.invoke('areInterfacesConfigurable')) ? '_action' : ''))}
                                        </button>
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
                                    </div>,
                                    !this.props.locked &&
                                        <div className='btn-group' role='group' key='add-nodes-button'>
                                            <button
                                                className='btn btn-success btn-add-nodes'
                                                onClick={_.bind(this.changeScreen, this, 'add', false)}
                                                disabled={this.props.locked}
                                            >
                                                <i className='glyphicon glyphicon-plus' />
                                                {i18n(ns + 'add_nodes_button')}
                                            </button>
                                        </div>
                                ]
                            )}
                        </div>
                        {this.props.mode != 'edit' && !!this.props.screenNodes.length && [
                            this.props.isLabelsPanelOpen &&
                                <NodeLabelsPanel {... _.pick(this.props, 'nodes', 'screenNodes')}
                                    key='labels'
                                    labels={this.props.selectedNodeLabels}
                                    toggleLabelsPanel={this.toggleLabelsPanel}
                                />,
                            this.state.areSortersVisible && (
                                <div className='col-xs-12 sorters' key='sorters'>
                                    <div className='well clearfix' key={this.state.sortersKey}>
                                        <div className='well-heading'>
                                            <i className='glyphicon glyphicon-sort' /> {i18n(ns + 'sort_by')}
                                            {canResetSorters &&
                                                <button className='btn btn-link pull-right btn-reset-sorting' onClick={this.resetSorters}>
                                                    <i className='glyphicon glyphicon-remove-sign' /> {i18n(ns + 'reset')}
                                                </button>
                                            }
                                        </div>
                                        {this.props.activeSorters.map(function(sorter) {
                                            var asc = sorter.order == 'asc';
                                            return (
                                                <div
                                                    key={'sort_by-' + sorter.name + (sorter.isLabel && '-label')}
                                                    className={utils.classNames({
                                                        'sorter-control pull-left': true,
                                                        ['sort-by-' + sorter.name + '-' + sorter.order]: !sorter.isLabel
                                                    })}
                                                >
                                                    <button className='btn btn-default' onClick={_.partial(this.props.changeSortingOrder, sorter)}>
                                                        {sorter.title}
                                                        <i
                                                            className={utils.classNames({
                                                                glyphicon: true,
                                                                'glyphicon-arrow-down': asc,
                                                                'glyphicon-arrow-up': !asc
                                                            })}
                                                        />
                                                    </button>
                                                    {this.props.activeSorters.length > 1 && this.renderDeleteSorterButton(sorter)}
                                                </div>
                                            );
                                        }, this)}
                                        <MultiSelectControl
                                            name='sorter-more'
                                            label={i18n(ns + 'more')}
                                            options={inactiveSorters}
                                            onChange={this.props.addSorting}
                                            dynamicValues
                                            isOpen= {this.state.isMoreSorterControlVisible}
                                            toggle={this.toggleMoreSorterControl}
                                        />
                                    </div>
                                </div>
                            ),
                            this.state.areFiltersVisible && (
                                <div className='col-xs-12 filters' key='filters'>
                                    <div className='well clearfix' key={this.state.filtersKey}>
                                        <div className='well-heading'>
                                            <i className='glyphicon glyphicon-filter' /> {i18n(ns + 'filter_by')}
                                            {!!appliedFilters.length &&
                                                <button className='btn btn-link pull-right btn-reset-filters' onClick={this.resetFilters}>
                                                    <i className='glyphicon glyphicon-remove-sign' /> {i18n(ns + 'reset')}
                                                </button>
                                            }
                                        </div>
                                        {_.map(this.props.activeFilters, function(filter) {
                                            var props = {
                                                key: (filter.isLabel ? 'label-' : '') + filter.name,
                                                ref: filter.name,
                                                name: filter.name,
                                                values: filter.values,
                                                className: utils.classNames({
                                                    'filter-control': true,
                                                    ['filter-by-' + filter.name]: !filter.isLabel
                                                }),
                                                label: filter.title,
                                                extraContent: this.renderDeleteFilterButton(filter),
                                                onChange: _.partial(this.props.changeFilter, filter),
                                                prefix: i18n('cluster_page.nodes_tab.filters.prefixes.' + filter.name, {defaultValue: ''}),
                                                isOpen: this.isFilterOpen(filter),
                                                toggle: _.partial(this.toggleFilter, filter)
                                            };

                                            if (filter.isNumberRange) {
                                                return <NumberRangeControl {...props} min={filter.limits[0]} max={filter.limits[1]} />;
                                            }
                                            return <MultiSelectControl {...props} options={this.props.getFilterOptions(filter)} />;
                                        }, this)}
                                        <MultiSelectControl
                                            name='filter-more'
                                            label={i18n(ns + 'more')}
                                            options={inactiveFilters}
                                            onChange={this.addFilter}
                                            dynamicValues
                                            isOpen={this.state.isMoreFilterControlVisible}
                                            toggle={this.toggleMoreFilterControl}
                                        />
                                    </div>
                                </div>
                            )
                        ]}
                        {this.props.mode != 'edit' && !!this.props.screenNodes.length &&
                            <div className='col-xs-12'>
                                {(!this.state.areSortersVisible || !this.state.areFiltersVisible && !!appliedFilters.length) &&
                                    <div className='active-sorters-filters'>
                                        {!this.state.areFiltersVisible && !!appliedFilters.length &&
                                            <div className='active-filters row' onClick={this.toggleFilters}>
                                                <strong className='col-xs-1'>{i18n(ns + 'filter_by')}</strong>
                                                <div className='col-xs-11'>
                                                    {i18n('cluster_page.nodes_tab.filter_results_amount', {
                                                        count: this.props.filteredNodes.length,
                                                        total: this.props.screenNodes.length
                                                    })}
                                                    {_.map(appliedFilters, function(filter) {
                                                        var options = filter.isNumberRange ? null : this.props.getFilterOptions(filter);
                                                        return (
                                                            <div key={filter.name}>
                                                                <strong>{filter.title}{!!filter.values.length && ':'} </strong>
                                                                <span>
                                                                    {filter.isNumberRange ?
                                                                        _.uniq(filter.values).join(' - ')
                                                                    :
                                                                        _.map(filter.values, function(value) {
                                                                            return _.find(options, {name: value}).label;
                                                                        }).join(', ')
                                                                    }
                                                                </span>
                                                            </div>
                                                        );
                                                    }, this)}
                                                </div>
                                                <button className='btn btn-link btn-reset-filters' onClick={this.resetFilters}>
                                                    <i className='glyphicon glyphicon-remove-sign' />
                                                </button>
                                            </div>
                                        }
                                        {!this.state.areSortersVisible &&
                                            <div className='active-sorters row' onClick={this.toggleSorters}>
                                                <strong className='col-xs-1'>{i18n(ns + 'sort_by')}</strong>
                                                <div className='col-xs-11'>
                                                    {this.props.activeSorters.map(function(sorter, index) {
                                                        var asc = sorter.order == 'asc';
                                                        return (
                                                            <span key={sorter.name + (sorter.isLabel && '-label')}>
                                                                {sorter.title}
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
                                                {canResetSorters &&
                                                    <button className='btn btn-link btn-reset-sorting' onClick={this.resetSorters}>
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

    NodeLabelsPanel = React.createClass({
        mixins: [componentMixins.unsavedChangesMixin],
        getInitialState: function() {
            var labels = _.map(this.props.labels, function(label) {
                    var labelValues = this.props.nodes.getLabelValues(label),
                        definedLabelValues = _.reject(labelValues, _.isUndefined);
                    return {
                        key: label,
                        values: _.uniq(definedLabelValues),
                        checked: labelValues.length == definedLabelValues.length,
                        indeterminate: labelValues.length != definedLabelValues.length,
                        error: null
                    };
                }, this);
            return {
                labels: _.cloneDeep(labels),
                initialLabels: _.cloneDeep(labels),
                actionInProgress: false
            };
        },
        hasChanges: function() {
            return !_.isEqual(this.state.labels, this.state.initialLabels);
        },
        componentDidMount: function() {
            _.each(this.state.labels, function(labelData) {
                this.refs[labelData.key].getInputDOMNode().indeterminate = labelData.indeterminate;
            }, this);
        },
        addLabel: function() {
            var labels = this.state.labels;
            labels.push({
                key: '',
                values: [null],
                checked: false,
                error: null
            });
            this.setState({labels: labels});
        },
        changeLabelKey: function(index, oldKey, newKey) {
            var labels = this.state.labels,
                labelData = labels[index];
            labelData.key = newKey;
            if (!labelData.indeterminate) labelData.checked = true;
            this.validateLabels(labels);
            this.setState({labels: labels});
        },
        changeLabelState: function(index, key, checked) {
            var labels = this.state.labels,
                labelData = labels[index];
            labelData.checked = checked;
            labelData.indeterminate = false;
            this.validateLabels(labels);
            this.setState({labels: labels});
        },
        changeLabelValue: function(index, key, value) {
            var labels = this.state.labels,
                labelData = labels[index];
            labelData.values = [value || null];
            if (!labelData.indeterminate) labelData.checked = true;
            this.validateLabels(labels);
            this.setState({labels: labels});
        },
        validateLabels: function(labels) {
            _.each(labels, (currentLabel, currentIndex) => {
                currentLabel.error = null;
                if (currentLabel.checked || currentLabel.indeterminate) {
                    var ns = 'cluster_page.nodes_tab.node_management_panel.labels.';
                    if (!_.trim(currentLabel.key)) {
                        currentLabel.error = i18n(ns + 'empty_label_key');
                    } else {
                        var doesLabelExist = _.any(labels, (label, index) => {
                            return index != currentIndex &&
                                _.trim(label.key) == _.trim(currentLabel.key) &&
                                (label.checked || label.indeterminate);
                        });
                        if (doesLabelExist) currentLabel.error = i18n(ns + 'existing_label');
                    }
                }
            });
        },
        isSavingPossible: function() {
            return !this.state.actionInProgress && this.hasChanges() && _.all(_.pluck(this.state.labels, 'error'), _.isNull);
        },
        revertChanges: function() {
            return this.props.toggleLabelsPanel();
        },
        applyChanges: function() {
            if (!this.isSavingPossible()) return $.Deferred().reject();

            this.setState({actionInProgress: true});

            var nodes = new models.Nodes(
                this.props.nodes.map(function(node) {
                    var nodeLabels = node.get('labels');

                    _.each(this.state.labels, function(labelData, index) {
                        var oldLabel = this.props.labels[index];

                        // delete label
                        if (!labelData.checked && !labelData.indeterminate) {
                            delete nodeLabels[oldLabel];
                        }

                        var nodeHasLabel = !_.isUndefined(nodeLabels[oldLabel]),
                            label = labelData.key;
                        // rename label
                        if ((labelData.checked || labelData.indeterminate) && nodeHasLabel) {
                            var labelValue = nodeLabels[oldLabel];
                            delete nodeLabels[oldLabel];
                            nodeLabels[label] = labelValue;
                        }
                        // add label
                        if (labelData.checked && !nodeHasLabel) {
                            nodeLabels[label] = labelData.values[0];
                        }
                        // change label value
                        if (!_.isUndefined(nodeLabels[label]) && labelData.values.length == 1) {
                            nodeLabels[label] = labelData.values[0];
                        }
                    }, this);

                    return {id: node.id, labels: nodeLabels};
                }, this)
            );

            return Backbone.sync('update', nodes)
                .done(_.bind(function() {
                    this.props.screenNodes.fetch().always(_.bind(function() {
                        dispatcher.trigger('labelsConfigurationUpdated');
                        this.props.screenNodes.trigger('change');
                        this.props.toggleLabelsPanel();
                    }, this));
                }, this))
                .fail(function(response) {
                    utils.showErrorDialog({
                        message: i18n('cluster_page.nodes_tab.node_management_panel.node_management_error.labels_warning'),
                        response: response
                    });
                });
        },
        render: function() {
            var ns = 'cluster_page.nodes_tab.node_management_panel.labels.';

            return (
                <div className='col-xs-12 labels'>
                    <div className='well clearfix'>
                        <div className='well-heading'>
                            <i className='glyphicon glyphicon-tag' /> {i18n(ns + 'manage_labels')}
                        </div>
                        <div className='forms-box form-inline'>
                            <p>
                                {i18n(ns + 'bulk_label_action_start')}
                                <strong>
                                    {i18n(ns + 'selected_nodes_amount', {count: this.props.nodes.length})}
                                </strong>
                                {i18n(ns + 'bulk_label_action_end')}
                            </p>

                            {_.map(this.state.labels, function(labelData, index) {
                                var labelValueProps = labelData.values.length > 1 ? {
                                        value: '',
                                        wrapperClassName: 'has-warning',
                                        tooltipText: i18n(ns + 'label_value_warning')
                                    } : {
                                        value: labelData.values[0]
                                    };

                                var showControlLabels = index == 0;
                                return (
                                    <div className={utils.classNames({clearfix: true, 'has-label': showControlLabels})} key={index}>
                                        <controls.Input
                                            type='checkbox'
                                            ref={labelData.key}
                                            checked={labelData.checked}
                                            onChange={_.partial(this.changeLabelState, index)}
                                            wrapperClassName='pull-left'
                                        />
                                        <controls.Input
                                            type='text'
                                            maxLength='100'
                                            label={showControlLabels && i18n(ns + 'label_key')}
                                            value={labelData.key}
                                            onChange={_.partial(this.changeLabelKey, index)}
                                            error={labelData.error}
                                            wrapperClassName='label-key-control'
                                            autoFocus={index == this.state.labels.length - 1}
                                        />
                                        <controls.Input {...labelValueProps}
                                            type='text'
                                            maxLength='100'
                                            label={showControlLabels && i18n(ns + 'label_value')}
                                            onChange={_.partial(this.changeLabelValue, index)}
                                        />
                                    </div>
                                );
                            }, this)}
                            <button
                                className='btn btn-default btn-add-label'
                                onClick={this.addLabel}
                                disabled={this.state.actionInProgress}
                            >
                                {i18n(ns + 'add_label')}
                            </button>
                        </div>
                        {!!this.state.labels.length &&
                            <div className='control-buttons text-right'>
                                <div className='btn-group' role='group'>
                                    <button
                                        className='btn btn-default'
                                        onClick={this.revertChanges}
                                        disabled={this.state.actionInProgress}
                                    >
                                        {i18n('common.cancel_button')}
                                    </button>
                                    <button
                                        className='btn btn-success'
                                        onClick={this.applyChanges}
                                        disabled={!this.isSavingPossible()}
                                    >
                                        {i18n('common.apply_button')}
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
                    .map(function(role) {
                        return roles.find({name: role}).conflicts;
                    })
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
                                    wrapperClassName={name}
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
            var checked = this.props.mode == 'edit' || (this.props.nodes.length && !_.any(this.props.nodes, function(node) {return !this.props.selectedNodeIds[node.id];}, this));
            return (
                <controls.Input
                    ref='select-all'
                    name='select-all'
                    type='checkbox'
                    checked={checked}
                    disabled={
                        this.props.mode == 'edit' || this.props.locked || !this.props.nodes.length ||
                        !checked && !_.isNull(this.props.maxNumberOfNodes) && this.props.maxNumberOfNodes < this.props.nodes.length
                    }
                    label={i18n('common.select_all')}
                    wrapperClassName='select-all pull-right'
                    onChange={_.bind(this.props.selectNodes, this.props, _.pluck(this.props.nodes, 'id'))}
                />
            );
        }
    };

    NodeList = React.createClass({
        mixins: [SelectAllMixin],
        groupNodes: function() {
            var uniqValueSorters = ['name', 'mac', 'ip'];

            var composeNodeDiskSizesLabel = function(node) {
                var diskSizes = node.resource('disks');
                return i18n('node_details.disks_amount', {
                    count: diskSizes.length,
                    size: diskSizes.map(function(size) {
                            return utils.showDiskSize(size) + ' ' + i18n('node_details.hdd');
                        }).join(', ')
                });
            };

            var labelNs = 'cluster_page.nodes_tab.node_management_panel.labels.',
                getLabelValue = function(node, label) {
                    var labelValue = node.getLabel(label);
                    return labelValue === false ?
                            i18n(labelNs + 'not_assigned_label', {label: label})
                        :
                            _.isNull(labelValue) ?
                                i18n(labelNs + 'not_specified_label', {label: label})
                            :
                                label + ' "' + labelValue + '"';
                };

            var groupingMethod = _.bind(function(node) {
                return _.compact(_.map(this.props.activeSorters, function(sorter) {
                    if (_.contains(uniqValueSorters, sorter.name)) return;

                    if (sorter.isLabel) return getLabelValue(node, sorter.name);

                    var result,
                        ns = 'cluster_page.nodes_tab.node.',
                        cluster = this.props.cluster || this.props.clusters.get(node.get('cluster'));
                    switch (sorter.name) {
                        case 'roles':
                            result = node.getRolesSummary(this.props.roles) || i18n(ns + 'no_roles');
                            break;
                        case 'status':
                            result = i18n(ns + 'status.' + node.getStatusSummary(), {
                                os: cluster && cluster.get('release').get('operating_system') || 'OS'
                            });
                            break;
                        case 'manufacturer':
                            result = node.get('manufacturer') || i18n('common.not_specified');
                            break;
                        case 'group_id':
                            var nodeNetworkGroup = this.props.nodeNetworkGroups.get(node.get('group_id'));
                            result = nodeNetworkGroup && i18n(ns + 'node_network_group', {
                                    group: nodeNetworkGroup.get('name') + (this.props.cluster ? '' : ' (' + cluster.get('name') + ')')
                                }) || i18n(ns + 'no_node_network_group');
                            break;
                        case 'cluster':
                            result = cluster && i18n(ns + 'cluster', {cluster: cluster.get('name')})
                                || i18n(ns + 'unallocated');
                            break;
                        case 'hdd':
                            result = i18n('node_details.total_hdd', {total: utils.showDiskSize(node.resource('hdd'))});
                            break;
                        case 'disks':
                            result = composeNodeDiskSizesLabel(node);
                            break;
                        case 'ram':
                            result = i18n('node_details.total_ram', {total: utils.showMemorySize(node.resource('ram'))});
                            break;
                        case 'interfaces':
                            result = i18n('node_details.interfaces_amount', {count: node.resource('interfaces')});
                            break;
                        default:
                            result = i18n('node_details.' + sorter.name, {count: node.resource(sorter.name)});
                    }
                    return result;
                }, this)).join('; ');
            }, this);
            var groups = _.pairs(_.groupBy(this.props.nodes, groupingMethod));

            // sort grouped nodes by name, mac or ip
            var formattedSorters = _.compact(_.map(this.props.activeSorters, function(sorter) {
                if (_.contains(uniqValueSorters, sorter.name)) {
                    return {attr: sorter.name, desc: sorter.order == 'desc'};
                }
            }));
            if (formattedSorters.length) {
                _.each(groups, function(group) {
                    group[1].sort(function(node1, node2) {
                        return utils.multiSort(node1, node2, formattedSorters);
                    });
                });
            }

            // sort grouped nodes by other applied sorters
            var preferredRolesOrder = this.props.roles.pluck('name');
            return groups.sort(_.bind(function(group1, group2) {
                var result;
                _.each(this.props.activeSorters, function(sorter) {
                    var node1 = group1[1][0], node2 = group2[1][0];

                    if (sorter.isLabel) {
                        var node1Label = node1.getLabel(sorter.name),
                            node2Label = node2.getLabel(sorter.name);
                        if (node1Label && node2Label) {
                            result = utils.natsort(node1Label, node2Label, {insensitive: true});
                        } else {
                            result = node1Label === node2Label ? 0 : _.isString(node1Label) ? -1 : _.isNull(node1Label) ? -1 : 1;
                        }
                    } else {
                        switch (sorter.name) {
                            case 'roles':
                                var roles1 = node1.sortedRoles(preferredRolesOrder),
                                    roles2 = node2.sortedRoles(preferredRolesOrder),
                                    order;
                                if (!roles1.length && !roles2.length) result = 0;
                                else if (!roles1.length) result = 1;
                                else if (!roles2.length) result = -1;
                                else {
                                    while (!order && roles1.length && roles2.length) {
                                        order = _.indexOf(preferredRolesOrder, roles1.shift()) - _.indexOf(preferredRolesOrder, roles2.shift());
                                    }
                                    result = order || roles1.length - roles2.length;
                                }
                                break;
                            case 'status':
                                result = _.indexOf(this.props.statusesToFilter, node1.getStatusSummary()) - _.indexOf(this.props.statusesToFilter, node2.getStatusSummary());
                                break;
                            case 'manufacturer':
                                result = utils.compare(node1, node2, {attr: sorter.name});
                                break;
                            case 'disks':
                                result = utils.natsort(composeNodeDiskSizesLabel(node1), composeNodeDiskSizesLabel(node2));
                                break;
                            case 'group_id':
                                var nodeGroup1 = node1.get('group_id'),
                                    nodeGroup2 = node2.get('group_id');
                                result = nodeGroup1 == nodeGroup2 ? 0 :
                                    !nodeGroup1 ? 1 : !nodeGroup2 ? -1 : nodeGroup1 - nodeGroup2;
                                break;
                            case 'cluster':
                                var cluster1 = node1.get('cluster'),
                                    cluster2 = node2.get('cluster');
                                result = cluster1 == cluster2 ? 0 :
                                    !cluster1 ? 1 : !cluster2 ? -1 : utils.natsort(this.props.clusters.get(cluster1).get('name'), this.props.clusters.get(cluster2).get('name'));
                                break;
                            default:
                                result = node1.resource(sorter.name) - node2.resource(sorter.name);
                                break;
                        }
                    }

                    if (sorter.order == 'desc') {
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
                                {utils.renderMultilineText(
                                    i18n('cluster_page.nodes_tab.' + (this.props.mode == 'add' ? 'no_nodes_in_fuel' : 'no_nodes_in_environment'))
                                )}
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
                                {... _.pick(this.props, 'mode', 'viewMode', 'nodeNetworkGroups')}
                                key={node.id}
                                node={node}
                                renderActionButtons={!!this.props.cluster}
                                cluster={this.props.cluster || this.props.clusters.get(node.get('cluster'))}
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
