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
    'views/cluster_page_tabs/nodes_tab',
    'views/cluster_page_tabs/network_tab',
    'views/cluster_page_tabs/settings_tab',
    'views/cluster_page_tabs/logs_tab',
    'views/cluster_page_tabs/actions_tab',
    'views/cluster_page_tabs/healthcheck_tab',
    'text!templates/cluster/page.html',
    'text!templates/cluster/customization_message.html',
    'text!templates/cluster/deployment_result.html',
    'text!templates/cluster/deployment_control.html'
],
function(utils, models, commonViews, dialogViews, NodesTab, NetworkTab, SettingsTab, LogsTab, ActionsTab, HealthCheckTab, clusterPageTemplate, clusterCustomizationMessageTemplate, deploymentResultTemplate, deploymentControlTemplate) {
    'use strict';
    var ClusterPage, ClusterCustomizationMessage, DeploymentResult, DeploymentControl;

    ClusterPage = commonViews.Page.extend({
        navbarActiveElement: 'clusters',
        breadcrumbsPath: function() {
            return [['home', '#'], ['environments', '#clusters'], [this.model.get('name'), null, true]];
        },
        title: function() {
            return this.model.get('name');
        },
        tabs: ['nodes', 'network', 'settings', 'logs', 'healthcheck', 'actions'],
        updateInterval: 5000,
        template: _.template(clusterPageTemplate),
        events: {
            'click .task-result .close': 'dismissTaskResult',
            'click .rollback': 'discardChanges',
            'click .deploy-btn:not(.disabled)': 'onDeployRequest'
        },
        getReleaseSetupTask: function(status) {
            return this.tasks.findTask({group: 'release_setup', status: status || 'running', release: this.model.get('release').id});
        },
        removeFinishedTasks: function(tasks, removeSilently) {
            tasks = tasks || this.model.tasks({group: 'network'});
            var requests = [];
            _.each(tasks, function(task) {
                if (task.get('status') != 'running') {
                    if (!removeSilently) {
                        this.model.get('tasks').remove(task);
                    }
                    requests.push(task.destroy({silent: true}));
                }
            }, this);
            return $.when.apply($, requests);
        },
        dismissTaskResult: function() {
            var task = this.model.task({group: 'deployment'}) || this.getReleaseSetupTask('error');
            if (task) {
                task.destroy();
            }
        },
        discardChanges: function() {
            this.registerSubView(new dialogViews.DiscardChangesDialog({model: this.model})).render();
        },
        displayChanges: function() {
            this.registerSubView(new dialogViews.DisplayChangesDialog({model: this.model})).render();
        },
        discardSettingsChanges: function(options) {
            this.registerSubView(new dialogViews.DiscardSettingsChangesDialog(options)).render();
        },
        onNameChange: function() {
            this.updateBreadcrumbs();
            this.updateTitle();
        },
        onDeployRequest: function() {
            if (_.result(this.tab, 'hasChanges')) {
                this.discardSettingsChanges({cb: _.bind(function() {
                    this.tab.revertChanges();
                    this.displayChanges();
                }, this)});
            } else {
                this.displayChanges();
            }
        },
        onTabLeave: function(e) {
            var href = $(e.currentTarget).attr('href');
            if (Backbone.history.getHash() != href.substr(1) && _.result(this.tab, 'hasChanges')) {
                e.preventDefault();
                this.discardSettingsChanges({
                    verification: this.model.tasks({group: 'network', status: 'running'}).length,
                    cb: _.bind(function() {
                        app.navigate(href, {trigger: true});
                    }, this)
                });
            }
        },
        scheduleUpdate: function() {
            if (this.model.task({group: ['deployment', 'network'], status: 'running'}) || this.getReleaseSetupTask()) {
                this.registerDeferred($.timeout(this.updateInterval).done(_.bind(this.update, this)));
            }
        },
        update: function() {
            var complete = _.after(2, _.bind(this.scheduleUpdate, this));
            var task = this.model.task({group: 'deployment', status: 'running'});
            if (task) {
                this.registerDeferred(task.fetch().done(_.bind(function() {
                    if (!task.match({status: 'running'})) {
                        this.deploymentTaskFinished();
                    }
                }, this)).always(complete));
                this.registerDeferred(this.model.get('nodes').fetch({data: {cluster_id: this.model.id}}).always(complete));
            }
            var verificationTask = this.model.task('verify_networks', 'running');
            if (verificationTask) {
                this.registerDeferred(verificationTask.fetch().always(_.bind(this.scheduleUpdate, this)));
            }
            var setupTask = this.getReleaseSetupTask();
            if (setupTask) {
                this.registerDeferred(this.tasks.fetch()
                    .always(_.bind(this.scheduleUpdate, this))
                    .done(_.bind(function() {
                        if (setupTask.get('status') != 'running') {
                            this.setupFinished(setupTask);
                        }
                    }, this))
                );
            }
        },
        deploymentTaskStarted: function() {
            $.when(this.model.fetch(), this.model.fetchRelated('nodes'), this.model.fetchRelated('tasks')).always(_.bind(function() {
                // FIXME: hack to prevent "Deploy" button flashing after deployment is finished
                this.model.set({changes: []}, {silent: true});
                this.scheduleUpdate();
            }, this));
        },
        deploymentTaskFinished: function() {
            $.when(this.model.fetch(), this.model.fetchRelated('nodes'), this.model.fetchRelated('tasks')).always(_.bind(function() {
                app.navbar.refresh();
            }, this));
        },
        setupFinished: function(task) {
            app.navbar.refresh();
            this.model.get('release').fetch();
            if (task.match({status: 'ready'})) {
                task.destroy();
            }
        },
        beforeTearDown: function() {
            $(window).off('beforeunload.' + this.eventNamespace);
            $('body').off('click.' + this.eventNamespace);
        },
        onBeforeunloadEvent: function() {
            if (_.result(this.tab, 'hasChanges')) {
                return dialogViews.DiscardSettingsChangesDialog.prototype.defaultMessage;
            }
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.model.on('change:name', this.onNameChange, this);
            this.scheduleUpdate();
            this.eventNamespace = 'unsavedchanges' + this.activeTab;
            $(window).on('beforeunload.' + this.eventNamespace, _.bind(this.onBeforeunloadEvent, this));
            $('body').on('click.' + this.eventNamespace, 'a[href^=#]:not(.no-leave-check)', _.bind(this.onTabLeave, this));
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            this.$el.html(this.template({
                cluster: this.model,
                tabs: this.tabs,
                activeTab: this.activeTab,
                renaming: this.renaming
            })).i18n();
            var options = {model: this.model, page: this};
            this.clusterCustomizationMessage = new ClusterCustomizationMessage(options);
            this.registerSubView(this.clusterCustomizationMessage);
            this.$('.customization-message').html(this.clusterCustomizationMessage.render().el);
            this.deploymentResult = new DeploymentResult(options);
            this.registerSubView(this.deploymentResult);
            this.$('.deployment-result').html(this.deploymentResult.render().el);
            this.deploymentControl = new DeploymentControl(options);
            this.registerSubView(this.deploymentControl);
            this.$('.deployment-control').html(this.deploymentControl.render().el);

            var tabs = {
                'nodes': NodesTab,
                'network': NetworkTab,
                'settings': SettingsTab,
                'actions': ActionsTab,
                'logs': LogsTab,
                'healthcheck': HealthCheckTab
            };
            if (_.has(tabs, this.activeTab)) {
                this.tab = new tabs[this.activeTab]({model: this.model, tabOptions: this.tabOptions, page: this});
                this.$('#tab-' + this.activeTab).html(this.tab.render().el);
                this.registerSubView(this.tab);
            }

            return this;
        }
    });

    ClusterCustomizationMessage = Backbone.View.extend({
        template: _.template(clusterCustomizationMessageTemplate),
        initialize: function(options) {
            this.model.on('change:is_customized', this.render, this);
        },
        render: function() {
            this.$el.html(this.template({cluster: this.model})).i18n();
            return this;
        }
    });

    DeploymentResult = Backbone.View.extend({
        template: _.template(deploymentResultTemplate),
        templateHelpers: _.pick(utils, 'urlify', 'linebreaks', 'serializeTabOptions'),
        initialize: function(options) {
            _.defaults(this, options);
            _.invoke([this.model.get('tasks'), this.page.tasks], 'bindToView', this, [{group: 'deployment'}, {group: 'release_setup', release: this.model.get('release').id}], function(task) {
                task.on('change:status', this.render, this);
            });
        },
        render: function() {
            this.$el.html(this.template(_.extend({
                cluster: this.model,
                task: this.model.task({group: 'deployment'}) || this.page.getReleaseSetupTask('error')
            }, this.templateHelpers))).i18n();
            return this;
        }
    });

    DeploymentControl = Backbone.View.extend({
        template: _.template(deploymentControlTemplate),
        events: {
            'click .stop-deployment-btn': 'stopDeployment'
        },
        stopDeployment: function() {
            this.registerSubView(new dialogViews.StopDeploymentDialog({model: this.model})).render();
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.model.on('change:changes', this.render, this);
            this.model.get('release').on('change:state', this.render, this);
            _.invoke([this.model.get('tasks'), this.page.tasks], 'bindToView', this, [{group: 'deployment'}, {group: 'release_setup', release: this.model.get('release').id}], function(task) {
                task.on('change:status', this.render, this);
                task.on('change:progress', this.updateProgress, this);
            });
            this.model.get('nodes').each(this.bindNodeEvents, this);
            this.model.get('nodes').on('resize', this.render, this);
            this.model.get('nodes').on('add', this.onNewNode, this);
        },
        bindNodeEvents: function(node) {
            return node.on('change:pending_addition change:pending_deletion', this.render, this);
        },
        onNewNode: function(node) {
            return this.bindNodeEvents(node) && this.render();
        },
        updateProgress: function() {
            var task = this.model.task({group: 'deployment', status: 'running'}) || this.page.getReleaseSetupTask();
            if (task) {
                var progress = task.get('progress') || 0;
                this.$('.bar').css('width', (progress > 3 ? progress : 3) + '%');
                this.$('.percentage').text(progress + '%');
            }
        },
        render: function() {
            this.$el.html(this.template({
                cluster: this.model,
                task: this.model.task({group: 'deployment', status: 'running'}) || this.page.getReleaseSetupTask()
            })).i18n();
            this.updateProgress();
            return this;
        }
    });

    return ClusterPage;
});
