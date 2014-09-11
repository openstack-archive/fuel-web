/*
 * Copyright 2013 Mirantis, Inc.
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
    'utils',
    'models',
    'jsx!views/dialogs',
    'views/cluster_page_tabs/nodes_tab_screens/screen',
    'jsx!views/cluster_page_tabs/nodes_tab_screens/node',
    'text!templates/cluster/nodes_management_panel.html',
    'text!templates/cluster/assign_roles_panel.html',
    'text!templates/cluster/node_list.html',
    'text!templates/cluster/node_group.html'
],
function(utils, models, dialogs, Screen, nodesManagementPanelTemplate, assignRolesPanelTemplate, nodeListTemplate, nodeGroupTemplate) {
    'use strict';
    var NodeListScreen, NodesManagementPanel, AssignRolesPanel, NodeList, NodeGroup;

    NodeListScreen = Screen.extend({
        constructorName: 'NodeListScreen',
        updateInterval: 20000,
        hasChanges: function() {
            return this instanceof this.ClusterNodesScreen ? false : !_.isEqual(this.nodes.pluck('pending_roles'), this.initialNodes.pluck('pending_roles'));
        },
        scheduleUpdate: function() {
            this.registerDeferred($.timeout(this.updateInterval).done(_.bind(this.update, this)));
        },
        update: function() {
            this.nodes.fetch().always(_.bind(this.scheduleUpdate, this));
        },
        revertChanges: function() {
            this.nodes.each(function(node) {
                node.set({pending_roles: this.initialNodes.get(node.id).get('pending_roles')}, {silent: true});
            }, this);
        },
        calculateApplyButtonState: function() {
            this.applyChangesButton.set('disabled', !this.hasChanges());
        },
        updateBatchActionsButtons: function() {
            var nodes = new models.Nodes(this.nodes.where({checked: true}));
            var deployedNodes = nodes.where({'status': 'ready'});
            this.configureDisksButton.set('disabled', !nodes.length || deployedNodes.length > 1);
            this.configureInterfacesButton.set('disabled', !nodes.length || deployedNodes.length > 1);
            this.deleteNodesButton.set('visible', !!nodes.where({pending_deletion: false}).length && !this.isLocked());
            this.addNodesButton.set('visible', !nodes.length);
            var notDeployedSelectedNodes = nodes.where({pending_addition: true});
            this.editRolesButton.set('visible', !!notDeployedSelectedNodes.length && notDeployedSelectedNodes.length == nodes.length);
            // check selected nodes for group configuration availability
            var noDisksConflict = true;
            nodes.each(function(node) {
                var noRolesConflict = !_.difference(_.union(nodes.at(0).get('roles'), nodes.at(0).get('pending_roles')), _.union(node.get('roles'), node.get('pending_roles'))).length;
                noDisksConflict = noDisksConflict && noRolesConflict && _.isEqual(nodes.at(0).resource('disks'), node.resource('disks'));
            });
            if (!deployedNodes.length) {
                this.configureDisksButton.set('invalid', !noDisksConflict);
                this.configureInterfacesButton.set('invalid', _.uniq(nodes.map(function(node) {return node.resource('interfaces');})).length > 1 || !!nodes.where({status: 'error'}).length);
            }
        },
        setupButtonsBindings: function() {
            var visibleBindings = {
                observe: 'visible',
                visible: true
            };
            var disabledBindings = {
                attributes: [{
                    name: 'disabled',
                    observe: 'disabled'
                }]
            };
            this.stickit(this.deleteNodesButton, {'.btn-delete-nodes': visibleBindings});
            this.stickit(this.configureDisksButton, {'.btn-configure-disks' : {
                attributes: _.union([], disabledBindings.attributes, this.getConfigureButtonsObject('btn btn-group-congiration btn-configure-disks'))
            }});
            this.stickit(this.configureInterfacesButton, {'.btn-configure-interfaces': {
                attributes: _.union([], disabledBindings.attributes, this.getConfigureButtonsObject('btn btn-group-congiration btn-configure-interfaces'))
            }});
            this.stickit(this.addNodesButton, {'.btn-add-nodes': _.extend({}, visibleBindings, disabledBindings)});
            this.stickit(this.editRolesButton, {'.btn-edit-nodes': _.extend({}, visibleBindings,disabledBindings)});
            this.stickit(this.applyChangesButton, {'.btn-apply': disabledBindings});
        },
        getConfigureButtonsObject: function(className) {
            return [
                {
                    name: 'data-invalid',
                    observe: 'invalid'
                },
                {
                    name: 'class',
                    observe: 'invalid',
                    onGet: function(value) {
                        return value ? className + ' conflict' : className;
                    }
                }
            ];
        },
        actualizePendingRoles: function(node, roles, options) {
            if (!options.assign) {
                node.set({pending_roles: node.previous('pending_roles')}, {assign: true});
            }
        },
        actualizeFilteredNode: function(node, options) {
            var filteredNode = this.nodeList.filteredNodes.get(node.id);
            if (filteredNode) {
                filteredNode.set(node.attributes);
            }
        },
        initialize: function() {
            this.ClusterNodesScreen = require('views/cluster_page_tabs/nodes_tab_screens/cluster_nodes_screen');
            this.AddNodesScreen = require('views/cluster_page_tabs/nodes_tab_screens/add_nodes_screen');
            this.EditNodesScreen = require('views/cluster_page_tabs/nodes_tab_screens/edit_nodes_screen');
            this.nodes.on('resize', function() {
                this.render();
                this.nodeList.filterNodes(this.nodeFilter.get('value'));
            }, this);
            if (this instanceof this.AddNodesScreen || this instanceof this.EditNodesScreen) {
                this.nodes.on('change:pending_roles', this.actualizePendingRoles, this);
                this.model.on('change:status', function() {
                    app.navigate('#cluster/' + this.model.id + '/nodes', {trigger: true});
                }, this);
            }
            this.nodes.on('change', this.actualizeFilteredNode, this);
            this.scheduleUpdate();
            var defaultButtonModelsData = {
                visible: false,
                disabled: true,
                invalid: false
            };
            this.addNodesButton = new Backbone.Model(_.extend({}, defaultButtonModelsData, {visible: true, disabled: false}));
            this.deleteNodesButton = new Backbone.Model(_.extend({}, defaultButtonModelsData, {disabled: false}));
            this.editRolesButton = new Backbone.Model(_.extend({}, defaultButtonModelsData));
            this.configureDisksButton = new Backbone.Model(_.extend({}, defaultButtonModelsData));
            this.configureInterfacesButton = new Backbone.Model(_.extend({}, defaultButtonModelsData));
            this.applyChangesButton = new Backbone.Model(_.extend({}, defaultButtonModelsData));
            this.nodeFilter = new Backbone.Model({value: ''});
            this.nodeFilter.on('change', _.debounce(function(filter) {
                this.nodeList.filterNodes(filter.get('value'));
            }, 300), this);
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            this.$el.html('');
            if (this instanceof this.EditNodesScreen) {
                this.$el.append($('<div>').addClass('alert').text($.t('cluster_page.nodes_tab.disk_configuration_reset_warning')));
            }
            var options = {nodes: this.nodes, screen: this};
            var managementPanel = new NodesManagementPanel(options);
            this.registerSubView(managementPanel);
            this.$el.append(managementPanel.render().el);
            if (this instanceof this.AddNodesScreen || this instanceof this.EditNodesScreen) {
                this.roles = new AssignRolesPanel(options);
                this.registerSubView(this.roles);
                this.$el.append(this.roles.render().el);
            }
            this.nodeList = new NodeList(options);
            this.registerSubView(this.nodeList);
            this.$el.append(this.nodeList.render().el);
            this.nodeList.calculateSelectAllCheckedState();
            this.nodeList.calculateSelectAllDisabledState();
            this.setupButtonsBindings();
            var bindings = {
                'input[name=filter]': {
                    observe: 'value',
                    getVal: function($el) { return $.trim($el.val()).toLowerCase(); }
                },
                '.btn-clear-filter': {
                    observe: 'value',
                    visible: function(value, options) {
                        return !!value;
                    }
                }
            };
            this.stickit(this.nodeFilter, bindings);
            return this;
        }
    });

    NodesManagementPanel = Backbone.View.extend({
        className: 'nodes-management-panel',
        template: _.template(nodesManagementPanelTemplate),
        events: {
            'change select[name=grouping]' : 'groupNodes',
            'click .btn-delete-nodes:not(:disabled)' : 'showDeleteNodesDialog',
            'click .btn-apply:not(:disabled)' : 'applyChanges',
            'click .btn-group-congiration:not(.conflict):not(:disabled)' : 'goToConfigurationScreen',
            'click .btn-group-congiration.conflict' : 'showUnavailableGroupConfigurationDialog',
            'click .btn-add-nodes': 'goToAddNodesScreen',
            'click .btn-edit-nodes': 'goToEditNodesRolesScreen',
            'click .btn-cancel': 'goToNodesList',
            'click .btn-clear-filter' : 'clearFilter'
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.cluster = this.screen.tab.model;
        },
        groupNodes: function(e) {
            var grouping = this.$(e.currentTarget).val();
            if (!(this.screen instanceof this.screen.AddNodesScreen || this.screen instanceof this.screen.EditNodesScreen)) {
                this.cluster.save({grouping: grouping}, {patch: true, wait: true});
            }
            this.screen.nodeList.groupNodes(grouping);
        },
        showDeleteNodesDialog: function() {
            var nodes = new models.Nodes(this.screen.nodes.where({checked: true}));
            nodes.cluster = this.nodes.cluster;
            var dialog = new dialogs.DeleteNodesDialog({nodes: nodes});
            app.page.tab.registerSubView(dialog);
            dialog.render();
        },
        applyChanges: function() {
            this.$('.btn-apply').prop('disabled', true);
            var nodes  = new models.Nodes(_.invoke(this.screen.nodes.where({checked: true}), 'clone'));
            nodes.each(function(node) {
                if (!this.nodes.cluster) {
                    node.set({cluster_id: this.cluster.id, pending_addition: true});
                }
                if (!node.get('pending_roles').length && node.get('pending_addition')) {
                    node.set({cluster_id: null, pending_addition: false});
                }
            }, this);
            nodes.toJSON = function(options) {
                return this.map(function(node) {
                    return _.pick(node.attributes, 'id', 'cluster_id', 'pending_roles', 'pending_addition');
                });
            };
            nodes.sync('update', nodes)
                .done(_.bind(function() {
                    $.when(this.cluster.fetch(), this.cluster.fetchRelated('nodes')).always(_.bind(function() {
                        app.navigate('#cluster/' + this.cluster.id + '/nodes', {trigger: true});
                        app.navbar.refresh();
                        app.page.removeFinishedNetworkTasks();
                        app.page.deploymentControl.render();
                    }, this));
                }, this))
                .fail(_.bind(function() {
                    this.$('.btn-apply').prop('disabled', false);
                    utils.showErrorDialog({
                        title: $.t('cluster_page.nodes_tab.node_management_panel.node_management_error.title'),
                        message: $.t('cluster_page.nodes_tab.node_management_panel.node_management_error.saving_warning')
                    });
                }, this));
        },
        goToConfigurationScreen: function(e) {
            var selectedNodesIds = _.pluck(this.screen.nodes.where({checked: true}), 'id').join(',');
            app.navigate('#cluster/' + this.cluster.id + '/nodes/' + $(e.currentTarget).data('action') + '/' + utils.serializeTabOptions({nodes: selectedNodesIds}), {trigger: true});
        },
        goToAddNodesScreen: function() {
            app.navigate('#cluster/' + this.cluster.id + '/nodes/add', {trigger: true});
        },
        goToEditNodesRolesScreen: function() {
            app.navigate('#cluster/' + this.cluster.id + '/nodes/edit/' + utils.serializeTabOptions({nodes: _.pluck(this.nodes.where({checked: true}), 'id')}), {trigger: true});
        },
        goToNodesList: function() {
            this.screen.revertChanges();
            app.navigate('#cluster/' + this.cluster.id + '/nodes', {trigger: true});
        },
        clearFilter: function() {
            this.screen.nodeFilter.set('value', '');
        },
        showUnavailableGroupConfigurationDialog: function (e) {
            var action = this.$(e.currentTarget).data('action');
            utils.showErrorDialog({
                title: $.t('cluster_page.nodes_tab.node_management_panel.node_management_error.title'),
                message: $.t('cluster_page.nodes_tab.node_management_panel.node_management_error.' + action + '_configuration_warning'),
                hideLogsLink: true
            });
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            this.$el.html(this.template({
                nodes: this.nodes,
                cluster: this.cluster,
                edit: this.screen instanceof this.screen.EditNodesScreen
            })).i18n();
            var isDisabled = !!this.cluster.tasks({group: 'deployment', status: 'running'}).length;
            this.screen.addNodesButton.set('disabled', isDisabled);
            this.screen.editRolesButton.set('disabled', isDisabled);
            return this;
        }
    });

    AssignRolesPanel = Backbone.View.extend({
        template: _.template(assignRolesPanelTemplate),
        className: 'roles-panel',
        handleChanges: function() {
            this.nodes = new models.Nodes(this.screen.nodes.where({checked: true}));
            this.assignRoles();
            this.checkForConflicts();
            this.screen.calculateApplyButtonState();
        },
        assignRoles: function() {
            _.each(this.collection.where({indeterminate: false}), function(role) {
                _.each(this.nodes.filter(function(node) {return !node.hasRole(role.get('name'), true);}), function(node) {
                    var pending_roles = role.get('checked') ? _.uniq(_.union(node.get('pending_roles'), role.get('name'))) : _.difference(node.get('pending_roles'), role.get('name'));
                    node.set({pending_roles: pending_roles}, {assign: true});
                });
            }, this);
        },
        isRoleSelected: function(roleName) {
            return this.collection.filter(function(role) {return role.get('name') == roleName && (role.get('checked') || role.get('indeterminate'));}).length;
        },
        isControllerSelectable: function(role) {
            var allocatedController = this.cluster.get('nodes').filter(function(node) {return !node.get('pending_deletion') && node.hasRole('controller') && !_.contains(this.nodes.pluck('id'), node.id);}, this);
            return role.get('name') != 'controller' || this.cluster.get('mode') != 'multinode' || ((this.isRoleSelected('controller') || this.screen.nodes.where({checked: true}).length <= 1) && !allocatedController.length);
        },
        isMongoSelectable: function(role) {
            var deployedNodes = this.cluster.get('nodes').filter(function(node) {
                return node.hasRole('mongo', true) && !node.get('pending_deletion');
            });
            return role.get('name') != 'mongo' || !deployedNodes.length;
        },
        isZabbixSelectable: function(role) {
            var allocatedZabbix = this.cluster.get('nodes').filter(function(node) {return !node.get('pending_deletion') && node.hasRole('zabbix-server') && !_.contains(this.nodes.pluck('id'), node.id);}, this);
            return role.get('name') != 'zabbix-server' || ((this.isRoleSelected('zabbix-server') || this.screen.nodes.where({checked: true}).length <= 1) && !allocatedZabbix.length);
        },
        getListOfIncompatibleRoles: function(roles) {
            var forbiddenRoles = [];
            _.each(roles, function(role) {
                forbiddenRoles = _.union(forbiddenRoles, this.conflictingRoles[role.get('name')]);
            }, this);
            return _.uniq(forbiddenRoles);
        },
        checkForConflicts: function(e) {
            this.collection.each(function(role) {
                var conflict = '';
                var disabled = !this.screen.nodes.length || this.loading.state() == 'pending';
                // checking if role is unavailable
                if (!disabled && role.get('unavailable')) {
                    disabled = true;
                    conflict = role.get('unavailabityReason');
                }
                // checking if role conflict with another role
                if (!disabled) {
                    var selectedRoles = this.collection.filter(function(role) {return role.get('checked') || role.get('indeterminate');});
                    var roleConflictsWithAnotherRole = _.contains(this.getListOfIncompatibleRoles(selectedRoles), role.get('name'));
                    if (roleConflictsWithAnotherRole) {
                        disabled = true;
                        conflict = $.t('cluster_page.nodes_tab.incompatible_roles_warning');
                    }
                }
                // checking controller role conditions
                if (!disabled && !this.isControllerSelectable(role)) {
                    disabled = true;
                    conflict = $.t('cluster_page.nodes_tab.one_controller_restriction');
                }
                // checking mongo role restriction
                if (!disabled && !this.isMongoSelectable(role)) {
                    disabled = true;
                    conflict = $.t('cluster_page.nodes_tab.mongo_restriction');
                }
                // checking zabbix role conditions
                if (!disabled && !this.isZabbixSelectable(role)) {
                    disabled = true;
                    conflict = $.t('cluster_page.nodes_tab.one_zabbix_restriction');
                }
                role.set({disabled: disabled, conflict: conflict});
            }, this);
            if (this.screen.nodeList) {
                var controllerNode = this.nodes.filter(function(node) {return node.hasRole('controller');})[0];
                var zabbixNode = this.nodes.filter(function(node) {return node.hasRole('zabbix-server');})[0];
                _.each(this.screen.nodes.where({checked: false}), function(node) {
                    var isControllerAssigned = this.cluster.get('mode') == 'multinode' && this.isRoleSelected('controller') && controllerNode && controllerNode.id != node.id;
                    var isZabbixAssigned = this.isRoleSelected('zabbix-server') && zabbixNode && zabbixNode.id != node.id;
                    var disabled = isControllerAssigned || isZabbixAssigned || !node.isSelectable() || this.screen instanceof this.screen.EditNodesScreen || this.screen.isLocked();
                    node.set('disabled', disabled);
                    var filteredNode = this.screen.nodeList.filteredNodes.get(node.id);
                    if (filteredNode) {
                        filteredNode.set('disabled', disabled);
                    }
                }, this);
                this.screen.nodeList.calculateSelectAllDisabledState();
                _.invoke(this.screen.nodeList.subViews, 'calculateSelectAllDisabledState', this);
            }
        },
        getRoleData: function(role) {
            return this.cluster.get('release').get('roles_metadata')[role];
        },
        checkRolesAvailability: function() {
            this.collection.each(function(role) {
                var unavailable = false;
                var visible = true;
                var unavailabityReasons = [];
                var dependencies = this.getRoleData(role.get('name')).depends;
                if (dependencies) {
                    var configModels = {
                        cluster: this.cluster,
                        settings: this.settings,
                        version: app.version,
                        default: this.settings
                    };
                    _.each(_.map(dependencies, utils.expandRestriction), function(dependency) {
                        if (!utils.evaluateExpression(dependency.condition, configModels).value) {
                            unavailable = true;
                            unavailabityReasons.push(dependency.warning);
                            if (dependency.action == 'hide') {
                                visible = false;
                            }
                        }
                    });
                }
                // FIXME(vk): hack for vCenter, do not allow ceph and controllers
                // has to be removed when we describe it in role metadata
                if (this.settings.get('common.libvirt_type.value') == 'vcenter') {
                    if (role.get('name') == 'compute') {
                        unavailable = true;
                        unavailabityReasons.push('Computes cannot be used with vCenter');
                    } else if (role.get('name') == 'ceph-osd') {
                        unavailable = true;
                        unavailabityReasons.push('Ceph cannot be used with vCenter');
                    }
                }

                if (unavailable) {
                    role.set({unavailable: true, unavailabityReason: unavailabityReasons.join(' ')});
                }
                role.set({visible: visible});
            }, this);
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.cluster = this.screen.tab.model;
            this.collection = new Backbone.Collection(_.map(this.cluster.get('release').get('roles'), function(role) {
                var roleData = this.getRoleData(role);
                var nodesWithRole = this.nodes.filter(function(node) {return node.hasRole(role);});
                return {
                    name: role,
                    label: roleData.name,
                    description: roleData.description,
                    disabled: false,
                    unavailable: false,
                    visible: true,
                    conflict: '',
                    checked: !!nodesWithRole.length && nodesWithRole.length == this.nodes.length,
                    indeterminate: !!nodesWithRole.length && nodesWithRole.length != this.nodes.length
                };
            }, this));
            this.collection.on('change:checked', this.handleChanges, this);
            this.settings = this.cluster.get('settings');
            (this.loading = this.settings.fetch({cache: true})).done(_.bind(function() {
                    this.processConflictingRoles();
                    this.checkRolesAvailability();
                    this.checkForConflicts();
            }, this));
        },
        processConflictingRoles: function() {
            var rolesMetadata = this.cluster.get('release').get('roles_metadata');
            this.conflictingRoles = {};
            _.each(rolesMetadata, function(roleData, roleName) {
                var conflicts = roleData.conflicts;
                if (conflicts) {
                    this.conflictingRoles[roleName] = _.uniq(_.union(this.conflictingRoles[roleName], conflicts));
                    _.each(conflicts, function(conflict) {
                        this.conflictingRoles[conflict] =  this.conflictingRoles[conflict] || [];
                        this.conflictingRoles[conflict].push(roleName);
                    }, this);
                }
            }, this);
        },
        stickitRole: function (role) {
            var bindings = {};
            bindings['input[name=' + role.get('name') + ']'] = {
                observe: 'checked',
                visible: function() {
                    return role.get('visible');
                },
                visibleFn: function($el, isVisible) {
                    $el.parents('.role-container').toggle(isVisible);
                },
                onSet: function(value) {
                    role.set('indeterminate', false);
                    return value;
                },
                attributes: [{
                    name: 'disabled',
                    observe: 'disabled'
                },{
                    name: 'indeterminate',
                    observe: 'indeterminate'
                }]
            };
            bindings['.role-conflict.' + role.get('name')] = 'conflict';
            return this.stickit(role, bindings);
        },
        render: function() {
            this.$el.html(this.template({roles: this.collection})).i18n();
            this.collection.each(this.stickitRole, this);
            this.checkForConflicts();
            return this;
        }
    });

    NodeList = Backbone.View.extend({
        className: 'node-list',
        template: _.template(nodeListTemplate),
        events: {
            'click .btn-cluster-details': 'toggleSummaryPanel'
        },
        selectAllBindings: {
            'input[name=select-nodes-common]': {
                observe: 'checked',
                onSet: 'selectNodes',
                attributes: [{
                    name: 'disabled',
                    observe: 'disabled'
                }]
            }
        },
        selectNodes: function(value) {
            _.each(this.subViews, function(nodeGroup) {
                if (!nodeGroup.selectAllCheckbox.get('disabled')) {
                    nodeGroup.selectAllCheckbox.set('checked', value);
                }
            });
            _.invoke(this.filteredNodes.where({disabled: false}), 'set', {checked: value});
            return value;
        },
        hideSummaryPanel: function(e) {
            if (!(e && $(e.target).closest(this.$('.node-list-name')).length)) {
                this.$('.cluster-details').hide();
            }
        },
        toggleSummaryPanel: function() {
            this.$('.cluster-details').toggle();
        },
        calculateSelectAllCheckedState: function() {
            var availableNodes = this.filteredNodes.filter(function(node) {return node.isSelectable();});
            this.selectAllCheckbox.set('checked', availableNodes.length && this.filteredNodes.where({checked: true}).length == availableNodes.length);
        },
        calculateSelectAllDisabledState: function() {
            var availableNodes = this.filteredNodes.filter(function(node) {return node.isSelectable();});
            var roleAmountRestrictions = this.screen.roles && (this.screen.roles.isRoleSelected('controller') || this.screen.roles.isRoleSelected('zabbix-server')) && availableNodes.length > 1;
            var disabled = !this.filteredNodes.where({disabled: false}).length || roleAmountRestrictions || this.screen instanceof this.screen.EditNodesScreen;
            this.selectAllCheckbox.set('disabled', disabled);
        },
        groupNodes: function(grouping) {
            if (_.isUndefined(grouping)) {
                grouping = this.screen instanceof this.screen.AddNodesScreen ? 'hardware' : this.screen.tab.model.get('grouping');
            }
            var nodeGroups = _.pairs(this.filteredNodes.groupByAttribute(grouping));
            // sort node groups
            if (grouping != 'hardware') {
                var preferredOrder = this.screen.tab.model.get('release').get('roles');
                nodeGroups.sort(function(firstGroup, secondGroup) {
                    var firstGroupRoles = firstGroup[1][0].sortedRoles();
                    var secondGroupRoles = secondGroup[1][0].sortedRoles();
                    var order;
                    while (!order && firstGroupRoles.length && secondGroupRoles.length) {
                        order = _.indexOf(preferredOrder, firstGroupRoles.shift()) - _.indexOf(preferredOrder, secondGroupRoles.shift());
                    }
                    return order || firstGroupRoles.length - secondGroupRoles.length;
                });
            } else {
                nodeGroups = _.sortBy(nodeGroups, function(group){ return group[0];});
            }
            this.renderNodeGroups(nodeGroups);
            this.screen.updateBatchActionsButtons();
        },
        filterNodes: function(filterValue) {
            this.filteredNodes.reset(_.invoke(this.nodes.filter(function(node) {
                return _.contains(node.get('name').toLowerCase(), filterValue) || _.contains(node.get('mac').toLowerCase(), filterValue);
            }), 'clone'));
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.screen.initialNodes = new models.Nodes(this.nodes.invoke('clone'));
            this.filteredNodes = new models.Nodes(this.nodes.invoke('clone'));
            this.filteredNodes.cluster = this.screen.nodes.cluster;
            this.filteredNodes.deferred = this.screen.nodes.deferred;
            this.filteredNodes.on('change:checked', this.calculateSelectAllCheckedState, this);
            this.filteredNodes.on('reset', this.render, this);
            this.eventNamespace = 'click.click-summary-panel';
            this.selectAllCheckbox = new Backbone.Model({
                checked: false,
                disabled: false
            });
        },
        renderNodeGroups: function(nodeGroups) {
            this.$('.nodes').html('');
            _.each(nodeGroups, function(group) {
                var nodeGroupView = new NodeGroup({
                    groupLabel: group[0],
                    nodes: new models.Nodes(group[1]),
                    nodeList: this
                });
                this.registerSubView(nodeGroupView);
                this.$('.nodes').append(nodeGroupView.render().el);
            }, this);
        },
        beforeTearDown: function() {
            $('html').off(this.eventNamespace);
            Backbone.history.off('route', this.hideSummaryPanel, this);
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            this.$el.html(this.template({
                nodes: this.filteredNodes,
                totalNodesAmount: this.screen.nodes.length,
                edit: this.screen instanceof this.screen.EditNodesScreen
            })).i18n();
            this.groupNodes();
            $('html').on(this.eventNamespace, _.bind(this.hideSummaryPanel, this));
            Backbone.history.on('route', this.hideSummaryPanel, this);
            this.stickit(this.selectAllCheckbox, this.selectAllBindings);
            return this;
        }
    });

    NodeGroup = Backbone.View.extend({
        className: 'node-group',
        template: _.template(nodeGroupTemplate),
        selectAllBindings: {
            'input[name=select-node-group]': {
                observe: 'checked',
                onSet: 'selectNodes',
                attributes: [{
                    name: 'disabled',
                    observe: 'disabled'
                }]
            }
        },
        selectNodes: function(value) {
            _.each(this.nodes.where({disabled: false}), function(node) {
                node.set('checked', value);
            });
            this.nodeList.calculateSelectAllCheckedState();
            return value;
        },
        calculateSelectAllCheckedState: function() {
            var availableNodes = this.nodes.filter(function(node) {return node.isSelectable();});
            this.selectAllCheckbox.set('checked', availableNodes.length && this.nodes.where({checked: true}).length == availableNodes.length);
        },
        calculateSelectAllDisabledState: function() {
            var availableNodes = this.nodes.where({disabled: false});
            var roleAmountRestrictions = this.nodeList.screen.roles && (this.nodeList.screen.roles.isRoleSelected('controller') || this.nodeList.screen.roles.isRoleSelected('zabbix-server')) && availableNodes.length > 1;
            var disabled = !availableNodes.length || roleAmountRestrictions || this.nodeList.screen instanceof this.nodeList.screen.EditNodesScreen;
            this.selectAllCheckbox.set('disabled', disabled);
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.selectAllCheckbox = new Backbone.Model({
                checked: false,
                disabled: false
            });
            this.selectAllCheckbox.on('change:disabled', this.nodeList.calculateSelectAllDisabledState, this.nodeList);
            this.nodes.on('change:checked', this.calculateSelectAllCheckedState, this);
        },
        renderNode: function(node) {
            //var nodeView = new Node({node: node, group: this});
            //this.registerSubView(nodeView);
            //this.$('.nodes-group').append(nodeView.render().el);
            this.clusterInfo = utils.universalMount(new Node({node: node, group: this}), this.$('.nodes-group'), this);
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            this.$el.html(this.template({
                groupLabel: this.groupLabel,
                nodes: this.nodes
            })).i18n();
            this.nodes.each(this.renderNode, this);
            this.stickit(this.selectAllCheckbox, this.selectAllBindings);
            this.calculateSelectAllCheckedState();
            this.calculateSelectAllDisabledState();
            return this;
        }
    });

    return NodeListScreen;
});
