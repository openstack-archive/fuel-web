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
    'text!templates/cluster/edit_node_disks.html',
    'text!templates/cluster/node_disk.html',
    'text!templates/cluster/volume_style.html',
    'text!templates/cluster/edit_node_interfaces.html',
    'text!templates/cluster/node_interface.html'
],
function(utils, models, commonViews, dialogViews, nodesManagementPanelTemplate, assignRolesPanelTemplate, nodeListTemplate, nodeGroupTemplate, nodeTemplate, editNodeDisksScreenTemplate, nodeDisksTemplate, volumeStylesTemplate, editNodeInterfacesScreenTemplate, nodeInterfaceTemplate) {
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
            var newScreen = new NewScreenView(options);
            var oldScreen = this.screen;
            if (oldScreen) {
                if (oldScreen.keepScrollPosition) {
                    this.scrollPositions[oldScreen.constructorName] = $(window).scrollTop();
                }
                oldScreen.$el.fadeOut('fast', _.bind(function() {
                    oldScreen.tearDown();
                    newScreen.render();
                    newScreen.$el.hide().fadeIn('fast');
                    this.$el.html(newScreen.el);
                    if (newScreen.keepScrollPosition && this.scrollPositions[newScreen.constructorName]) {
                        $(window).scrollTop(this.scrollPositions[newScreen.constructorName]);
                    }
                }, this));
            } else {
                this.$el.html(newScreen.render().el);
            }
            this.screen = newScreen;
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
            return !!this.model.task('deploy', 'running');
        },
        initButtons: function() {
            this.loadDefaultsButton = new Backbone.Model({disabled: false});
            this.cancelChangesButton = new Backbone.Model({disabled: true});
            this.applyChangesButton = new Backbone.Model({disabled: true});
        },
        setupButtonsBindings: function() {
            var bindings = {
                attributes: [{
                    name: 'disabled',
                    observe: 'disabled',
                    onGet: function(value) {
                        return _.isUndefined(value) ? false : value;
        }
                }]
            };
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
            return this instanceof ClusterNodesScreen ? false : !_.isEqual(this.nodes.map(function(node) {return node.get('pending_roles') || [];}), this.initialRoles);
        },
        scheduleUpdate: function() {
            this.registerDeferred($.timeout(this.updateInterval).done(_.bind(this.update, this)));
        },
        update: function() {
            this.nodes.fetch().always(_.bind(this.scheduleUpdate, this));
        },
        calculateApplyButtonState: function() {
            this.$('.btn-apply').prop('disabled', !this.hasChanges());
        },
        updateBatchActionsButtons: function() {
            var nodes = new models.Nodes(this.nodes.where({checked: true}));
            this.$('.btn-group-congiration').prop('disabled', !nodes.length);
            this.$('.btn-delete-nodes').toggle(!!this.nodes.where({checked: true, pending_deletion: false}).length);
            this.$('.btn-add-nodes').css('display', nodes.length ? 'none' : 'block');
            var notDeployedSelectedNodes = this.nodes.where({checked: true, online: true, pending_addition: true});
            this.$('.btn-edit-nodes').toggle(!!notDeployedSelectedNodes.length && notDeployedSelectedNodes.length == nodes.length);
            this.$('.btn-edit-nodes').attr('href', '#cluster/' + this.model.id + '/nodes/edit/' + utils.serializeTabOptions({nodes: _.pluck(notDeployedSelectedNodes, 'id')}));
            // check selected nodes for group configuration availability
            var noDisksConflict = true;
            nodes.each(function(node) {
                var noRolesConflict = !_.difference(_.union(nodes.at(0).get('roles'), nodes.at(0).get('pending_roles')), _.union(node.get('roles'), node.get('pending_roles'))).length;
                noDisksConflict = noDisksConflict && noRolesConflict && _.isEqual(nodes.at(0).resource('disks'), node.resource('disks'));
            });
            this.$('.btn-configure-disks').toggleClass('conflict', !noDisksConflict);
            this.$('.btn-configure-interfaces').toggleClass('conflict', _.uniq(nodes.map(function(node) {return node.resource('interfaces');})).length > 1);
        },
        initialize: function() {
            this.nodes.on('resize', this.render, this);
            if (this instanceof AddNodesScreen || this instanceof EditNodesScreen) {
                this.model.on('change:status', _.bind(function() {app.navigate('#cluster/' + this.model.id + '/nodes', {trigger: true});}, this));
            }
            this.scheduleUpdate();
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            this.$el.html('');
            if (this instanceof EditNodesScreen) {
                this.$el.append($('<div>').addClass('alert').text('Disk configuration will be reset to default after roles change'));
            }
            var managementPanel = new NodesManagementPanel({screen: this});
            this.registerSubView(managementPanel);
            this.$el.append(managementPanel.render().el);
            if (this instanceof AddNodesScreen || this instanceof EditNodesScreen) {
                this.roles = new AssignRolesPanel({screen: this});
                this.registerSubView(this.roles);
                this.$el.append(this.roles.render().el);
            }
            this.nodeList = new NodeList({
                nodes: this.nodes,
                screen: this
            });
            this.registerSubView(this.nodeList);
            this.$el.append(this.nodeList.render().el);
            this.nodeList.calculateSelectAllCheckedState();
            this.nodeList.calculateSelectAllDisabledState();

            return this;
        }
    });

    ClusterNodesScreen = NodeListScreen.extend({
        constructorName: 'ClusterNodesScreen',
        initialize: function(options) {
            _.defaults(this, options);
            this.nodes = this.model.get('nodes');
            this.nodes.cluster = this.model;
            var clusterId = this.model.id;
            this.nodes.fetch = function(options) {
                return this.constructor.__super__.fetch.call(this, _.extend({data: {cluster_id: clusterId}}, options));
            };
            this.model.on('change:status', this.render, this);
            this.model.get('tasks').each(this.bindTaskEvents, this);
            this.model.get('tasks').on('add', this.onNewTask, this);
            this.constructor.__super__.initialize.apply(this, arguments);
            this.nodes.fetch();
        },
        bindTaskEvents: function(task) {
            return (task.get('name') == 'deploy' || task.get('name') == 'verify_networks') ? task.on('change:status', this.render, this) : null;
        },
        onNewTask: function(task) {
            return this.bindTaskEvents(task) && this.render();
        }
    });

    AddNodesScreen = NodeListScreen.extend({
        constructorName: 'AddNodesScreen',
        initialize: function(options) {
            _.defaults(this, options);
            this.nodes = new models.Nodes();
            this.nodes.fetch = function(options) {
                return this.constructor.__super__.fetch.call(this, _.extend({data: {cluster_id: ''}}, options));
            };
            this.constructor.__super__.initialize.apply(this, arguments);
            this.nodes.parse = function(response) {
                return _.map(response, function(node) {
                    return _.omit(node, 'pending_roles');
                });
            };
            this.nodes.fetch().done(_.bind(function() {
                this.nodes.each(function(node) {node.set({pending_roles: []}, {silent: true});});
                this.render();
            }, this));
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
                return _.map(_.filter(response, function(node) {return _.contains(nodeIds, node.id);}), function(node) {
                    return _.omit(node, 'pending_roles');
                });
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
            'click .btn-group-congiration.conflict' : 'showUnavailableGroupConfigurationDialog'
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.nodes = this.screen.nodes;
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
            var nodes = new models.Nodes(this.nodes.where({checked: true}));
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
        showUnavailableGroupConfigurationDialog: function (e) {
            var action = this.$(e.currentTarget).data('action');
            var messages = {
                'disks': 'Only nodes with identical disk capacities can be configured together in the same action.',
                'interfaces': 'Only nodes with an identical number of network interfaces can be configured together in the same action.'
            };
            var dialog = new dialogViews.Dialog();
            app.page.registerSubView(dialog);
            dialog.render({title: 'Unable to configure ' + action, message: messages[action]});
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            this.$el.html(this.template({
                nodes: this.nodes,
                cluster: this.cluster,
                edit: this.screen instanceof EditNodesScreen,
                locked: this.screen.isLocked()
            })).i18n();
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
                    node.set({pending_roles: pending_roles});
                });
            }, this);
        },
        isControllerRoleSelected: function() {
            return this.collection.filter(function(role) {return role.get('name') == 'controller' && (role.get('checked') || role.get('indeterminate'));}).length;
        },
        canControllerBeSelected: function(role) {
            var allocatedController = this.cluster.get('nodes').filter(function(node) {return !node.get('pending_deletion') && node.hasRole('controller') && !_.contains(this.nodes.pluck('id'), node.id);}, this);
            return role.get('name') == 'controller' && this.cluster.get('mode') == 'multinode' && ((this.screen.nodes.length > 1 && (!this.isControllerRoleSelected() && this.nodes.length > 1)) || allocatedController.length);
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
                var selectedRoles = this.collection.filter(function(role) {return role.get('checked') || role.get('indeterminate');});
                role.set('disabled', !this.screen.nodes.length || this.canControllerBeSelected(role) || _.contains(this.getListOfIncompatibleRoles(selectedRoles), role.get('name')));
            }, this);
            if (this.cluster.get('mode') == 'multinode' && this.screen.nodeList) {
                var controllerNode = this.nodes.filter(function(node) {return node.hasRole('controller');})[0];
                _.each(this.screen.nodes.where({checked: false}), function(node) {
                    node.set('disabled', (this.isControllerRoleSelected() && controllerNode && controllerNode.id != node.id) || !node.isSelectable() || this.screen instanceof EditNodesScreen || this.screen.isLocked());
                }, this);
                _.invoke(this.screen.nodeList.subViews, 'calculateSelectAllDisabledState', this);
            }
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.cluster = this.screen.tab.model;
            this.nodes = new models.Nodes(this.screen.nodes.where({checked: true}));
            this.collection = new Backbone.Collection(_.map(this.cluster.availableRoles(), function(role) {
                var roleData = this.cluster.get('release').get('roles_metadata')[role];
                var nodesWithRole = this.nodes.filter(function(node) {return node.hasRole(role);});
                return {
                    name: role,
                    label: roleData.name,
                    description: roleData.description,
                    disabled: false,
                    checked: !!nodesWithRole.length && nodesWithRole.length == this.nodes.length,
                    indeterminate: !!nodesWithRole.length && nodesWithRole.length != this.nodes.length
                };
            }, this));
            this.collection.on('change:checked', this.handleChanges, this);
        },
        defineConflict: function(value, options) {
            return value ? this.canControllerBeSelected(options.stickitChange) ? $.t('cluster_page.nodes_tab.one_controller_restriction') : $.t('cluster_page.nodes_tab.incompatible_roles_warning') : '';
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
                    observe: 'indeterminate',
                    onGet: _.bind(function(value) {
                        this.$('input[name=' + role.get('name') + ']').prop('indeterminate', value);
                    }, this)
                }]
            };
            bindings['.role-conflict.' + role.get('name')] = {
                observe: 'disabled',
                stickitChange: role,
                onGet: this.defineConflict
            };
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
                stickitChange: true,
                attributes: [{
                    name: 'disabled',
                    observe: 'disabled'
                }]
            }
        },
        selectNodes: function(model, value, options) {
            if (options.stickitChange) {
                _.each(this.subViews, function(nodeGroup) {
                    if (!nodeGroup.selectAllCheckbox.get('disabled')) {
                        nodeGroup.selectAllCheckbox.set('checked', value);
                    }
                });
                _.each(this.nodes.where({disabled: false}), function(node) {
                    node.set('checked', value);
                });
            }
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
            var availableNodes = this.nodes.filter(function(node) {return node.isSelectable();});
            this.selectAllCheckbox.set('checked', availableNodes.length && this.nodes.where({checked: true}).length == availableNodes.length);
        },
        calculateSelectAllDisabledState: function() {
            var availableNodes = this.nodes.where({disabled: false, checked: false});
            var disabled = !availableNodes.length || (this.screen.roles && this.screen.roles.isControllerRoleSelected() && availableNodes.length > 1) || this.screen instanceof EditNodesScreen || this.screen.isLocked();
            this.selectAllCheckbox.set('disabled', disabled);
        },
        groupNodes: function(attribute) {
            if (_.isUndefined(attribute)) {
                attribute = this.screen instanceof AddNodesScreen ? 'hardware' : this.screen.tab.model.get('grouping');
            }
            if (attribute == 'roles') {
                var rolesMetadata = this.screen.tab.model.get('release').get('roles_metadata');
                this.nodeGroups = this.nodes.groupBy(function(node) {return  _.map(node.sortedRoles(), function(role) {return rolesMetadata[role].name;}).join(' + ');});
            } else if (attribute == 'hardware') {
                this.nodeGroups = this.nodes.groupBy(function(node) {
                    return $.t('cluster_page.nodes_tab.node.hardware.hdd') + ': ' + utils.showDiskSize(node.resource('hdd')) + ' \u00A0 ' + $.t('cluster_page.nodes_tab.node.hardware.ram') + ': ' + utils.showMemorySize(node.resource('ram'));
                });
            } else {
                this.nodeGroups = this.nodes.groupBy(function(node) {
                    return _.union(node.get('roles'), node.get('pending_roles')).join(' + ') + ' + ' + $.t('cluster_page.nodes_tab.node.hardware.hdd') + ': ' + utils.showDiskSize(node.resource('hdd')) + ' \u00A0 ' + $.t('cluster_page.nodes_tab.node.hardware.ram') + ': ' + utils.showMemorySize(node.resource('ram'));
                });
            }
            this.renderNodeGroups();
            this.screen.updateBatchActionsButtons();
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.screen.initialRoles = this.nodes.map(function(node) {return node.get('pending_roles') || [];});
            this.eventNamespace = 'click.click-summary-panel';
            this.selectAllCheckbox = new Backbone.Model({
                checked: false,
                disabled: false
            });
            this.selectAllCheckbox.on('change:checked', this.selectNodes, this);
        },
        renderNodeGroups: function() {
            this.$('.nodes').html('');
            _.each(_.keys(this.nodeGroups).sort(), function(groupLabel) {
                var nodeGroupView = new NodeGroup({
                    groupLabel: groupLabel,
                    nodes: new models.Nodes(this.nodeGroups[groupLabel]),
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
                nodes: this.nodes,
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
                stickitChange: true,
                attributes: [{
                    name: 'disabled',
                    observe: 'disabled'
                }]
            }
        },
        selectNodes: function(model, value, options) {
            if (options.stickitChange) {
                _.each(this.nodes.where({disabled: false}), function(node) {
                    node.set('checked', value);
                });
                this.nodeList.calculateSelectAllCheckedState();
            }
        },
        calculateSelectAllCheckedState: function() {
            var availableNodes = this.nodes.filter(function(node) {return node.isSelectable();});
            this.selectAllCheckbox.set('checked', availableNodes.length && this.nodes.where({checked: true}).length == availableNodes.length);
        },
        calculateSelectAllDisabledState: function() {
            var availableNodes = this.nodes.where({disabled: false});
            var disabled = !availableNodes.length || (this.nodeList.screen.roles && this.nodeList.screen.roles.isControllerRoleSelected() && availableNodes.length > 1) || this.nodeList.screen instanceof EditNodesScreen || this.nodeList.screen.isLocked();
            this.selectAllCheckbox.set('disabled', disabled);
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.selectAllCheckbox = new Backbone.Model({
                checked: false,
                disabled: false
            });
            this.selectAllCheckbox.on('change:checked', this.selectNodes, this);
            this.selectAllCheckbox.on('change:disabled', this.nodeList.calculateSelectAllDisabledState, this.nodeList);
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
                onGet: 'formatRoleList',
                updateMethod: 'html'
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
                stickitChange: true,
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
                visible: function(value) {
                    return !_.contains(['provisioning', 'deploying'], this.node.get('status'));
                },
                updateView: true,
                attributes: [{
                    name: 'class',
                    observe: ['status', 'online', 'pending_addition', 'pending_deletion'],
                    onGet: 'formatStatusIconClass'
                }]
            },
            '.node-button button': {
                observe: ['cluster'],
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
        formatRoleList: function() {
            var deployedRoleList = '<ul class="roles"><li>' + this.sortRoles(this.node.get('roles')).join('</li><li>') + '</li></ul>';
            var pendingRoleList = '<ul class="pending-roles"><li>' + this.sortRoles(this.node.get('pending_roles')).join('</li><li>') + '</li></ul>';
            return _.union(this.node.get('roles'), this.node.get('pending_roles')).length ? deployedRoleList + pendingRoleList : $.t('cluster_page.nodes_tab.node.unallocated');
        },
        sortRoles: function(roles) {
            roles = roles || [];
            var preferredOrder = app.page.tab.model.get('release').get('roles');
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
            } catch(e){}
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
        onNodeSelection: function(node, checked, options) {
            if (options.stickitChange) {
                this.group.calculateSelectAllCheckedState();
                this.group.nodeList.calculateSelectAllCheckedState();
            }
            if (!checked) {
                node.set({pending_roles: this.initialRoles});
            }
            if (this.screen instanceof AddNodesScreen || this.screen instanceof EditNodesScreen) {
                this.screen.roles.handleChanges();
            } else {
                this.screen.updateBatchActionsButtons();
            }
        },
        calculateNodeDisabledState: function() {
            this.node.set('disabled', !this.node.isSelectable() || this.screen instanceof EditNodesScreen || this.screen.isLocked());
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
        showNodeDetails: function() {
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
        discardRoleChanges: function() {
            var data = {pending_roles: []};
            if (this.node.get('pending_addition')) {
                data.cluster = null;
                data.pending_addition = false;
            }
            this.updateNode(data);
        },
        discardAddition: function() {
            this.updateNode({
                cluster: null,
                pending_addition: false,
                pending_roles: []
            });
        },
        discardDeletion: function() {
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
        uncheckNode: function() {
            this.node.set('checked', false);
            this.calculateNodeDisabledState();
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.screen = this.group.nodeList.screen;
            this.eventNamespace = 'click.editnodename' + this.node.id;
            this.node.set('checked', this.screen instanceof EditNodesScreen);
            this.node.on('change:name', this.render, this);
            this.node.on('change:checked change:online', this.onNodeSelection, this);
            this.node.on('change:pending_deletion change:status change:online', this.calculateNodeDisabledState, this);
            this.node.on('change:disabled', this.group.calculateSelectAllDisabledState, this.group);
            this.node.on('change:pending_deletion', this.uncheckNode, this);
            this.initialRoles = this.node.get('pending_roles');
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
            this.calculateNodeDisabledState();
            return this;
        }
    });

    EditNodeScreen = Screen.extend({
        constructorName: 'EditNodeScreen',
        keepScrollPosition: true,
        disableControls: function(disable) {
            this.$('.btn, input').attr('disabled', disable || this.isLocked());
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
        disableControls: function(disable) {
            this.updateButtonsState(disable || this.isLocked());
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
            var forbiddenNodes = _.union(this.nodes.where({pending_addition: true}), this.nodes.where({status: 'error', error_type: 'provision'})).length;
            return !forbiddenNodes || this.constructor.__super__.isLocked.apply(this);
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
        renderDisks: function() {
            this.tearDownRegisteredSubViews();
            this.$('.node-disks').html('');
            this.disks.each(function(disk) {
                var nodeDisk = new NodeDisk({
                    disk: disk,
                    diskMetaData: _.find(this.nodes.at(0).get('meta').disks, {disk: disk.id}),
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
            sortEntryProperties: function(entry) {
                var properties = _.keys(entry);
                if (_.has(entry, 'name')) {
                    properties = ['name'].concat(_.keys(_.omit(entry, ['name'])));
                }
                return properties;
            },
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
                volume.on('change:size', this.checkForGroupsDeletionAvailability, this);
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
            if (!this.disk.get('volumes').some('validationError') && !this.disk.validationError) {
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
            'click .btn-defaults': 'loadDefaults',
            'click .btn-revert-changes:not(:disabled)': 'revertChanges',
            'click .btn-apply:not(:disabled)': 'applyChanges',
            'click .btn-return:not(:disabled)': 'returnToNodeList'
        },
        disableControls: function(disable) {
            this.updateButtonsState(disable || this.isLocked());
        },
        hasChanges: function() {
            var noChanges = true;
            var networks = this.interfaces.getAssignedNetworks();
            this.nodes.each(function(node) {
                noChanges = noChanges && _.isEqual(networks, node.interfaces.getAssignedNetworks());
            }, this);
            return !noChanges;
        },
        isLocked: function() {
            var forbiddenNodes = this.nodes.filter(function(node) {return node.get('pending_addition') || node.get('status') == 'error';});
            return !forbiddenNodes.length || this.constructor.__super__.isLocked.apply(this);
        },
        checkForChanges: function() {
            this.updateButtonsState(this.isLocked() || !this.hasChanges());
            this.loadDefaultsButton.set('disabled', this.isLocked());
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
            return $.when.apply($, this.nodes.map(function(node) {
                    node.interfaces.each(function(ifc, index) {
                        ifc.set({assigned_networks: new models.InterfaceNetworks(this.interfaces.at(index).get('assigned_networks').toJSON())});
                    }, this);
                    var interfaces = new models.Interfaces(node.interfaces.toJSON());
                    interfaces.toJSON = _.bind(function() {
                        return interfaces.map(function(ifc, index) {
                            return _.pick(ifc.attributes, 'id', 'assigned_networks');
                        }, this);
                    }, this);
                    return Backbone.sync('update', interfaces, {url: _.result(node, 'url') + '/interfaces'});
                }, this))
                .done(_.bind(function() {
                    this.checkForChanges();
                }, this))
                .fail(_.bind(function() {
                    this.checkForChanges();
                    utils.showErrorDialog({title: 'Interfaces configuration'});
                }, this));
        },
        initialize: function(options) {
            this.constructor.__super__.initialize.apply(this, arguments);
            if (this.nodes.length) {
                this.model.on('change:status', function() {
                    this.revertChanges();
                    this.render();
                    this.checkForChanges();
                }, this);
                $.when.apply($, this.nodes.map(function(node) {
                    node.interfaces = new models.Interfaces();
                    return node.interfaces.fetch({url: _.result(node, 'url') + '/interfaces'});
                }, this))
                .done(_.bind(function() {
                    this.interfaces = new models.Interfaces(this.nodes.at(0).interfaces.toJSON(), {parse: true});
                    this.interfaces.on('reset', this.render, this);
                    this.interfaces.on('sync', this.checkForChanges, this);
                    var networkConfiguration = new models.NetworkConfiguration();
                    this.loading = networkConfiguration
                        .fetch({url: _.result(this.model, 'url') + '/network_configuration/' + this.model.get('net_provider')})
                        .done(_.bind(function() {
                            // FIXME(vk): modifying models prototypes to use vlan data from NetworkConfiguration
                            // this mean that these models cannot be used safely in places other than this view
                            // helper function for template to get vlan_start NetworkConfiguration
                            models.InterfaceNetwork.prototype.vlanStart = function() {
                                return networkConfiguration.get('networks').findWhere({name: this.get('name')}).get('vlan_start');
                            };
                            models.InterfaceNetwork.prototype.amount = function() {
                                return networkConfiguration.get('networks').findWhere({name: this.get('name')}).get('amount');
                            };
                            this.render();
                        }, this))
                        .fail(_.bind(this.goToNodeList, this));
                }, this));
            } else {
                this.goToNodeList();
            }
            this.initButtons();
        },
        renderInterfaces: function() {
            this.tearDownRegisteredSubViews();
            this.$('.node-networks').html('');
            this.interfaces.each(_.bind(function(ifc) {
                var nodeInterface = new NodeInterface({model: ifc, screen: this});
                this.registerSubView(nodeInterface);
                this.$('.node-networks').append(nodeInterface.render().el);
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
                locked: this.isLocked()
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
            'sortover .logical-network-box': 'updateDropTarget'
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
        draggedNetworksAllowed: function() {
            var dragged = _.invoke(this.screen.draggedNetworks, 'get', 'name');
            var allowed = this.model.get('allowed_networks').pluck('name');
            return _.intersection(dragged, allowed).length == dragged.length;
        },
        checkIfEmpty: function() {
            this.$('.network-help-message').toggle(!this.model.get('assigned_networks').length && !this.screen.isLocked());
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.model.get('assigned_networks').on('add remove', this.checkIfEmpty, this);
            this.model.get('assigned_networks').on('add remove', this.screen.checkForChanges, this.screen);
        },
        render: function() {
            this.$el.html(this.template(_.extend({ifc: this.model}, this.templateHelpers))).i18n();
            this.checkIfEmpty();
            this.$('.logical-network-box').sortable({
                connectWith: '.logical-network-box',
                items: '.logical-network-group:not(.disabled)',
                containment: this.screen.$('.node-networks'),
                disabled: this.screen.isLocked()
            }).disableSelection();
            var validationResult = this.model.validate();
            if (validationResult.length > 0) {
                this.screen.applyChangesButton.set('disabled', true);
                _.each(validationResult, _.bind(function (error) {
                    this.$('.physical-network-box[data-name=' + this.model.get('name') + ']')
                        .addClass('nodrag')
                        .next('.network-box-error-message').text(error);
                }, this));
            }
            return this;
        }
    });

    return NodesTab;
});
