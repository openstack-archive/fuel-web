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
    'jsx!views/cluster_page_tabs/nodes_tab_screens/node_list',
    'text!templates/cluster/nodes_management_panel.html'
],
function(utils, models, dialogs, panels, Screen, NodeList, nodesManagementPanelTemplate) {
    'use strict';
    var NodeListScreen, NodesManagementPanel;

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
            var filteredNode = this.filteredNodes.get(node.id);
            if (filteredNode) {
                filteredNode.set(node.attributes);
            }
        },
        filterNodes: function(filterValue) {
            this.filteredNodes.reset(_.invoke(this.nodes.filter(function(node) {
                return _.contains(node.get('name').toLowerCase(), filterValue) || _.contains(node.get('mac').toLowerCase(), filterValue);
            }), 'clone'));
        },
        initialize: function() {
            this.ClusterNodesScreen = require('views/cluster_page_tabs/nodes_tab_screens/cluster_nodes_screen');
            this.AddNodesScreen = require('views/cluster_page_tabs/nodes_tab_screens/add_nodes_screen');
            this.EditNodesScreen = require('views/cluster_page_tabs/nodes_tab_screens/edit_nodes_screen');
            this.nodes.on('resize', function() {
                this.filterNodes(this.nodeFilter.get('value'));
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
                this.filterNodes(filter.get('value'));
            }, 300), this);
            this.filteredNodes = new models.Nodes(this.nodes.invoke('clone'));
            this.filteredNodes.cluster = this.nodes.cluster;
            this.grouping = this instanceof this.AddNodesScreen ? 'hardware' : this.model.get('grouping');
            this.updateInitialNodes();
        },
        updateInitialNodes: function() {
            this.initialNodes = new models.Nodes(this.nodes.invoke('clone'));
        },
        beforeTearDown: function() {
            if (this.roles) {
                utils.universalUnmount(this.roles);
            }
            if (this.nodeList) {
                utils.universalUnmount(this.nodeList);
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
            this.$el.append($('<div />'));
            if (this.nodeList) {
                utils.universalUnmount(this.nodeList);
            }
            this.nodeList = utils.universalMount(new NodeList({
                nodes: this.filteredNodes,
                grouping: this.grouping,
                cluster: this.model,
                locked: this.isLocked() || this instanceof this.EditNodesScreen,
                checked: this instanceof this.EditNodesScreen
            }), this.$el.find('div:last')[0]);
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
            this.updateBatchActionsButtons();
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
            this.screen.grouping = this.$(e.currentTarget).val();
            if (this.screen instanceof this.screen.ClusterNodesScreen) {
                this.cluster.save({grouping: this.screen.grouping}, {patch: true, wait: true});
            }
            this.screen.render();
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
                currentGrouping: this.screen.grouping,
                edit: this.screen instanceof this.screen.EditNodesScreen
            })).i18n();
            var isDisabled = !!this.cluster.tasks({group: 'deployment', status: 'running'}).length;
            this.screen.addNodesButton.set('disabled', isDisabled);
            this.screen.editRolesButton.set('disabled', isDisabled);
            return this;
        }
    });

    return NodeListScreen;
});
