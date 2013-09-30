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
    'text!templates/cluster/node_status.html',
    'text!templates/cluster/node_roles.html',
    'text!templates/cluster/edit_node_disks.html',
    'text!templates/cluster/node_disk.html',
    'text!templates/cluster/volume_style.html',
    'text!templates/cluster/edit_node_interfaces.html',
    'text!templates/cluster/node_interface.html'
],
function(utils, models, commonViews, dialogViews, nodesManagementPanelTemplate, assignRolesPanelTemplate, nodeListTemplate, nodeGroupTemplate, nodeTemplate, nodeStatusTemplate, nodeRolesTemplate, editNodeDisksScreenTemplate, nodeDisksTemplate, volumeStylesTemplate, editNodeInterfacesScreenTemplate, nodeInterfaceTemplate) {
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
            this.$('.btn-delete-nodes').toggle(!!this.$('.node-box:not(.node-delete) input[type=checkbox]:checked').length);
            this.$('.btn-add-nodes').css('display', this.$('.node-checkbox input:checked').length ? 'none' : 'block');
            var notDeployedSelectedNodes = this.$('.node-box.node-new:not(.node-offline) .node-checkbox input:checked');
            this.$('.btn-edit-nodes').toggle(!!notDeployedSelectedNodes.length && notDeployedSelectedNodes.length == this.$('.node-checkbox input:checked').length);
            var nodesIds = notDeployedSelectedNodes.map(function() {return parseInt($(this).val(), 10);}).get().join(',');
            this.$('.btn-edit-nodes').attr('href', '#cluster/' + this.model.id + '/nodes/edit/' + utils.serializeTabOptions({nodes: nodesIds}));
            // check selected nodes for group configuration availability
            var nodeIds = this.$('.node-box:not(.node-delete):not(.node-offline) input[type=checkbox]:checked').map(function() {return parseInt($(this).val(), 10);}).get();
            this.$('.btn-group-congiration').prop('disabled', !nodeIds.length);
            var nodes = new models.Nodes(this.nodes.filter(function(node) {return _.contains(nodeIds, node.id);}));
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
                this.nodes.parse = function(response) {
                    return _.map(response, function(node) {
                       return _.omit(node, 'pending_roles');
                    });
                };
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
            this.nodes.fetch().done(_.bind(this.render, this));
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
            this.constructor.__super__.initialize.apply(this, arguments);
        },
        render: function() {
            this.constructor.__super__.render.apply(this, arguments);
            this.roles.render();
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
            var chosenNodesIds = this.screen.$('.node-box:not(.node-delete) .node-checkbox input:checked').map(function() {return parseInt($(this).val(), 10);}).get();
            var nodes = new models.Nodes(this.nodes.getByIds(chosenNodesIds));
            nodes.cluster = this.nodes.cluster;
            var dialog = new dialogViews.DeleteNodesDialog({nodes: nodes});
            app.page.tab.registerSubView(dialog);
            dialog.render();
        },
        applyChanges: function() {
            this.$('.btn-apply').prop('disabled', true);
            var nodeIds = this.screen.roles.nodeIds;
            var nodes  = new models.Nodes(this.nodes.getByIds(nodeIds));
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
            var selectedNodesIds = this.screen.$('.node-checkbox input:checked').map(function() {return parseInt($(this).val(), 10);}).get().join(',');
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
            }));
            return this;
        }
    });

    AssignRolesPanel = Backbone.View.extend({
        template: _.template(assignRolesPanelTemplate),
        className: 'roles-panel',
        events: {
            'change input' : 'handleChanges'
        },
        handleChanges: function(e) {
            this.defineNodes();
            this.assignRoles();
            if (e) {
                this.checkRoleDeletionAbility(this.$(e.currentTarget));
            } else {
                _.each(this.$('input'), this.calculateInputState, this);
            }
            this.checkForConflicts();
        },
        calculateInputState: function(input) {
            var nodes = this.screen.nodes.filter(function(node) {return _.contains(this.nodeIds, node.id) && _.contains(_.union(node.get('roles'),node.get('pending_roles')), $(input).val());}, this);
            this.setInputState($(input), nodes);
        },
        checkRoleDeletionAbility: function(input) {
            if (!$(input).is(':checked')) {
                var nodes = this.screen.nodes.filter(function(node) {return _.contains(this.nodeIds, node.id) && !node.get('pending_addition') && _.contains(node.get('roles'), $(input).val());}, this);
                this.setInputState($(input), nodes);
            }
        },
        setInputState: function(input, nodes) {
            var prop = nodes.length ? nodes.length == this.nodeIds.length ? 'checked' : 'indeterminate' : '';
            input.prop(prop, true);
        },
        assignRoles: function() {
            var nodes = new models.Nodes(this.screen.nodes.getByIds(this.nodeIds));
            _.each(this.$('input'), function(input) {
                var role = $(input).val();
                if (!$(input).prop('indeterminate')) {
                    nodes.each(function(node) {
                        if (!_.contains(node.get('roles'), role)) {
                            var pending_roles = $(input).is(':checked') ? _.uniq(_.union(node.get('pending_roles'), role)) : _.difference(node.get('pending_roles'), role);
                            node.set({pending_roles: pending_roles});
                        }
                    }, this);
                }
            }, this);
            this.screen.calculateApplyButtonState();
        },
        checkForConflicts: function(e) {
            this.$('input').prop('disabled', false);
            this.$('.role-conflict').text('');
            // check for nodes
            this.$('input').prop('disabled', !this.screen.nodes.length);
            // check for deployed nodes
            _.each(this.$('input'), function(input) {
                var deployedNodes = this.screen.nodes.filter(function(node) {return _.contains(node.get('roles'), $(input).val());}).length;
                $(input).prop('disabled', deployedNodes && deployedNodes == this.nodeIds.length);
            }, this);
            // check uncompatible roles
            var selectedRoles = _.filter(this.$('input'), function(input) {return $(input).prop('indeterminate') || $(input).prop('checked');}).map(function(input) {return $(input).val();});
            _.each(this.getListOfUncompatibleRoles(selectedRoles), function(role) {
                this.$('input[value=' + role + ']').prop('disabled', true);
                this.$('.role-conflict.' + role).text('This role cannot be combined with the other roles already selected.');
            }, this);
            // non-ha deployment mode restriction: environment can not have more than one controller node
            if (this.cluster.get('mode') == 'multinode') {
                var allocatedController = this.screen.tab.model.get('nodes').filter(function(node) {return !node.get('pending_deletion') && _.contains(_.union(node.get('roles'),node.get('pending_roles')), 'controller');})[0];
                var cantAddController = allocatedController && !_.contains(this.nodeIds, allocatedController.id);
                var controllerSelected = (this.$('input[value=controller]').is(':checked') || this.$('input[value=controller]').prop('indeterminate')) && this.nodeIds.length;
                this.screen.$('.node-box:not(.node-offline):not(.node-error):not(.node-delete) input:not(:checked)').prop('disabled', controllerSelected);
                this.screen.$('.select-all input:not(:checked)').prop('disabled', controllerSelected).parent().toggleClass('disabled', controllerSelected);
                // if there are no allocated controllers, check Select All tumblers for its' disabled state (offline, error nodes)
                if (!controllerSelected && this.screen.nodeList) {
                    _.invoke(this.screen.nodeList.subViews, 'calculateSelectAllDisabledState', this);
                }
                if (this.nodeIds.length > 1 || cantAddController) {
                    this.$('input[value=controller]').prop('disabled', true);
                }
                if (this.nodeIds.length > 1 || controllerSelected || cantAddController) {
                    this.$('.role-conflict.controller').text('Only one controller can be assigned in a multi-node deployment that is not Highly-Available (HA).');
                }
            }
        },
        getListOfUncompatibleRoles: function(roles) {
            var forbiddenRoles = [];
            var release = this.cluster.get('release');
            _.each(roles, function(role) {
                forbiddenRoles = _.union(forbiddenRoles, release.get('roles_metadata')[role].conflicts);
            });
            return _.uniq(forbiddenRoles);
        },
        defineNodes: function() {
            this.nodeIds = this.screen.$('.node-checkbox input:checked').map(function() {return parseInt($(this).val(), 10);}).get();
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.cluster = this.screen.tab.model;
            this.roles = this.cluster.availableRoles();
        },
        render: function() {
            this.$el.html(this.template({
                roles: this.roles,
                rolesData: this.cluster.get('release').get('roles_metadata')
            }));
            this.defineNodes();
            _.each(this.$('input'), this.calculateInputState, this);
            this.checkForConflicts();
            return this;
        }
    });

    NodeList = Backbone.View.extend({
        className: 'node-list',
        template: _.template(nodeListTemplate),
        events: {
            'change input[name=select-nodes-common]' : 'selectAllNodes',
            'click .btn-cluster-details': 'toggleSummaryPanel'
        },
        selectAllNodes: function(e) {
            this.$('input[name=select-node-group]:not(:disabled)').prop('checked', this.$(e.currentTarget).is(':checked')).trigger('change');
        },
        hideSummaryPanel: function(e) {
            if (!(e && $(e.target).closest(this.$('.node-list-name')).length)) {
                this.$('.cluster-details').hide();
            }
        },
        toggleSummaryPanel: function() {
            this.$('.cluster-details').toggle();
        },
        amountOfAvailableNodes: function() {
            return this.$('.node-box:not(.node-offline):not(.node-error):not(.node-delete)').length;
        },
        calculateSelectAllCheckedState: function() {
            this.$('input[name=select-nodes-common]').prop('checked', this.amountOfAvailableNodes() && this.$('.node-checkbox input:checked').length == this.amountOfAvailableNodes());
        },
        calculateSelectAllDisabledState: function() {
            var disabled = !this.amountOfAvailableNodes() || this.screen instanceof EditNodesScreen || this.screen.isLocked();
            this.$('input[name=select-nodes-common]').prop('disabled', disabled).parent().toggleClass('disabled', disabled);
        },
        groupNodes: function(attribute) {
            if (_.isUndefined(attribute)) {
                attribute = this.screen instanceof AddNodesScreen ? 'hardware' : this.screen.tab.model.get('grouping');
            }
            if (attribute == 'roles') {
                var rolesMetadata = this.screen.tab.model.get('release').get('roles_metadata');
                this.nodeGroups = this.nodes.groupBy(function(node) {return  _.map(node.sortRoles(), function(role) {return rolesMetadata[role].name;}).join(' + ');});
            } else if (attribute == 'hardware') {
                this.nodeGroups = this.nodes.groupBy(function(node) {return 'HDD: ' + utils.showDiskSize(node.resource('hdd')) + ' RAM: ' + utils.showMemorySize(node.resource('ram'));});
            } else {
                this.nodeGroups = this.nodes.groupBy(function(node) {return _.union(node.get('roles'), node.get('pending_roles')).join(' + ') + ' + HDD: ' + utils.showDiskSize(node.resource('hdd')) + ' RAM: ' + utils.showMemorySize(node.resource('ram'));});
            }
            this.renderNodeGroups();
            this.screen.updateBatchActionsButtons();
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.screen.initialRoles = this.nodes.map(function(node) {return node.get('pending_roles') || [];});
            this.eventNamespace = 'click.click-summary-panel';
        },
        renderNodeGroups: function() {
            this.$('.nodes').html('');
            _.each(_.keys(this.nodeGroups), function(groupLabel) {
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
            }));
            this.groupNodes();
            $('html').on(this.eventNamespace, _.bind(this.hideSummaryPanel, this));
            Backbone.history.on('route', this.hideSummaryPanel, this);
            return this;
        }
    });

    NodeGroup = Backbone.View.extend({
        className: 'node-group',
        template: _.template(nodeGroupTemplate),
        events: {
            'change input[name=select-node-group]' : 'selectAllNodes'
        },
        selectAllNodes: function(e) {
            this.$('.node-checkbox input:not(:disabled)').prop('checked', this.$(e.currentTarget).is(':checked')).trigger('change');
        },
        amountOfAvailableNodes: function() {
            return this.$('.node-box:not(.node-offline):not(.node-error):not(.node-delete)').length;
        },
        calculateSelectAllCheckedState: function() {
            this.$('input[name=select-node-group]').prop('checked', this.amountOfAvailableNodes() && this.$('.node-checkbox input:checked').length == this.amountOfAvailableNodes());
            this.nodeList.calculateSelectAllCheckedState();
        },
        calculateSelectAllDisabledState: function() {
            var disabled = !this.amountOfAvailableNodes() || this.nodeList.screen instanceof EditNodesScreen || this.nodeList.screen.isLocked();
            this.$('input[name=select-node-group]').prop('disabled', disabled).parent().toggleClass('disabled', disabled);
            this.nodeList.calculateSelectAllDisabledState();
        },
        initialize: function(options) {
            _.defaults(this, options);
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
            }));
            this.nodes.each(this.renderNode, this);
            this.calculateSelectAllCheckedState();
            this.calculateSelectAllDisabledState();
            return this;
        }
    });

    Node = Backbone.View.extend({
        className: 'node',
        template: _.template(nodeTemplate),
        nodeStatusTemplate: _.template(nodeStatusTemplate),
        nodeRolesTemplate: _.template(nodeRolesTemplate),
        templateHelpers: _.pick(utils, 'showDiskSize', 'showMemorySize'),
        renaming: false,
        checked: false,
        events: {
            'change .node-checkbox input': 'selectNode',
            'click .node-renameable': 'startNodeRenaming',
            'keydown .name input': 'onNodeNameInputKeydown',
            'click .node-details': 'showNodeDetails',
            'click .btn-discard-role-changes': 'discardRoleChanges',
            'click .btn-discard-addition': 'discardAddition',
            'click .btn-discard-deletion': 'discardDeletion',
            'click .btn-view-logs': 'showNodeLogs'
        },
        selectNode: function() {
            this.checked = this.$('.node-checkbox input').is(':checked');
            this.$el.toggleClass('checked', this.checked);
            this.group.calculateSelectAllCheckedState();
            this.group.calculateSelectAllDisabledState();
            if (!this.checked) {
                this.node.set({pending_roles: this.initialRoles});
            }
            if (this.screen instanceof AddNodesScreen || this.screen instanceof EditNodesScreen) {
                this.screen.roles.handleChanges();
            } else {
                this.screen.updateBatchActionsButtons();
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
        showNodeDetails: function() {
            var dialog = new dialogViews.ShowNodeInfoDialog({node: this.node});
            app.page.tab.registerSubView(dialog);
            dialog.render();
        },
        updateNode: function(data) {
            this.node.save(data, {patch: true, wait: true})
                .done(_.bind(function() {
                    this.screen.tab.model.get('nodes').fetch();
                    app.page.deploymentControl.render();
                    app.page.removeFinishedTasks();
                }, this))
                .fail(function() {utils.showErrorDialog({title: "Can't discard node changes"});});
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
        updateProgress: function() {
            if (this.node.get('status') == 'provisioning' || this.node.get('status') == 'deploying') {
                var progress = this.node.get('progress') || 0;
                this.$('.bar').css('width', (progress > 3 ? progress : 3) + '%');
            }
        },
        updateStatus: function() {
            this.$('.node-status').html(this.nodeStatusTemplate({
                node: this.node,
                edit: this.screen instanceof EditNodesScreen
            }));
            this.$('.node-box').toggleClass('node-offline', !this.node.get('online'));
            this.updateProgress();
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
        updateRoles: function() {
            var roles = this.node.get('pending_roles') || [];
            var preferredOrder = ['controller', 'compute', 'cinder'];
            roles.sort(function(a, b) {
                return _.indexOf(preferredOrder, a) - _.indexOf(preferredOrder, b);
            });
            this.node.set({pending_roles: roles}, {silent: true});
            this.$('.roles').html(this.nodeRolesTemplate({node: this.node}));
        },
        uncheckNode: function() {
            if (this.node.get('pending_deletion')) {
                this.checked = false;
            }
            this.group.render();
        },
        beforeTearDown: function() {
            $('html').off(this.eventNamespace);
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.screen = this.group.nodeList.screen;
            this.eventNamespace = 'click.editnodename' + this.node.id;
            this.node.on('change:pending_deletion', this.uncheckNode, this);
            this.node.on('change:name change:online', this.render, this);
            this.node.on('change:pending_roles', this.updateRoles, this);
            this.node.on('change:status change:pending_addition', this.updateStatus, this);
            this.node.on('change:progress', this.updateProgress, this);
            this.initialRoles = this.node.get('pending_roles');
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            this.$el.html(this.template(_.extend({
                node: this.node,
                renaming: this.renaming,
                renameable: this.renameable,
                checked: this.checked,
                edit: this.screen instanceof EditNodesScreen,
                locked: this.screen.isLocked()
            }, this.templateHelpers)));
            this.updateStatus();
            this.updateRoles();
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
        hasChanges: function() {
            return !_.isEqual(this.disks.toJSON(), this.initialData);
        },
        hasValidationErrors: function() {
            var result = false;
            this.disks.each(function(disk) {result = result || _.some(disk.get('volumes').models, 'validationError');}, this);
            return result;
        },
        isLocked: function() {
            var forbiddenNodes = _.union(this.nodes.where({pending_addition: true}), this.nodes.where({status: 'error', error_type: 'provision'})).length;
            return !forbiddenNodes || this.constructor.__super__.isLocked.apply(this);
        },
        checkForChanges: function() {
            var hasChanges = this.hasChanges();
            var hasValidationErrors = this.hasValidationErrors();
            this.$('.btn-apply').attr('disabled', !hasChanges || hasValidationErrors);
            this.$('.btn-revert-changes').attr('disabled', !hasChanges && !hasValidationErrors);
            this.$('.btn-defaults').attr('disabled', false);
        },
        loadDefaults: function() {
            this.disableControls(true);
            this.disks.fetch({url: _.result(this.nodes.at(0), 'url') + '/disks/defaults/'})
                .fail(_.bind(function() {utils.showErrorDialog({title: 'Disks configuration'});}, this));
        },
        revertChanges: function() {
            this.disks.reset(_.cloneDeep(this.initialData), {parse: true});
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
                    this.initialData = _.cloneDeep(this.disks.toJSON());
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
                this.disks = new models.Disks([], {url: _.result(this.nodes.at(0), 'url') + '/disks'});
                this.loading = $.when(this.volumes.fetch(), this.disks.fetch())
                    .done(_.bind(function() {
                        this.initialData = _.cloneDeep(this.disks.toJSON());
                        this.mapVolumesColors();
                        this.render();
                        this.disks.on('sync', this.render, this);
                        this.disks.on('reset', this.render, this);
                        this.disks.on('error', this.checkForChanges, this);
                    }, this))
                    .fail(_.bind(this.goToNodeList, this));
            } else {
                this.goToNodeList();
            }
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
            }));
            if (this.loading && this.loading.state() != 'pending') {
                this.renderDisks();
                this.checkForChanges();
            }
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
            'keyup input': 'updateDisks',
            'click .use-all-allowed': 'useAllAllowedSpace'
        },
        toggleEditDiskForm: function(e) {
            if (this.screen.isLocked()) {return;}
            this.$('.disk-form').collapse('toggle');
            this.checkForGroupsDeletionAvailability();
        },
        getVolumeMinimum: function(name) {
            return this.screen.volumes.findWhere({name: name}).get('min_size');
        },
        checkForGroupsDeletionAvailability: function() {
            this.disk.get('volumes').each(function(volume) {
                var name = volume.get('name');
                this.$('.disk-visual .' + name + ' .close-btn').toggle(volume.getMinimalSize(this.getVolumeMinimum(name)) <= 0 && this.$('.disk-form').hasClass('in'));
            }, this);
        },
        validateVolume: function (volume) {
            var name = volume.get('name');
            volume.set({size: Number((this.$('input[name=' + name + ']').val()).replace(/,/g, ''))}, {validate: true, minimum: this.getVolumeMinimum(name)});
        },
        updateDisk: function() {
            this.$('.disk-visual').removeClass('invalid');
            this.$('input').removeClass('error').parents('.volume-group').next().text('');
            this.$('.volume-group-error-message.common').text('');
            this.disk.get('volumes').each(this.validateVolume, this); // volumes validation (minimum)
            this.disk.set({volumes: this.disk.get('volumes')}, {validate: true}); // disk validation (maximum)
            this.renderVisualGraph();
            this.checkForGroupsDeletionAvailability();
        },
        updateDisks: function(e) {
            this.updateDisk();
            _.invoke(_.omit(this.screen.subViews, this.cid), 'updateDisk', this);
            this.screen.checkForChanges();
        },
        deleteVolume: function(e) {
            this.$('input[name=' + this.$(e.currentTarget).parents('.volume-group').data('volume') + ']').val(0).trigger('keyup');
        },
        useAllAllowedSpace: function(e) {
            var volumeName = this.$(e.currentTarget).parents('.volume-group').data('volume');
            this.$('input[name=' + volumeName + ']').val(_.max([0, this.disk.getUnallocatedSpace({skip: volumeName})])).trigger('keyup');
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.disk.on('invalid', function(model, error) {
                this.$('.disk-visual').addClass('invalid');
                this.$('input').addClass('error');
                this.$('.volume-group-error-message.common').text(error);
            }, this);
            this.disk.get('volumes').each(function(volume) {
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
        render: function() {
            this.$el.html(this.template(_.extend({
                diskMetaData: this.diskMetaData,
                disk: this.disk,
                volumes: this.screen.volumes
            }, this.templateHelpers)));
            this.$('.disk-form').collapse({toggle: false});
            this.applyColors();
            this.renderVisualGraph();
            this.$('input').autoNumeric('init', {mDec: 0});
            return this;
        }
    });

    EditNodeInterfacesScreen = EditNodeScreen.extend({
        className: 'edit-node-networks-screen',
        constructorName: 'EditNodeInterfacesScreen',
        template: _.template(editNodeInterfacesScreenTemplate),
        events: {
            'click .btn-defaults': 'loadDefaults',
            'click .btn-revert-changes': 'revertChanges',
            'click .btn-apply:not(:disabled)': 'applyChanges',
            'click .btn-return:not(:disabled)': 'returnToNodeList'
        },
        hasChanges: function() {
            return !_.isEqual(this.interfaces.toJSON(), this.initialData);
        },
        isLocked: function() {
            var forbiddenNodes = _.union(this.nodes.where({pending_addition: true}), this.nodes.where({status: 'error'})).length;
            return !forbiddenNodes || this.constructor.__super__.isLocked.apply(this);
        },
        checkForChanges: function() {
            this.$('.btn-apply, .btn-revert-changes').attr('disabled', this.isLocked() || !this.hasChanges());
        },
        loadDefaults: function() {
            this.disableControls(true);
            this.interfaces.fetch({url: _.result(this.nodes.at(0), 'url') + '/interfaces/default_assignment', reset: true})
                .done(_.bind(function() {
                    this.disableControls(false);
                    this.checkForChanges();
                }, this))
                .fail(_.bind(function() {
                    this.disableControls(false);
                    utils.showErrorDialog({title: 'Unable to load default settings'});
                }, this));
        },
        revertChanges: function() {
            this.interfaces.reset(_.cloneDeep(this.initialData), {parse: true});
        },
        applyChanges: function() {
            this.disableControls(true);
            return $.when.apply($, this.nodes.map(function(node) {
                    var configuration = new models.NodeInterfaceConfiguration({id: node.id, interfaces: this.interfaces});
                    configuration.get('interfaces').each(function(ifc, index) {
                        ifc.set({id: this.nodeInterfaceIds[node.id][index]}, {silent: true});
                    }, this);
                    return Backbone.sync('update', new models.NodeInterfaceConfigurations(configuration));
                }, this))
                .done(_.bind(function() {
                    this.initialData = this.interfaces.toJSON();
                }, this))
                .fail(_.bind(function() {
                    utils.showErrorDialog({title: 'Interfaces configuration'});
                }, this))
                .always(_.bind(function() {
                    this.disableControls(false);
                    this.checkForChanges();
                }, this));
        },
        initialize: function(options) {
            this.constructor.__super__.initialize.apply(this, arguments);
            if (this.nodes.length) {
                this.model.on('change:status', function() {
                    this.revertChanges();
                    this.render();
                }, this);
                var complete = _.after(this.nodes.length, _.bind(function() {
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
                            this.checkForChanges();
                            this.renderInterfaces();
                        }, this))
                        .fail(_.bind(this.goToNodeList, this));
                }, this));
                this.nodeInterfaceIds = {};
                this.nodes.each(function(node) {
                    var interfaces = new models.Interfaces();
                    interfaces
                        .fetch({url: _.result(node, 'url') + '/interfaces'})
                        .done(_.bind(function() {
                            if (node.id == this.nodes.at(0).id) {
                                this.initialData = interfaces.toJSON();
                                this.interfaces = new models.Interfaces();
                                this.interfaces.reset(_.cloneDeep(this.initialData), {parse: true});
                                this.interfaces.on('reset', this.renderInterfaces, this);
                                this.interfaces.on('reset', this.checkForChanges, this);
                            }
                            this.nodeInterfaceIds[node.id] = interfaces.pluck('id');
                        }, this))
                        .always(complete);
                }, this);
            } else {
                this.goToNodeList();
            }
        },
        renderInterfaces: function() {
            this.tearDownRegisteredSubViews();
            this.$('.node-networks').html('');
            this.interfaces.each(_.bind(function(ifc) {
                var nodeInterface = new NodeInterface({model: ifc, screen: this});
                this.registerSubView(nodeInterface);
                this.$('.node-networks').append(nodeInterface.render().el);
            }, this));
        },
        render: function() {
            this.$el.html(this.template({
                nodes: this.nodes,
                locked: this.isLocked()
            }));
            if (this.loading && this.loading.state() != 'pending') {
                this.renderInterfaces();
            }
            return this;
        }
    });

    NodeInterface = Backbone.View.extend({
        template: _.template(nodeInterfaceTemplate),
        templateHelpers: _.pick(utils, 'showBandwidth'),
        events: {
            'sortremove .logical-network-box': 'dragStart',
            'sortreceive .logical-network-box': 'dragStop',
            'sortstop .logical-network-box': 'dragStop'
        },
        dragStart: function(event, ui) {
            var networkNames = $(ui.item).find('.logical-network-item').map(function(index, el) {return $(el).data('name');}).get();
            var networks = this.model.get('assigned_networks').filter(function(network) {return _.contains(networkNames, network.get('name'));});
            this.model.get('assigned_networks').remove(networks);
            this.screen.draggedNetworks = networks;
        },
        dragStop: function(event, ui) {
            var networks = this.screen.draggedNetworks;
            if (event.type == 'sortreceive') {
                this.model.get('assigned_networks').add(networks);
            }
            this.render();
            this.screen.draggedNetworks = null;
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
            this.$el.html(this.template(_.extend({ifc: this.model}, this.templateHelpers)));
            this.checkIfEmpty();
            this.$('.logical-network-box').sortable({
                connectWith: '.logical-network-box',
                items: '.logical-network-group',
                containment: this.screen.$('.node-networks'),
                disabled: this.screen.isLocked()
            }).disableSelection();
            return this;
        }
    });

    return NodesTab;
});
