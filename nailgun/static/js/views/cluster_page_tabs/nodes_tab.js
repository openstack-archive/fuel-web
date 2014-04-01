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
    'views/common',
    'views/dialogs',
    'text!templates/cluster/nodes_management_panel.html',
    'text!templates/cluster/assign_roles_panel.html',
    'text!templates/cluster/node_list.html',
    'text!templates/cluster/node_group.html',
    'text!templates/cluster/node.html',
    'text!templates/cluster/node_roles.html',
    'text!templates/cluster/edit_node_disks.html',
    'text!templates/cluster/node_disk.html',
    'text!templates/cluster/volume_style.html',
    'text!templates/cluster/edit_node_interfaces.html',
    'text!templates/cluster/node_interface.html'
],
function(utils, models, commonViews, dialogViews, nodesManagementPanelTemplate, assignRolesPanelTemplate, nodeListTemplate, nodeGroupTemplate, nodeTemplate, nodeRoleTemplate, editNodeDisksScreenTemplate, nodeDisksTemplate, volumeStylesTemplate, editNodeInterfacesScreenTemplate, nodeInterfaceTemplate) {
    'use strict';
    var NodesTab, Screen, NodeListScreen, ClusterNodesScreen, AddNodesScreen, EditNodesScreen, NodesManagementPanel, AssignRolesPanel, NodeList, NodeGroup, Node, EditNodeScreen, EditNodeDisksScreen, NodeDisk, EditNodeInterfacesScreen, NodeInterface;

    NodesTab = commonViews.Tab.extend({
        className: 'wrapper',
        screen: null,
        scrollPositions: {},
        hasChanges: function() {
            return this.screen && _.result(this.screen, 'hasChanges');
        },
        changeScreen: function(NewScreenView, screenOptions) {
            var options = _.extend({model: this.model, tab: this, screenOptions: screenOptions || []});
            if (this.screen) {
                if (this.screen.keepScrollPosition) {
                    this.scrollPositions[this.screen.constructorName] = $(window).scrollTop();
                }
                this.screen.$el.fadeOut('fast', _.bind(function() {
                    this.screen.tearDown();
                    this.screen = new NewScreenView(options);
                    this.screen.render();
                    this.screen.$el.hide().fadeIn('fast');
                    this.$el.html(this.screen.el);
                    if (this.screen.keepScrollPosition && this.scrollPositions[this.screen.constructorName]) {
                        $(window).scrollTop(this.scrollPositions[this.screen.constructorName]);
                    }
                }, this));
            } else {
                this.screen = new NewScreenView(options);
                this.$el.html(this.screen.render().el);
            }
            this.registerSubView(this.screen);
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.revertChanges = _.bind(function() {
                return this.screen && this.screen.revertChanges();
            }, this);
            this.selectedNodes = new models.Nodes();
            this.selectedNodes.cluster = this.model;
        },
        routeScreen: function(options) {
            var screens = {
                'list': ClusterNodesScreen,
                'add': AddNodesScreen,
                'edit': EditNodesScreen,
                'disks': EditNodeDisksScreen,
                'interfaces': EditNodeInterfacesScreen
            };
            this.changeScreen(screens[options[0]] || screens.list, options.slice(1));
        },
        render: function() {
            this.routeScreen(this.tabOptions);
            return this;
        }
    });

    Screen = Backbone.View.extend({
        constructorName: 'Screen',
        keepScrollPosition: false,
        goToNodeList: function() {
            app.navigate('#cluster/' + this.model.id + '/nodes', {trigger: true});
        },
        isLocked: function() {
            return !!this.model.tasks({group: 'deployment', status: 'running'}).length;
        },
        initButtons: function() {
            this.loadDefaultsButton = new Backbone.Model({disabled: false});
            this.cancelChangesButton = new Backbone.Model({disabled: true});
            this.applyChangesButton = new Backbone.Model({disabled: true});
        },
        setupButtonsBindings: function() {
            var bindings = {attributes: [{name: 'disabled', observe: 'disabled'}]};
            this.stickit(this.loadDefaultsButton, {'.btn-defaults': bindings});
            this.stickit(this.cancelChangesButton, {'.btn-revert-changes': bindings});
            this.stickit(this.applyChangesButton, {'.btn-apply': bindings});
        },
        updateButtonsState: function(state) {
            this.applyChangesButton.set('disabled', state);
            this.cancelChangesButton.set('disabled', state);
            this.loadDefaultsButton.set('disabled',  state);
        }
    });

    NodeListScreen = Screen.extend({
        constructorName: 'NodeListScreen',
        updateInterval: 20000,
        hasChanges: function() {
            return this instanceof ClusterNodesScreen ? false : !_.isEqual(this.nodes.pluck('pending_roles'), this.initialNodes.pluck('pending_roles'));
        },
        scheduleUpdate: function() {
            this.registerDeferred($.timeout(this.updateInterval).done(_.bind(this.update, this)));
        },
        update: function() {
            this.nodes.fetch().always(_.bind(this.scheduleUpdate, this));
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
            this.nodes.on('resize', function() {
                this.render();
                this.nodeList.filterNodes(this.nodeFilter.get('value'));
            }, this);
            if (this instanceof AddNodesScreen || this instanceof EditNodesScreen) {
                this.nodes.on('change:pending_roles', this.actualizePendingRoles, this);
                this.model.on('change:status', _.bind(function() {app.navigate('#cluster/' + this.model.id + '/nodes', {trigger: true});}, this));
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
            if (this instanceof EditNodesScreen) {
                this.$el.append($('<div>').addClass('alert').text($.t('cluster_page.nodes_tab.disk_configuration_reset_warning')));
            }
            var options = {nodes: this.nodes, screen: this};
            var managementPanel = new NodesManagementPanel(options);
            this.registerSubView(managementPanel);
            this.$el.append(managementPanel.render().el);
            if (this instanceof AddNodesScreen || this instanceof EditNodesScreen) {
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

    ClusterNodesScreen = NodeListScreen.extend({
        constructorName: 'ClusterNodesScreen',
        initialize: function(options) {
            _.defaults(this, options);
            this.nodes = this.model.get('nodes');
            var clusterId = this.model.id;
            this.nodes.fetch = function(options) {
                return this.constructor.__super__.fetch.call(this, _.extend({data: {cluster_id: clusterId}}, options));
            };
            this.nodes.on('change:checked', this.updateBatchActionsButtons, this);
            this.model.on('change:status', this.render, this);
            this.model.get('tasks').each(this.bindTaskEvents, this);
            this.model.get('tasks').on('add', this.onNewTask, this);
            this.constructor.__super__.initialize.apply(this, arguments);
            this.nodes.deferred = this.nodes.fetch().done(_.bind(this.render, this));
        },
        bindTaskEvents: function(task) {
            return task.match({group: ['deployment', 'network']}) ? task.on('change:status', this.render, this) : null;
        },
        onNewTask: function(task) {
            return this.bindTaskEvents(task) && this.render();
        }
    });

    AddNodesScreen = NodeListScreen.extend({
        constructorName: 'AddNodesScreen',
        removeRoles: function(node, checked, options) {
            if (!checked) {
                node.set({pending_roles: []}, {assign: true});
            }
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.nodes = new models.Nodes();
            this.nodes.fetch = function(options) {
                return this.constructor.__super__.fetch.call(this, _.extend({data: {cluster_id: ''}}, options));
            };
            this.constructor.__super__.initialize.apply(this, arguments);
            this.nodes.on('change:checked', this.removeRoles, this);
            this.nodes.deferred = this.nodes.fetch().done(_.bind(this.render, this));
        }
    });

    EditNodesScreen = NodeListScreen.extend({
        constructorName: 'EditNodesScreen',
        initialize: function(options) {
            _.defaults(this, options);
            var nodeIds = utils.deserializeTabOptions(this.screenOptions[0]).nodes.split(',').map(function(id) {return parseInt(id, 10);});
            this.nodes = new models.Nodes(this.model.get('nodes').getByIds(nodeIds));
            this.nodes.cluster = this.model;
            this.nodes.fetch = function(options) {
                return this.constructor.__super__.fetch.call(this, _.extend({data: {cluster_id: this.cluster.id}}, options));
            };
            this.nodes.parse = function(response) {
                return _.filter(response, function(node) {return _.contains(nodeIds, node.id);});
            };
            this.constructor.__super__.initialize.apply(this, arguments);
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
            if (!(this.screen instanceof AddNodesScreen || this.screen instanceof EditNodesScreen)) {
                this.cluster.save({grouping: grouping}, {patch: true, wait: true});
            }
            this.screen.nodeList.groupNodes(grouping);
        },
        showDeleteNodesDialog: function() {
            var nodes = new models.Nodes(this.screen.nodes.where({checked: true}));
            nodes.cluster = this.nodes.cluster;
            var dialog = new dialogViews.DeleteNodesDialog({nodes: nodes});
            app.page.tab.registerSubView(dialog);
            dialog.render();
        },
        applyChanges: function() {
            this.$('.btn-apply').prop('disabled', true);
            var nodes  = new models.Nodes(this.screen.nodes.where({checked: true}));
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
                    this.cluster.fetch();
                    app.navigate('#cluster/' + this.cluster.id + '/nodes', {trigger: true});
                    app.navbar.refresh();
                    app.page.removeFinishedTasks();
                    app.page.deploymentControl.render();
                }, this))
                .fail(_.bind(function() {
                    this.$('.btn-apply').prop('disabled', false);
                    utils.showErrorDialog({title: 'Unable to apply changes'});
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
            this.nodes.each(_.bind(function(node) {
                node.set({pending_roles: this.screen.initialNodes.get(node.id).get('pending_roles')}, {silent: true});
            }, this));
            app.navigate('#cluster/' + this.cluster.id + '/nodes', {trigger: true});
        },
        clearFilter: function() {
            this.screen.nodeFilter.set('value', '');
        },
        showUnavailableGroupConfigurationDialog: function (e) {
            var action = this.$(e.currentTarget).data('action');
            var dialog = new dialogViews.Dialog();
            app.page.registerSubView(dialog);
            dialog.render({title: $.t('cluster_page.nodes_tab.node_management_panel.cant_configure_' + action), message: $.t('cluster_page.nodes_tab.node_management_panel.' + action + '_configuration_warning')});
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            this.$el.html(this.template({
                nodes: this.nodes,
                cluster: this.cluster,
                edit: this.screen instanceof EditNodesScreen
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
        isZabbixSelectable: function(role) {
            var allocatedZabbix = this.cluster.get('nodes').filter(function(node) {return !node.get('pending_deletion') && node.hasRole('zabbix-server') && !_.contains(this.nodes.pluck('id'), node.id);}, this);
            return role.get('name') != 'zabbix-server' || ((this.isRoleSelected('zabbix-server') || this.screen.nodes.where({checked: true}).length <= 1) && !allocatedZabbix.length);
        },
        getListOfIncompatibleRoles: function(roles) {
            var forbiddenRoles = [];
            var release = this.cluster.get('release');
            _.each(roles, function(role) {
                forbiddenRoles = _.union(forbiddenRoles, release.get('roles_metadata')[role.get('name')].conflicts);
            });
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
                    var disabled = isControllerAssigned || isZabbixAssigned || !node.isSelectable() || this.screen instanceof EditNodesScreen || this.screen.isLocked();
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
                var dependencies = this.getRoleData(role.get('name')).depends;
                if (dependencies) {
                    var configModels = {settings: this.settings, cluster: this.cluster, default: this.settings};
                    var unavailable = false;
                    var unavailabityReasons = [];
                    _.each(dependencies, function(dependency){
                        var path = _.keys(dependency.condition)[0];
                        var value = dependency.condition[path];
                        if (utils.parseModelPath(path, configModels).get() != value) {
                            unavailable = true;
                            unavailabityReasons.push(dependency.warning);
                        }
                    });
                    if (unavailable) {
                        role.set({unavailable: true, unavailabityReason: unavailabityReasons.join(' ')});
                    }
                }
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
                    conflict: '',
                    checked: !!nodesWithRole.length && nodesWithRole.length == this.nodes.length,
                    indeterminate: !!nodesWithRole.length && nodesWithRole.length != this.nodes.length
                };
            }, this));
            this.collection.on('change:checked', this.handleChanges, this);
            this.settings = this.cluster.get('settings');
            (this.loading = this.settings.fetch({cache: true})).done(_.bind(this.checkRolesAvailability, this));
        },
        stickitRole: function (role) {
            var bindings = {};
            bindings['input[name=' + role.get('name') + ']'] = {
                observe: 'checked',
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
            var disabled = !this.filteredNodes.where({disabled: false}).length || roleAmountRestrictions || this.screen instanceof EditNodesScreen;
            this.selectAllCheckbox.set('disabled', disabled);
        },
        groupNodes: function(grouping) {
            if (_.isUndefined(grouping)) {
                grouping = this.screen instanceof AddNodesScreen ? 'hardware' : this.screen.tab.model.get('grouping');
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
                edit: this.screen instanceof EditNodesScreen
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
            var disabled = !availableNodes.length || roleAmountRestrictions || this.nodeList.screen instanceof EditNodesScreen;
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
            var nodeView = new Node({
                node: node,
                renameable: !this.nodeList.screen.isLocked(),
                group: this
            });
            this.registerSubView(nodeView);
            this.$('.nodes-group').append(nodeView.render().el);
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

    Node = Backbone.View.extend({
        template: _.template(nodeTemplate),
        roleTemplate: _.template(nodeRoleTemplate),
        templateHelpers: _.pick(utils, 'showDiskSize', 'showMemorySize'),
        renaming: false,
        events: {
            'click .node-renameable': 'startNodeRenaming',
            'keydown .name input': 'onNodeNameInputKeydown',
            'click .node-details': 'showNodeDetails',
            'click .btn-discard-role-changes': 'discardRoleChanges',
            'click .btn-discard-addition': 'discardAddition',
            'click .btn-discard-deletion': 'discardDeletion',
            'click .btn-view-logs': 'showNodeLogs'
        },
        bindings: {
            '.role-list': {
                observe: ['roles', 'pending_roles'],
                update: function($el) {
                    return $el.html(this.roleTemplate({
                        deployedRoles: this.sortRoles(this.node.get('roles')),
                        pendingRoles: this.sortRoles(this.node.get('pending_roles'))
                    }));
                }
            },
            '.node': {
                attributes: [{
                    name: 'class',
                    observe: 'checked',
                    onGet: function(value, options) {
                        return value ? 'node checked' : 'node';
                    }
                }]
            },
            '.node-checkbox input': {
                observe: 'checked',
                attributes: [{
                    name: 'disabled',
                    observe: 'disabled'
                }]
            },
            '.node-status-label': {
                observe: ['status', 'online', 'pending_addition', 'pending_deletion'],
                onGet: 'formatStatusLabel'
            },
            '.node-box': {
                attributes: [{
                    name: 'class',
                    observe: ['status', 'online', 'pending_addition', 'pending_deletion'],
                    onGet: 'formatNodePanelClass'
                }]
            },
            '.node-status': {
                attributes: [{
                    name: 'class',
                    observe: ['status', 'online', 'pending_addition', 'pending_deletion'],
                    onGet: 'formatStatusBlockClass'
                }]
            },
            '.progress': {
                attributes: [{
                    name: 'class',
                    observe: 'status',
                    onGet: function(value, options) {
                        var progressBarClass = value == 'deploying' ? 'progress-success' : value == 'provisioning' ? '' : 'hide';
                        return 'progress ' + progressBarClass;
                    }
                }]
            },
            '.bar': {
                observe: 'progress',
                update: function($el, value) {
                    value = _.max([value, 3]);
                    $el.css('width', value + '%');
                }
            },
            '.node-status i': {
                observe: 'status',
                visible: function(value) {
                    return !_.contains(['provisioning', 'deploying'], value);
                },
                attributes: [{
                    name: 'class',
                    observe: ['status', 'online', 'pending_addition', 'pending_deletion'],
                    onGet: 'formatStatusIconClass'
                }]
            },
            '.node-button button': {
                observe: 'cluster',
                visible: function(value) {
                    return !_.isUndefined(value) && value != '';
                },
                attributes: [{
                    name: 'class',
                    observe: ['pending_addition', 'pending_deletion', 'pending_roles'],
                    onGet: 'formatNodeButtonClass'
                },{
                    name: 'title',
                    observe: ['pending_addition', 'pending_deletion', 'pending_roles'],
                    onGet: 'formatNodeButtonTitle'
                }]
            },
            '.node-button i': {
                attributes: [{
                    name: 'class',
                    observe: ['pending_addition', 'pending_deletion', 'pending_roles'],
                    onGet: 'formatNodeButtonIcon'
                }]
            }
        },
        sortRoles: function(roles) {
            roles = roles || [];
            var preferredOrder = this.screen.tab.model.get('release').get('roles');
            return roles.sort(function(a, b) {
                return _.indexOf(preferredOrder, a) - _.indexOf(preferredOrder, b);
            });
        },
        defineNodeViewStatus: function() {
            return !this.node.get('online') ? 'offline' : this.node.get('pending_addition') ? 'pending_addition' : this.node.get('pending_deletion') ? 'pending_deletion' : this.node.get('status');
        },
        formatNodePanelClass: function(value, options) {
            var nodeClass = this.node.get('pending_deletion') ? 'node-delete' : this.node.get('pending_addition') ? 'node-new' : this.node.get('online') ? this.node.get('status') : 'node-offline';
            return 'node-box ' + nodeClass;
        },
        formatStatusIconClass: function(value, options) {
            var icons = {
                offline: 'icon-block',
                pending_addition: 'icon-ok-circle-empty',
                pending_deletion: 'icon-cancel-circle',
                ready: 'icon-ok',
                provisioned: 'icon-install',
                error: 'icon-attention',
                discover: 'icon-ok-circle-empty'
            };
            return icons[this.defineNodeViewStatus()] || '';
        },
        formatStatusBlockClass: function(value, options) {
            var classes = {
                offline: 'msg-offline',
                pending_addition: 'msg-ok',
                pending_deletion: 'msg-warning',
                ready: 'msg-ok',
                provisioning: 'provisioning',
                provisioned: 'msg-provisioned',
                deploying: 'deploying',
                error: 'msg-error',
                discover: 'msg-discover'
            };
            return 'node-status ' + classes[this.defineNodeViewStatus()];
        },
        formatStatusLabel: function(value) {
            var operatingSystem;
            try {
              operatingSystem = this.node.collection.cluster.get('release').get('operating_system');
            } catch (ignore) {}
            operatingSystem = operatingSystem || 'OS';
            var labels = {
                offline: $.t('cluster_page.nodes_tab.node.status.offline'),
                pending_addition: $.t('cluster_page.nodes_tab.node.status.pending_addition'),
                pending_deletion: $.t('cluster_page.nodes_tab.node.status.pending_deletion'),
                ready: $.t('cluster_page.nodes_tab.node.status.ready'),
                provisioning: $.t('cluster_page.nodes_tab.node.status.installing_os', {os: operatingSystem}),
                provisioned: $.t('cluster_page.nodes_tab.node.status.os_is_installed', {os: operatingSystem}),
                deploying: $.t('cluster_page.nodes_tab.node.status.installing_openstack'),
                error: $.t('cluster_page.nodes_tab.node.status.error'),
                discover: $.t('cluster_page.nodes_tab.node.status.discovered')
            };
            return labels[this.defineNodeViewStatus()] || '';
        },
        hasChanges: function() {
            return this.node.get('pending_addition') || this.node.get('pending_deletion') || (this.node.get('pending_roles') && this.node.get('pending_roles').length);
        },
        formatNodeButtonClass: function(value, options) {
            var btnClass = this.node.get('pending_addition') ? 'addition' : this.node.get('pending_deletion') ? 'deletion' : 'role-changes';
            return this.hasChanges() && !(this.screen instanceof EditNodesScreen) ? 'btn btn-link btn-discard-node-changes btn-discard-' + btnClass : 'btn btn-link btn-view-logs';
        },
        formatNodeButtonTitle: function(value, options) {
            var title = this.node.get('pending_addition') ? $.t('cluster_page.nodes_tab.node.status.discard_addition') : this.node.get('pending_deletion') ? $.t('cluster_page.nodes_tab.node.status.discard_deletion') : $.t('cluster_page.nodes_tab.node.status.discard_role_changes');
            return this.hasChanges() && !(this.screen instanceof EditNodesScreen) ? title : $.t('cluster_page.nodes_tab.node.status.view_logs');
        },
        formatNodeButtonIcon: function(value, options) {
            return this.hasChanges() && !(this.screen instanceof EditNodesScreen) ? 'icon-back-in-time' : 'icon-logs';
        },
        calculateNodeState: function() {
            this.node.set('disabled', !this.node.isSelectable() || this.screen instanceof EditNodesScreen || this.screen.isLocked());
            if (this.screen.isLocked()) {
                this.node.set('checked', false);
            }
        },
        startNodeRenaming: function() {
            if (!this.renameable || this.renaming) {return;}
            $('html').off(this.eventNamespace);
            $('html').on(this.eventNamespace, _.after(2, _.bind(function(e) {
                if (!$(e.target).closest(this.$('.name input')).length) {
                    this.endNodeRenaming();
                }
            }, this)));
            this.renaming = true;
            this.render();
            this.$('.name input').focus();
        },
        endNodeRenaming: function() {
            $('html').off(this.eventNamespace);
            this.renaming = false;
            this.render();
        },
        applyNewNodeName: function() {
            var name = $.trim(this.$('.name input').val());
            if (name && name != this.node.get('name')) {
                this.$('.name input').attr('disabled', true);
                this.node.save({name: name}, {patch: true, wait: true}).always(_.bind(this.endNodeRenaming, this));
            } else {
                this.endNodeRenaming();
            }
        },
        onNodeNameInputKeydown: function(e) {
            if (e.which == 13) {
                this.applyNewNodeName();
            } else if (e.which == 27) {
                this.endNodeRenaming();
            }
        },
        showNodeDetails: function(e) {
            e.preventDefault();
            var dialog = new dialogViews.ShowNodeInfoDialog({node: this.node});
            app.page.tab.registerSubView(dialog);
            dialog.render();
        },
        updateNode: function(data) {
            this.node.save(data, {patch: true, wait: true})
                .done(_.bind(function() {
                    this.screen.tab.model.fetch();
                    this.screen.tab.model.fetchRelated('nodes');
                    app.page.removeFinishedTasks();
                }, this))
                .fail(function() {utils.showErrorDialog({title: $.t('dialog.discard_changes.cant_discard')});});
        },
        discardRoleChanges: function(e) {
            e.preventDefault();
            var data = {pending_roles: []};
            if (this.node.get('pending_addition')) {
                data.cluster = null;
                data.pending_addition = false;
            }
            this.updateNode(data);
        },
        discardAddition: function(e) {
            e.preventDefault();
            this.updateNode({
                cluster_id: null,
                pending_addition: false,
                pending_roles: []
            });
        },
        discardDeletion: function(e) {
            e.preventDefault();
            this.updateNode({pending_deletion: false});
        },
        showNodeLogs: function() {
            var status = this.node.get('status');
            var error = this.node.get('error_type');
            var options = {type: 'remote', node: this.node.id};
            if (status == 'discover') {
                options.source = 'bootstrap/messages';
            } else if (status == 'provisioning' || status == 'provisioned' || (status == 'error' && error == 'provision')) {
                options.source = 'install/anaconda';
            } else if (status == 'deploying' || status == 'ready' || (status == 'error' && error == 'deploy')) {
                options.source = 'install/puppet';
            }
            app.navigate('#cluster/' + this.screen.tab.model.id + '/logs/' + utils.serializeTabOptions(options), {trigger: true});
        },
        beforeTearDown: function() {
            $('html').off(this.eventNamespace);
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.screen = this.group.nodeList.screen;
            this.eventNamespace = 'click.editnodename' + this.node.id;
            this.node.on('change:checked', function(node, checked, options) {
                this.screen.nodes.get(node.id).set('checked', checked);
            }, this);
            this.node.set('checked', this.screen instanceof EditNodesScreen || this.screen.nodes.get(this.node.id).get('checked') || false);
            this.node.on('change:status', this.calculateNodeState, this);
            this.node.on('change:disabled', this.group.calculateSelectAllDisabledState, this.group);
            if (!(this.screen instanceof ClusterNodesScreen)) {
                this.node.on('change:checked', this.screen.roles.handleChanges, this.screen.roles);
            }
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            this.$el.html(this.template(_.extend({
                node: this.node,
                renaming: this.renaming,
                renameable: this.renameable,
                edit: this.screen instanceof EditNodesScreen,
                locked: this.screen.isLocked()
            }, this.templateHelpers))).i18n();
            this.stickit(this.node);
            this.calculateNodeState();
            return this;
        }
    });

    EditNodeScreen = Screen.extend({
        constructorName: 'EditNodeScreen',
        keepScrollPosition: true,
        disableControls: function(disable) {
            this.updateButtonsState(disable || this.isLocked());
        },
        returnToNodeList: function() {
            if (this.hasChanges()) {
                this.tab.page.discardSettingsChanges({cb: _.bind(this.goToNodeList, this)});
            } else {
                this.goToNodeList();
            }
        },
        initialize: function(options) {
            _.defaults(this, options);
            var nodeIds = utils.deserializeTabOptions(this.screenOptions[0]).nodes.split(',').map(function(id) {return parseInt(id, 10);});
            this.nodes = new models.Nodes(this.model.get('nodes').getByIds(nodeIds));
        }
    });

    EditNodeDisksScreen = EditNodeScreen.extend({
        className: 'edit-node-disks-screen',
        constructorName: 'EditNodeDisksScreen',
        template: _.template(editNodeDisksScreenTemplate),
        events: {
            'click .btn-defaults': 'loadDefaults',
            'click .btn-revert-changes': 'revertChanges',
            'click .btn-apply:not(:disabled)': 'applyChanges',
            'click .btn-return:not(:disabled)': 'returnToNodeList'
        },
        hasChanges: function() {
            var disks = this.disks.toJSON();
            return !this.nodes.reduce(function(result, node) {
                return result && _.isEqual(disks, node.disks.toJSON());
            }, true);
        },
        hasValidationErrors: function() {
            var result = false;
            this.disks.each(function(disk) {result = result || disk.validationError || _.some(disk.get('volumes').models, 'validationError');}, this);
            return result;
        },
        isLocked: function() {
            var nodesAvailableForChanges = this.nodes.filter(function(node) {
                return node.get('pending_addition') || (node.get('status') == 'error' && node.get('error_type') == 'provision');
            });
            return !nodesAvailableForChanges.length || this.constructor.__super__.isLocked.apply(this);
        },
        checkForChanges: function() {
            this.updateButtonsState(this.isLocked());
            this.applyChangesButton.set('disabled', this.isLocked() || !this.hasChanges() || this.hasValidationErrors());
            this.cancelChangesButton.set('disabled', this.isLocked() || (!this.hasChanges() && !this.hasValidationErrors()));
        },
        loadDefaults: function() {
            this.disableControls(true);
            this.disks.fetch({url: _.result(this.nodes.at(0), 'url') + '/disks/defaults/'})
                .fail(_.bind(function() {utils.showErrorDialog({title: 'Disks configuration'});}, this));
        },
        revertChanges: function() {
            this.disks.reset(_.cloneDeep(this.nodes.at(0).disks.toJSON()), {parse: true});
        },
        applyChanges: function() {
            if (this.hasValidationErrors()) {
                return (new $.Deferred()).reject();
            }
            this.disableControls(true);
            return $.when.apply($, this.nodes.map(function(node) {
                    return Backbone.sync('update', this.disks, {url: _.result(node, 'url') + '/disks'});
                }, this))
                .done(_.bind(function() {
                    this.model.fetch();
                    var disks = this.disks.toJSON();
                    this.nodes.each(function(node) {
                        node.disks = new models.Disks(_.cloneDeep(disks), {parse: true});
                    }, this);
                    this.render();
                }, this))
                .fail(_.bind(function() {
                    this.checkForChanges();
                    utils.showErrorDialog({title: 'Disks configuration'});
                }, this));
        },
        mapVolumesColors: function() {
            this.volumesColors = {};
            var colors = [
                ['#23a85e', '#1d8a4d'],
                ['#3582ce', '#2b6ba9'],
                ['#eea616', '#c38812'],
                ['#1cbbb4', '#189f99'],
                ['#9e0b0f', '#870a0d'],
                ['#8f50ca', '#7a44ac'],
                ['#1fa0e3', '#1b88c1'],
                ['#85c329', '#71a623'],
                ['#7d4900', '#6b3e00']
            ];
            this.volumes.each(function(volume, index) {
                this.volumesColors[volume.get('name')] = colors[index];
            }, this);
        },
        initialize: function(options) {
            this.constructor.__super__.initialize.apply(this, arguments);
            if (this.nodes.length) {
                this.model.on('change:status', this.revertChanges, this);
                this.volumes = new models.Volumes([], {url: _.result(this.nodes.at(0), 'url') + '/volumes'});
                this.loading = $.when.apply($, this.nodes.map(function(node) {
                        node.disks = new models.Disks();
                        return node.disks.fetch({url: _.result(node, 'url') + '/disks'});
                    }, this).concat(this.volumes.fetch()))
                    .done(_.bind(function() {
                        this.disks = new models.Disks(_.cloneDeep(this.nodes.at(0).disks.toJSON()), {parse: true});
                        this.disks.on('sync', this.render, this);
                        this.disks.on('reset', this.render, this);
                        this.disks.on('error', this.checkForChanges, this);
                        this.mapVolumesColors();
                        this.render();
                    }, this))
                    .fail(_.bind(this.goToNodeList, this));
            } else {
                this.goToNodeList();
            }
            this.initButtons();
        },
        getDiskMetaData: function(disk) {
            var result;
            var disksMetaData = this.nodes.at(0).get('meta').disks;
            // try to find disk metadata by matching "extra" field
            // if at least one entry presents both in disk and metadata entry,
            // this metadata entry is for our disk
            var extra = disk.get('extra') || [];
            result = _.find(disksMetaData, function(diskMetaData) {
                if (_.isArray(diskMetaData.extra)) {
                    return _.intersection(diskMetaData.extra, extra).length;
                }
                return false;
            }, this);

            // if matching "extra" fields doesn't work, try to search by disk id
            if (!result) {
                result = _.find(disksMetaData, {disk: disk.id});
            }

            return result;
        },
        renderDisks: function() {
            this.tearDownRegisteredSubViews();
            this.$('.node-disks').html('');
            this.disks.each(function(disk) {
                var nodeDisk = new NodeDisk({
                    disk: disk,
                    diskMetaData: this.getDiskMetaData(disk),
                    screen: this
                });
                this.registerSubView(nodeDisk);
                this.$('.node-disks').append(nodeDisk.render().el);
            }, this);
        },
        render: function() {
            this.$el.html(this.template({
                nodes: this.nodes,
                locked: this.isLocked()
            })).i18n();
            if (this.loading && this.loading.state() != 'pending') {
                this.renderDisks();
                this.checkForChanges();
            }
            this.setupButtonsBindings();
            return this;
        }
    });

    NodeDisk = Backbone.View.extend({
        template: _.template(nodeDisksTemplate),
        volumeStylesTemplate: _.template(volumeStylesTemplate),
        templateHelpers: {
            sortEntryProperties: utils.sortEntryProperties,
            showDiskSize: utils.showDiskSize
        },
        events: {
            'click .toggle-volume': 'toggleEditDiskForm',
            'click .close-btn': 'deleteVolume',
            'click .use-all-allowed': 'useAllAllowedSpace'
        },
        diskFormBindings: {
            '.disk-form': {
                observe: 'visible',
                visible: true,
                visibleFn: function($el, isVisible, options) {
                    $el.collapse(isVisible ? 'show' : 'hide');
                }
            }
        },
        toggleEditDiskForm: function(e) {
            this.diskForm.set({visible: !this.diskForm.get('visible')});
        },
        getVolumeMinimum: function(name) {
            return this.screen.volumes.findWhere({name: name}).get('min_size');
        },
        checkForGroupsDeletionAvailability: function() {
            this.disk.get('volumes').each(function(volume) {
                var name = volume.get('name');
                this.$('.disk-visual .' + name + ' .close-btn').toggle(!this.screen.isLocked() && this.diskForm.get('visible') && volume.getMinimalSize(this.getVolumeMinimum(name)) <= 0);
            }, this);
        },
        updateDisk: function() {
            this.$('.disk-visual').removeClass('invalid');
            this.$('input').removeClass('error').parents('.volume-group').next().text('');
            this.$('.volume-group-error-message.common').text('');
            this.disk.get('volumes').each(function(volume) {
                volume.set({size: volume.get('size')}, {validate: true, minimum: this.getVolumeMinimum(volume.get('name'))});
            }, this); // volumes validation (minimum)
            this.disk.set({volumes: this.disk.get('volumes')}, {validate: true}); // disk validation (maximum)
            this.renderVisualGraph();
        },
        updateDisks: function(e) {
            this.updateDisk();
            _.invoke(_.omit(this.screen.subViews, this.cid), 'updateDisk', this);
            this.screen.checkForChanges();
        },
        deleteVolume: function(e) {
            var volumeName = this.$(e.currentTarget).parents('.volume-group').data('volume');
            var volume = this.disk.get('volumes').findWhere({name: volumeName});
            volume.set({size: 0});
        },
        useAllAllowedSpace: function(e) {
            var volumeName = this.$(e.currentTarget).parents('.volume-group').data('volume');
            var volume = this.disk.get('volumes').findWhere({name: volumeName});
            volume.set({size: _.max([0, this.disk.getUnallocatedSpace({skip: volumeName})])});
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.diskForm = new Backbone.Model({visible: false});
            this.diskForm.on('change:visible', this.checkForGroupsDeletionAvailability, this);
            this.disk.on('invalid', function(model, error) {
                this.$('.disk-visual').addClass('invalid');
                this.$('input').addClass('error');
                this.$('.volume-group-error-message.common').text(error);
            }, this);
            this.disk.get('volumes').each(function(volume) {
                volume.on('change:size', this.updateDisks, this);
                volume.on('change:size', function() {_.invoke(this.screen.subViews, 'checkForGroupsDeletionAvailability', this);}, this);
                volume.on('invalid', function(model, error) {
                    this.$('.disk-visual').addClass('invalid');
                    this.$('input[name=' + volume.get('name') + ']').addClass('error').parents('.volume-group').next().text(error);
                }, this);
            }, this);
        },
        renderVolume: function(name, width, size) {
            this.$('.disk-visual .' + name)
                .toggleClass('hidden-titles', width < 6)
                .css('width', width + '%')
                .find('.volume-group-size').text(utils.showDiskSize(size, 2));
        },
        renderVisualGraph: function() {
            if (!this.disk.get('volumes').some('validationError') && this.disk.isValid()) {
                var unallocatedWidth = 100;
                this.disk.get('volumes').each(function(volume) {
                    var width = this.disk.get('size') ? utils.floor(volume.get('size') / this.disk.get('size') * 100, 2) : 0;
                    unallocatedWidth -= width;
                    this.renderVolume(volume.get('name'), width, volume.get('size'));
                }, this);
                this.renderVolume('unallocated', unallocatedWidth, this.disk.getUnallocatedSpace());
            }
        },
        applyColors: function() {
            this.disk.get('volumes').each(function(volume) {
                var name = volume.get('name');
                var colors = this.screen.volumesColors[name];
                this.$('.disk-visual .' + name + ', .volume-group-box-flag.' + name).attr('style', this.volumeStylesTemplate({startColor: _.first(colors), endColor: _.last(colors)}));
            }, this);
        },
        setupVolumesBindings: function() {
            this.disk.get('volumes').each(function(volume) {
                var bindings = {};
                bindings['input[name=' + volume.get('name') + ']'] = {
                    events: ['keyup'],
                    observe: 'size',
                    getVal: function($el) {
                        return Number($el.autoNumeric('get'));
                    },
                    update: function($el, value) {
                        $el.autoNumeric('set', value);
                    }
                };
                this.stickit(volume, bindings);
            }, this);
        },
        render: function() {
            this.$el.html(this.template(_.extend({
                diskMetaData: this.diskMetaData,
                disk: this.disk,
                volumes: this.screen.volumes,
                locked: this.screen.isLocked()
            }, this.templateHelpers))).i18n();
            this.$('.disk-form').collapse({toggle: false});
            this.applyColors();
            this.renderVisualGraph();
            this.$('input').autoNumeric('init', {mDec: 0});
            this.stickit(this.diskForm, this.diskFormBindings);
            this.setupVolumesBindings();
            return this;
        }
    });

    EditNodeInterfacesScreen = EditNodeScreen.extend({
        className: 'edit-node-networks-screen',
        constructorName: 'EditNodeInterfacesScreen',
        template: _.template(editNodeInterfacesScreenTemplate),
        events: {
            'click .btn-bond:not(:disabled)': 'bondInterfaces',
            'click .btn-unbond:not(:disabled)': 'unbondInterfaces',
            'click .btn-defaults': 'loadDefaults',
            'click .btn-revert-changes:not(:disabled)': 'revertChanges',
            'click .btn-apply:not(:disabled)': 'applyChanges',
            'click .btn-return:not(:disabled)': 'returnToNodeList'
        },
        initButtons: function() {
            this.constructor.__super__.initButtons.apply(this);
            this.bondInterfacesButton = new Backbone.Model({disabled: true});
            this.unbondInterfacesButton = new Backbone.Model({disabled: true});
        },
        updateButtonsState: function(state) {
            this.constructor.__super__.updateButtonsState.apply(this, arguments);
            this.bondInterfacesButton.set('disabled', state);
            this.unbondInterfacesButton.set('disabled', state);
        },
        setupButtonsBindings: function() {
            this.constructor.__super__.setupButtonsBindings.apply(this);
            var bindings = {attributes: [{name: 'disabled', observe: 'disabled'}]};
            this.stickit(this.bondInterfacesButton, {'.btn-bond': bindings});
            this.stickit(this.unbondInterfacesButton, {'.btn-unbond': bindings});
        },
        isLocked: function() {
            var nodesAvailableForChanges = this.nodes.filter(function(node) {
                return node.get('pending_addition') || node.get('status') == 'error';
            });
            return !nodesAvailableForChanges.length || this.constructor.__super__.isLocked.apply(this);
        },
        hasChanges: function() {
            function getInterfaceConfiguration(interfaces) {
                return _.map(interfaces.toJSON(), function(ifc) {
                    return _.pick(ifc, ['assigned_networks', 'type', 'mode', 'slaves']);
                });
            }
            var currentConfiguration = getInterfaceConfiguration(this.interfaces);
            return !this.nodes.reduce(function(result, node) {
                return result && _.isEqual(currentConfiguration, getInterfaceConfiguration(node.interfaces));
            }, true);
        },
        checkForChanges: function() {
            this.updateButtonsState(this.isLocked() || !this.hasChanges());
            this.loadDefaultsButton.set('disabled', this.isLocked());
            this.updateBondingControlsState();
        },
        validateInterfacesSpeedsForBonding: function(interfaces) {
            var slaveInterfaces = _.flatten(_.invoke(interfaces, 'getSlaveInterfaces'), true);
            var speeds = _.invoke(slaveInterfaces, 'get', 'current_speed');
            // warn if not all speeds are the same or there are interfaces with unknown speed
            return _.uniq(speeds).length > 1 || !_.compact(speeds).length;
        },
        bondingAvailable: function() {
            return !this.isLocked() && this.model.get('net_provider') == 'neutron';
        },
        updateBondingControlsState: function() {
            var checkedInterfaces = this.interfaces.filter(function(ifc) {return ifc.get('checked') && !ifc.isBond();});
            var checkedBonds = this.interfaces.filter(function(ifc) {return ifc.get('checked') && ifc.isBond();});
            var creatingNewBond = checkedInterfaces.length >= 2 && !checkedBonds.length;
            var addingInterfacesToExistingBond = !!checkedInterfaces.length && checkedBonds.length == 1;
            var bondingPossible = creatingNewBond || addingInterfacesToExistingBond;
            var newBondWillHaveInvalidSpeeds = bondingPossible && this.validateInterfacesSpeedsForBonding(checkedBonds.concat(checkedInterfaces));
            var existingBondHasInvalidSpeeds = !!this.interfaces.find(function(ifc) {
                return ifc.isBond() && this.validateInterfacesSpeedsForBonding(ifc.getSlaveInterfaces());
            }, this);
            this.bondInterfacesButton.set('disabled', !bondingPossible);
            this.unbondInterfacesButton.set('disabled', checkedInterfaces.length || !checkedBonds.length);
            this.$('.bond-speed-warning').toggle(newBondWillHaveInvalidSpeeds || existingBondHasInvalidSpeeds);
        },
        bondInterfaces: function() {
            var interfaces = this.interfaces.filter(function(ifc) {return ifc.get('checked') && !ifc.isBond();});
            var bond = this.interfaces.find(function(ifc) {return ifc.get('checked') && ifc.isBond();});
            if (!bond) {
                // if no bond selected - create new one
                bond = new models.Interface({
                    type: 'bond',
                    name: this.interfaces.generateBondName(),
                    mode: models.Interface.prototype.bondingModes[0],
                    assigned_networks: new models.InterfaceNetworks(),
                    slaves: _.invoke(interfaces, 'pick', 'name')
                });
            } else {
                // adding interfaces to existing bond
                bond.set({slaves: bond.get('slaves').concat(_.invoke(interfaces, 'pick', 'name'))});
                // remove the bond to add it later and trigger re-rendering
                this.interfaces.remove(bond, {silent: true});
            }
            _.each(interfaces, function(ifc) {
                bond.get('assigned_networks').add(ifc.get('assigned_networks').models);
                ifc.get('assigned_networks').reset();
                ifc.set({checked: false});
            });
            this.interfaces.add(bond);
        },
        unbondInterfaces: function() {
            _.each(this.interfaces.where({checked: true}), function(bond) {
                // assign all networks from the bond to the first slave interface
                var ifc = this.interfaces.findWhere({name: bond.get('slaves')[0].name});
                ifc.get('assigned_networks').add(bond.get('assigned_networks').models);
                bond.get('assigned_networks').reset();
                bond.set({checked: false});
                this.interfaces.remove(bond);
            }, this);
        },
        loadDefaults: function() {
            this.disableControls(true);
            this.interfaces.fetch({url: _.result(this.nodes.at(0), 'url') + '/interfaces/default_assignment', reset: true})
                .fail(_.bind(function() {
                    utils.showErrorDialog({title: 'Unable to load default configuration'});
                }, this));
        },
        revertChanges: function() {
            this.interfaces.reset(_.cloneDeep(this.nodes.at(0).interfaces.toJSON()), {parse: true});
        },
        applyChanges: function() {
            this.disableControls(true);
            var bonds = this.interfaces.filter(function(ifc) {return ifc.isBond();});
            // bonding map contains indexes of slave interfaces
            // it is needed to build the same configuration for all the nodes
            // as interface names might be different, so we use indexes
            var bondingMap = _.map(bonds, function(bond) {
                return _.map(bond.get('slaves'), function(slave) {
                    return this.interfaces.indexOf(this.interfaces.findWhere(slave));
                }, this);
            }, this);
            return $.when.apply($, this.nodes.map(function(node) {
                // removing previously configured bonds
                var oldNodeBonds = node.interfaces.filter(function(ifc) {return ifc.isBond();});
                node.interfaces.remove(oldNodeBonds);
                // creating node-specific bonds without slaves
                var nodeBonds = _.map(bonds, function(bond) {
                    return new models.Interface(_.omit(bond.toJSON(), 'slaves'), {parse: true});
                }, this);
                node.interfaces.add(nodeBonds);
                // determining slaves using bonding map
                _.each(nodeBonds, function(bond, bondIndex) {
                    var slaveIndexes = bondingMap[bondIndex];
                    var slaveInterfaces = _.map(slaveIndexes, node.interfaces.at, node.interfaces);
                    bond.set({slaves: _.invoke(slaveInterfaces, 'pick', 'name')});
                });
                // assigning networks according to user choice
                node.interfaces.each(function(ifc, index) {
                    ifc.set({assigned_networks: new models.InterfaceNetworks(this.interfaces.at(index).get('assigned_networks').toJSON())});
                }, this);
                return Backbone.sync('update', node.interfaces, {url: _.result(node, 'url') + '/interfaces'});
            }, this))
            .always(_.bind(this.checkForChanges, this))
            .fail(function() {
                utils.showErrorDialog({title: 'Interfaces configuration'});
            });
        },
        initialize: function(options) {
            this.constructor.__super__.initialize.apply(this, arguments);
            if (this.nodes.length) {
                this.model.on('change:status', function() {
                    this.revertChanges();
                    this.render();
                    this.checkForChanges();
                }, this);
                this.networkConfiguration = new models.NetworkConfiguration();
                this.networkConfiguration.url = _.result(this.model, 'url') + '/network_configuration/' + this.model.get('net_provider');
                this.loading = $.when.apply($, this.nodes.map(function(node) {
                    node.interfaces = new models.Interfaces();
                    node.interfaces.url = _.result(node, 'url') + '/interfaces';
                    return node.interfaces.fetch();
                }, this).concat(this.networkConfiguration.fetch()))
                    .done(_.bind(function() {
                        this.interfaces = new models.Interfaces(this.nodes.at(0).interfaces.toJSON(), {parse: true});
                        this.interfaces.on('reset add remove change:slaves', this.render, this);
                        this.interfaces.on('sync change:mode', this.checkForChanges, this);
                        this.interfaces.on('change:checked reset', this.updateBondingControlsState, this);
                        // FIXME: modifying prototype to easily access NetworkConfiguration model
                        // should be reimplemented in a less hacky way
                        var networks = this.networkConfiguration.get('networks');
                        models.InterfaceNetwork.prototype.getFullNetwork = function() {
                            return networks.findWhere({name: this.get('name')});
                        };
                        var networkingParameters = this.networkConfiguration.get('networking_parameters');
                        models.Network.prototype.getVlanRange = function() {
                            if (!this.get('meta').neutron_vlan_range) {
                                var externalNetworkData = this.get('meta').ext_net_data;
                                var vlanStart = externalNetworkData ? networkingParameters.get(externalNetworkData[0]) : this.get('vlan_start');
                                return _.isNull(vlanStart) ? vlanStart : [vlanStart, externalNetworkData ? vlanStart + networkingParameters.get(externalNetworkData[1]) - 1 : vlanStart];
                            }
                            return networkingParameters.get('vlan_range');
                        };
                        this.render();
                    }, this))
                    .fail(_.bind(this.goToNodeList, this));
            } else {
                this.goToNodeList();
            }
            this.initButtons();
        },
        beforeTearDown: function() {
            delete models.InterfaceNetwork.prototype.getFullNetwork;
            delete models.Network.prototype.getVlanRange;
        },
        renderInterfaces: function() {
            this.tearDownRegisteredSubViews();
            this.$('.node-networks').html('');
            var slaveInterfaceNames = _.pluck(_.flatten(_.filter(this.interfaces.pluck('slaves'))), 'name');
            this.interfaces.each(_.bind(function(ifc) {
                if (!_.contains(slaveInterfaceNames, ifc.get('name'))) {
                    var nodeInterface = new NodeInterface({model: ifc, screen: this});
                    this.registerSubView(nodeInterface);
                    this.$('.node-networks').append(nodeInterface.render().el);
                }
            }, this));
            // if any errors found disable apply button
            _.each(this.interfaces.invoke('validate'), _.bind(function(interfaceValidationResult) {
                if (!_.isEmpty(interfaceValidationResult)) {
                    this.applyChangesButton.set('disabled', true);
                }
            }, this));
        },
        render: function() {
            this.$el.html(this.template({
                nodes: this.nodes,
                locked: this.isLocked(),
                bondingAvailable: this.bondingAvailable()
            })).i18n();
            if (this.loading && this.loading.state() != 'pending') {
                this.renderInterfaces();
                this.checkForChanges();
            }
            this.setupButtonsBindings();
            return this;
        }
    });

    NodeInterface = Backbone.View.extend({
        template: _.template(nodeInterfaceTemplate),
        templateHelpers: _.pick(utils, 'showBandwidth'),
        events: {
            'sortremove .logical-network-box': 'dragStart',
            'sortstart .logical-network-box': 'dragStart',
            'sortreceive .logical-network-box': 'dragStop',
            'sortstop .logical-network-box': 'dragStop',
            'sortactivate .logical-network-box': 'dragActivate',
            'sortdeactivate .logical-network-box': 'dragDeactivate',
            'sortover .logical-network-box': 'updateDropTarget',
            'click .btn-remove-interface': 'removeInterface'
        },
        bindings: {
            'input[type=checkbox]': {
                observe: 'checked'
            },
            'select[name=mode]': {
                observe: 'mode',
                selectOptions: {
                    collection: function() {
                        return _.map(models.Interface.prototype.bondingModes, function(mode) {
                            return {value: mode, label: $.t('cluster_page.nodes_tab.configure_interfaces.bonding_modes.' + mode, {defaultValue: mode})};
                        });
                    }
                }
            }
        },
        removeInterface: function(e) {
            var slaveInterfaceId = parseInt($(e.currentTarget).data('interface-id'), 10);
            var slaveInterface = this.screen.interfaces.get(slaveInterfaceId);
            this.model.set('slaves', _.reject(this.model.get('slaves'), {name: slaveInterface.get('name')}));
        },
        dragStart: function(event, ui) {
            var networkNames = $(ui.item).find('.logical-network-item').map(function(index, el) {
                return $(el).data('name');
            }).get();
            this.screen.draggedNetworks = this.model.get('assigned_networks').filter(function(network) {
                return _.contains(networkNames, network.get('name'));
            });
            if (event.type == 'sortstart') {
                this.updateDropTarget();
            } else if (event.type == 'sortremove') {
                this.model.get('assigned_networks').remove(this.screen.draggedNetworks);
            }
        },
        dragStop: function(event, ui) {
            if (event.type == 'sortreceive') {
                this.model.get('assigned_networks').add(this.screen.draggedNetworks);
            }
            this.render();
            this.screen.draggedNetworks = null;
        },
        updateDropTarget: function(event) {
            this.screen.dropTarget = this;
        },
        checkIfEmpty: function() {
            this.$('.network-help-message').toggle(!this.model.get('assigned_networks').length && !this.screen.isLocked());
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.model.get('assigned_networks').on('add remove', this.checkIfEmpty, this);
            this.model.get('assigned_networks').on('add remove', this.screen.checkForChanges, this.screen);
        },
        handleValidationErrors: function() {
            var validationResult = this.model.validate();
            if (validationResult.length) {
                this.screen.applyChangesButton.set('disabled', true);
                _.each(validationResult, _.bind(function(error) {
                    this.$('.physical-network-box[data-name=' + this.model.get('name') + ']')
                        .addClass('nodrag')
                        .next('.network-box-error-message').text(error);
                }, this));
            }
        },
        render: function() {
            this.$el.html(this.template(_.extend({
                ifc: this.model,
                locked: this.screen.isLocked(),
                bondingAvailable: this.screen.bondingAvailable()
            }, this.templateHelpers))).i18n();
            this.checkIfEmpty();
            this.$('.logical-network-box').sortable({
                connectWith: '.logical-network-box',
                items: '.logical-network-group:not(.disabled)',
                containment: this.screen.$('.node-networks'),
                disabled: this.screen.isLocked()
            }).disableSelection();
            this.handleValidationErrors();
            this.stickit(this.model);
            return this;
        }
    });
    return NodesTab;
});
