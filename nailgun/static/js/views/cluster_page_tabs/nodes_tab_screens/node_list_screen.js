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
    'jsx!views/cluster_page_tabs/nodes_tab_screens/nodes_tab_subviews',
    'views/cluster_page_tabs/nodes_tab_screens/screen',
    'text!templates/cluster/nodes_management_panel.html',
    'text!templates/cluster/node_list.html',
    'text!templates/cluster/node_group.html',
    'text!templates/cluster/node.html',
    'text!templates/cluster/node_roles.html'
],
function(utils, models, dialogs, panels, Screen, nodesManagementPanelTemplate, nodeListTemplate, nodeGroupTemplate, nodeTemplate, nodeRoleTemplate) {
    'use strict';
    var NodeListScreen, NodesManagementPanel, NodeList, NodeGroup, Node;

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
            var deployedNodes = nodes.where({status: 'ready'});
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
            this.stickit(this.configureDisksButton, {'.btn-configure-disks': {
                attributes: _.union([], disabledBindings.attributes, this.getConfigureButtonsObject('btn btn-group-congiration btn-configure-disks'))
            }});
            this.stickit(this.configureInterfacesButton, {'.btn-configure-interfaces': {
                attributes: _.union([], disabledBindings.attributes, this.getConfigureButtonsObject('btn btn-group-congiration btn-configure-interfaces'))
            }});
            this.stickit(this.addNodesButton, {'.btn-add-nodes': _.extend({}, visibleBindings, disabledBindings)});
            this.stickit(this.editRolesButton, {'.btn-edit-nodes': _.extend({}, visibleBindings, disabledBindings)});
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
                this.nodes.on('change:pending_roles', function(node, roles, options) {
                    this.actualizePendingRoles(node, roles, options);
                    this.calculateApplyButtonState();
                }, this);
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
        beforeTearDown: function() {
            if (this.roles) {
                utils.universalUnmount(this.roles);
            }
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
                this.$el.append($('<div/>').addClass('roles-panel'));
                if (this.roles) {
                    utils.universalUnmount(this.roles);
                }
                this.roles = utils.universalMount(new panels.RolesPanel({cluster: this.model, nodes: this.nodes}), this.$('.roles-panel'), this);
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
            'change select[name=grouping]': 'groupNodes',
            'click .btn-delete-nodes:not(:disabled)': 'showDeleteNodesDialog',
            'click .btn-apply:not(:disabled)': 'applyChanges',
            'click .btn-group-congiration:not(.conflict):not(:disabled)': 'goToConfigurationScreen',
            'click .btn-group-congiration.conflict': 'showUnavailableGroupConfigurationDialog',
            'click .btn-add-nodes': 'goToAddNodesScreen',
            'click .btn-edit-nodes': 'goToEditNodesRolesScreen',
            'click .btn-cancel': 'goToNodesList',
            'click .btn-clear-filter': 'clearFilter'
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
        showUnavailableGroupConfigurationDialog: function(e) {
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
                nodeGroups = _.sortBy(nodeGroups, function(group) { return group[0];});
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
            var nodeView = new Node({
                node: node,
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
                    observe: ['status', 'online', 'pending_addition', 'pending_deletion', 'disabled'],
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
                }, {
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
            },
            '.name p': {
                observe: ['name', 'mac'],
                onGet: function(values) {
                    return values[0] || values[1];
                }
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
            return 'node-box ' + nodeClass + (this.node.get('disabled') ? ' disabled' : '');
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
            return this.hasChanges() && !(this.screen instanceof this.screen.EditNodesScreen) ? 'btn btn-link btn-discard-node-changes btn-discard-' + btnClass : 'btn btn-link btn-view-logs';
        },
        formatNodeButtonTitle: function(value, options) {
            var title = this.node.get('pending_addition') ? $.t('cluster_page.nodes_tab.node.status.discard_addition') : this.node.get('pending_deletion') ? $.t('cluster_page.nodes_tab.node.status.discard_deletion') : $.t('cluster_page.nodes_tab.node.status.discard_role_changes');
            return this.hasChanges() && !(this.screen instanceof this.screen.EditNodesScreen) ? title : $.t('cluster_page.nodes_tab.node.status.view_logs');
        },
        formatNodeButtonIcon: function(value, options) {
            return this.hasChanges() && !(this.screen instanceof this.screen.EditNodesScreen) ? 'icon-back-in-time' : 'icon-logs';
        },
        calculateNodeState: function() {
            this.node.set('disabled', !this.node.isSelectable() || this.screen instanceof this.screen.EditNodesScreen || this.screen.isLocked());
            if (this.screen.isLocked()) {
                this.node.set('checked', false);
            }
        },
        startNodeRenaming: function() {
            $('html').on(this.eventNamespace, _.bind(function(e) {
                // FIXME: 'node-renameable' class usage should be revised
                if ($(e.target).hasClass('node-name') || $(e.target).hasClass('node-renameable')) {
                    e.preventDefault();
                } else {
                    this.endNodeRenaming();
                }
            }, this));
            this.renaming = true;
            this.render();
            this.$('.node-name').focus();
        },
        endNodeRenaming: function() {
            $('html').off(this.eventNamespace);
            this.renaming = false;
            this.render();
        },
        applyNewNodeName: function() {
            var name = $.trim(this.$('.node-name').val());
            if (name && name != this.node.get('name')) {
                this.$('.node-name').attr('disabled', true);
                this.screen.nodes.get(this.node.id).save({name: name}, {patch: true, wait: true}).always(_.bind(this.endNodeRenaming, this));
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
            var dialog = new dialogs.ShowNodeInfoDialog({node: this.node});
            app.page.tab.registerSubView(dialog);
            dialog.render();
        },
        updateNode: function(data) {
            this.node.save(data, {patch: true, wait: true})
                .done(_.bind(function() {
                    this.screen.tab.model.fetch();
                    this.screen.tab.model.fetchRelated('nodes');
                    app.navbar.refresh();
                    app.page.removeFinishedNetworkTasks();
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
            this.node.on('change:status', this.calculateNodeState, this);
            this.node.on('change:disabled', this.group.calculateSelectAllDisabledState, this.group);
            if (this.screen.roles) {
                this.node.on('change:checked', this.screen.roles.assignRoles, this.screen.roles);
            }
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            this.$el.html(this.template(_.extend({
                node: this.node,
                renaming: this.renaming,
                edit: this.screen instanceof this.screen.EditNodesScreen,
                locked: this.screen.isLocked()
            }, this.templateHelpers))).i18n();
            this.stickit(this.node);
            this.calculateNodeState();
            return this;
        }
    });

    return NodeListScreen;
});
