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
        'text!templates/cluster/actions_common.html',
        'text!templates/cluster/actions_rename.html',
        'text!templates/cluster/actions_reset.html',
        'text!templates/cluster/actions_delete.html'
    ],
function(models, commonViews, dialogViews, actionsTabTemplate, actionTemplate, renameEnvironmentTemplate, resetEnvironmentTemplate, deleteEnvironmentTemplate) {
    'use strict';

    var ActionsTab, Action, RenameEnvironmentAction, ResetEnvironmentAction, DeleteEnvironmentAction;

    ActionsTab = commonViews.Tab.extend({
        template: _.template(actionsTabTemplate),
        initialize: function(options) {
            _.defaults(this, options);
            this.model.on('change:status', this.render, this);
            this.model.get('tasks').bindToView(this, [{group: 'deployment'}], function(task) {
                task.on('change:status', this.render, this);
            });
        },
        renderAction: function(actionData) {
            var options = _.extend({model: this.model}, actionData.options);
            var actionView = new actionData.constructor(options);
            this.registerSubView(actionView);
            this.$('.environment-actions').append(actionView.render().el).i18n();
        },
        render: function() {
            this.$el.html(this.template()).i18n();
            var actions = [
                {constructor: RenameEnvironmentAction},
                {constructor: ResetEnvironmentAction},
                {constructor: DeleteEnvironmentAction}
            ];
            _.each(actions, this.renderAction, this);
            return this;
        }
    });

    Action = Backbone.View.extend({
        className: 'span4 action-item-placeholder',
        template: _.template(actionTemplate),
        events: {
            'click .action-btn': 'applyAction'
        },
        isLocked: function() {
            return !!this.model.tasks({group: 'deployment', status: 'running'}).length;
        },
        setControlsDisabledState: function(disabled) {
           this.$('input, button').attr('disabled', disabled);
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.button = new Backbone.Model({disabled: false});
        },
        render: function() {
            this.$el.html(this.template({actionName: this.actionName, btnClass: this.btnClass})).i18n();
            this.$('.action-body').html(this.bodyTemplate(_.extend({cluster: this.model}, this.templateOptions))).i18n();
            this.stickit(this.button, this.buttonBindings);
            return this;
        }
    });

    RenameEnvironmentAction = Action.extend({
        actionName: 'rename',
        btnClass: 'success',
        bodyTemplate: _.template(renameEnvironmentTemplate),
        events: {
            'click .action-btn': 'applyAction',
            'keydown input[name=cluster_name]': 'onClusterNameInputKeydown'
        },
        applyAction: function() {
            // Backbone.Stickit is not used here to bind cluster name
            // because we don't need an immediately cluster model change
            // which reflected in breadcrumbs and other interface elements
            var name = $.trim(this.$('input[name=cluster_name]').val());
            if (name != this.model.get('name')) {
                var deferred = this.model.save({name: name}, {patch: true, wait: true});
                if (deferred) {
                    this.setControlsDisabledState(true);
                    deferred
                        .fail(_.bind(function(response) {
                            if (response.status == 409) {
                                this.model.trigger('invalid', this.model, {name: response.responseText});
                            }
                        }, this))
                        .always(_.bind(function() {
                            this.setControlsDisabledState(false);
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
            this.constructor.__super__.initialize.call(this, options);
            this.model.on('change:name', this.render, this);
            this.model.on('invalid', this.showValidationError, this);
        }
    });

    ResetEnvironmentAction = Action.extend({
        actionName: 'reset',
        btnClass: 'danger',
        bodyTemplate: _.template(resetEnvironmentTemplate),
        bindings: {
            '.action-item-description': {
                attributes: [{
                    name: 'class',
                    onGet: function() { return this.isResetDisabled ? 'unavailable' : ''; }
                }]
            },
            '.action-item-description.important': {
                visible: function() { return !this.isResetDisabled; }
            }
        },
        buttonBindings: {
            '.action-btn': {
                attributes: [{
                    name: 'disabled',
                    onGet: function() { return this.isResetDisabled; }
                }]
            }
        },
        applyAction: function() {
            this.registerSubView(new dialogViews.ResetEnvironmentDialog({model: this.model})).render();
        },
        getDescriptionKey: function() {
            if (this.model.task('reset_environment', 'running')) { return 'repeated_reset_disabled'; }
            if (this.isLocked()) { return 'reset_disabled_for_deploying_cluster'; }
            if (this.model.get('status') == 'new') { return 'reset_disabled_for_new_cluster'; }
            return 'reset_environment_description';
        },
        initialize: function(options) {
            this.constructor.__super__.initialize.call(this, options);
            this.isResetDisabled = this.model.get('status') == 'new' || this.isLocked();
            this.templateOptions = {descriptionKey: this.getDescriptionKey()};
        },
        render: function() {
            this.constructor.__super__.render.call(this);
            this.stickit();
            return this;
        }
    });

    DeleteEnvironmentAction = Action.extend({
        actionName: 'delete',
        btnClass: 'danger',
        bodyTemplate: _.template(deleteEnvironmentTemplate),
        applyAction: function() {
            this.registerSubView(new dialogViews.RemoveClusterDialog({model: this.model})).render();
        }
    });

    return ActionsTab;
});
