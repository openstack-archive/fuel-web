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
        'models',
        'views/common',
        'views/dialogs',
        'text!templates/cluster/actions_tab.html',
        'text!templates/cluster/actions_rename.html',
        'text!templates/cluster/actions_reset.html',
        'text!templates/cluster/actions_delete.html',
        'text!templates/cluster/actions_update.html',
        'text!templates/cluster/actions_rollback.html'
    ],
function(models, commonViews, dialogViews, actionsTabTemplate, renameEnvironmentTemplate, resetEnvironmentTemplate, deleteEnvironmentTemplate, updateEnvironmentTemplate, rollbackEnvironmentTemplate) {
    'use strict';

    var ActionsTab, RenameEnvironmentAction, ResetEnvironmentAction, DeleteEnvironmentAction, UpdateEnvironmentAction;

    ActionsTab = commonViews.Tab.extend({
        template: _.template(actionsTabTemplate),
        initialize: function(options) {
            _.defaults(this, options);
            var cluster = this.model;
            cluster.on('change:status', this.render, this);
            cluster.get('tasks').bindToView(this, [{group: 'deployment'}], function(task) {
                task.on('change:status', this.render, this);
            });
        },
        isLocked: function() {
            return !!this.model.tasks({group: 'deployment', status: 'running'}).length;
        },
        renderAction: function(ActionData) {
            var options = _.extend({model: this.model, tab: this});
            var actionView = new ActionData(options);
            this.registerSubView(actionView);
            this.$('.environment-actions').append(actionView.render().el).i18n();
        },
        render: function() {
            this.$el.html(this.template()).i18n();
            var actions = [ RenameEnvironmentAction, ResetEnvironmentAction, DeleteEnvironmentAction, UpdateEnvironmentAction ];
            _.each(actions, this.renderAction, this);
            return this;
        }
    });

    RenameEnvironmentAction = Backbone.View.extend({
        className: 'span4 action-item-placeholder',
        template: _.template(renameEnvironmentTemplate),
        events: {
            'click .action-btn': 'applyAction',
            'keydown input[name=cluster_name]': 'onClusterNameInputKeydown'
        },
        applyAction: function() {
            var name = $.trim(this.$('input[name=cluster_name]').val());
            if (name != this.model.get('name')) {
                var deferred = this.model.save({name: name}, {patch: true, wait: true});
                if (deferred) {
                    var controls = this.$('input, button');
                    controls.attr('disabled', true);
                    this.setControlsDisabledState(true);
                    deferred
                        .fail(_.bind(function(response) {
                            if (response.status == 409) {
                                this.model.trigger('invalid', this.model, {name: response.responseText});
                            }
                        }, this))
                        .always(_.bind(function() {
                            controls.attr('disabled', false);
                        }, this));
                }
            }
        },
        showValidationError: function(model, error) {
            this.$('input[name=cluster_name]').addClass('error');
            this.$('.text-error').text(_.values(error).join('; ')).show();
        },
        onClusterNameInputKeydown: function(e) {
            this.$('input[name=cluster_name]').removeClass('error');
            this.$('.text-error').hide();
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.model.on('change:name', this.render, this);
            this.model.on('invalid', this.showValidationError, this);
        },
        render: function() {
            this.$el.html(this.template({cluster: this.model})).i18n();
            return this;
        }
    });

    ResetEnvironmentAction = Backbone.View.extend({
        className: 'span4 action-item-placeholder',
        template: _.template(resetEnvironmentTemplate),
        events: {
            'click .action-btn:not([disabled])': 'applyAction'
        },
        applyAction: function() {
            this.registerSubView(new dialogViews.DeploymentTaskDialog({model: this.model, action: 'reset'})).render();
        },
        getDescriptionKey: function() {
            if (this.model.task('reset_environment', 'running')) { return 'repeated_reset_disabled'; }
            if (this.tab.isLocked()) { return 'action_disabled_for_deploying_cluster'; }
            if (this.model.get('status') == 'new') { return 'action_disabled_for_new_cluster'; }
            return 'reset_environment_description';
        },
        initialize: function(options) {
            _.defaults(this, options);
        },
        render: function() {
            this.$el.html(this.template({
                cluster: this.model,
                isResetDisabled: this.model.get('status') == 'new' || this.tab.isLocked(),
                descriptionKey: this.getDescriptionKey()})).i18n();
            return this;
        }
    });

    DeleteEnvironmentAction = Backbone.View.extend({
        className: 'span4 action-item-placeholder',
        template: _.template(deleteEnvironmentTemplate),
        events: {
            'click .action-btn': 'applyAction'
        },
        applyAction: function() {
            this.registerSubView(new dialogViews.RemoveClusterDialog({model: this.model})).render();
        },
        initialize: function(options) {
            _.defaults(this, options);
        },
        render: function() {
            this.$el.html(this.template({cluster: this.model})).i18n();
            return this;
        }
    });

    UpdateEnvironmentAction = Backbone.View.extend({
        className: 'span12 action-item-placeholder action-update',
        events: {
            'click .action-btn:not([disabled])': 'applyAction'
        },
        bindings: {
            'select[name=update_release]': {
                observe: 'pending_release_id',
                selectOptions: {
                    collection:function() {
                        return this.releases.map(function(release) {
                            return {value: release.id, label: release.get('name') + ' (' + release.get('version') + ')'};
                        });
                    },
                    defaultOption: {
                        label: $.t('cluster_page.actions_tab.choose_release'),
                        value: null
                    }
                },
                visible: function() { return this.releases.length != 0 && !this.isUpdateDisabled; }
            },
            '.action-btn': {
                attributes: [{
                    name: 'disabled',
                    observe: 'pending_release_id',
                    onGet: function(value) {
                        if (this.actionName == 'update') {
                            return _.isNull(value) || this.isUpdateDisabled;
                        }
                        return this.tab.isLocked();
                    }
                }]
            }
        },
        applyAction: function() {
            if (this.actionName == 'rollback') {
                this.model.set({pending_release_id: this.model.get('release_id')});
            }
            this.registerSubView(new dialogViews.DeploymentTaskDialog({model: this.model, action: this.actionName})).render();
        },
        getDescriptionKey: function() {
            if (this.model.task('update', 'running')) { return 'repeated_update_disabled'; }
            if (this.tab.isLocked()) { return 'action_disabled_for_deploying_cluster'; }
            if (this.model.get('status') == 'new') { return 'action_disabled_for_new_cluster'; }
            return 'update_environment_description';
        },
        getReleasesForUpdate: function() {
            this.releases = new models.Releases();
            var operatingSystem =  this.model.get('release').get('operating_system');
            var version =  this.model.get('release').get('version');
            this.releases.parse = function(response) {
                return _.filter(response, function(release) {
                    return _.contains(release.can_update_versions, version) && release.operating_system == operatingSystem;
                });
            };
            this.releases.fetch().done(_.bind(this.render, this));
        },
        initialize:  function(options) {
            _.defaults(this, options);
            this.actionName = this.model.get('status') == 'update_error' ? 'rollback' : 'update';
            this.template = this.actionName == 'update' ? _.template(updateEnvironmentTemplate) : _.template(rollbackEnvironmentTemplate);
            this.getReleasesForUpdate();
            this.isUpdateDisabled = this.model.get('status') == 'new' || this.tab.isLocked();
        },
        render: function() {
            this.$el.html(this.template({
                cluster: this.model,
                releases: this.releases,
                isUpdateDisabled: this.isUpdateDisabled,
                descriptionKey: this.getDescriptionKey()})).i18n();
            this.stickit();
            return this;
        }
    });

    return ActionsTab;
});
