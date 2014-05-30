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

    var ActionsTab, Action, RenameEnvironmentAction, ResetEnvironmentAction, DeleteEnvironmentAction, UpdateEnvironmentAction, RollbackEnvironmentAction;

    ActionsTab = commonViews.Tab.extend({
        template: _.template(actionsTabTemplate),
        initialize: function(options) {
            _.defaults(this, options);
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            this.$el.html(this.template()).i18n();
            var actions = [
                RenameEnvironmentAction,
                ResetEnvironmentAction,
                DeleteEnvironmentAction,
                this.model.get('status') == 'update_error' ? RollbackEnvironmentAction : UpdateEnvironmentAction
            ];
            _.each(actions, function(ActionConstructor) {
                var actionView = new ActionConstructor({model: this.model});
                this.registerSubView(actionView);
                this.$('.environment-actions').append(actionView.render().el);
            }, this);
            return this;
        }
    });

    Action = Backbone.View.extend({
        className: 'span4 action-item-placeholder',
        events: {
            'click .action-btn:not([disabled])': 'applyAction'
        },
        isLocked: function() {
            return !!this.model.tasks({group: 'deployment', status: 'running'}).length;
        },
        getDescription: function(action) {
            if (this.model.get('status') == 'new') { return action + '_disabled_for_new_cluster'; }
            var task = this.model.task('update', 'running') || this.model.task('reset_environment', 'running');
            if (task) { return 'repeated_' + action + '_disabled'; }
            if (!!this.model.tasks({group: 'deployment', status: 'running'}).length) { return action + '_disabled_for_deploying_cluster'; }
            return action + '_environment_description';
        },
        initialize:  function(options) {
            _.defaults(this, options);
            this.model.on('change:status', this.render, this);
            this.model.get('tasks').bindToView(this, [{group: 'deployment'}], function(task) {
                task.on('change:status', this.render, this);
            });
        },
        render: function() {
            this.$el.html(this.template({cluster: this.model})).i18n();
            return this;
        }
    });

    RenameEnvironmentAction = Action.extend({
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
            this.constructor.__super__.initialize.apply(this);
            this.model.on('change:name', this.render, this);
            this.model.on('invalid', this.showValidationError, this);
        }
    });

    ResetEnvironmentAction = Action.extend({
        action: 'reset',
        template: _.template(resetEnvironmentTemplate),
        applyAction: function() {
            this.registerSubView(new dialogViews.DeploymentTaskDialog({model: this.model, action: 'reset'})).render();
        },
        isLocked: function() {
            return this.model.get('status') == 'new' || this.constructor.__super__.isLocked.apply(this);
        },
        render: function() {
            this.$el.html(this.template({
                cluster: this.model,
                isResetDisabled: this.isLocked(),
                descriptionKey: this.getDescription(this.action)})).i18n();
            return this;
        }
    });

    DeleteEnvironmentAction = Action.extend({
        template: _.template(deleteEnvironmentTemplate),
        applyAction: function() {
            this.registerSubView(new dialogViews.RemoveClusterDialog({model: this.model})).render();
        }
    });

    UpdateEnvironmentAction = Action.extend({
        action: 'update',
        className: 'span12 action-item-placeholder action-update',
        template: _.template(updateEnvironmentTemplate),
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
                visible: function() { return this.releases.length != 0 && !this.isLocked(); }
            },
            '.action-btn': {
                attributes: [{
                    name: 'disabled',
                    observe: 'pending_release_id',
                    onGet: function(value) {
                        return _.isNull(value) || this.isLocked();
                    }
                }]
            }
        },
        applyAction: function() {
            var deferred = this.model.save({pending_release_id: this.model.get('pending_release_id')}, {patch: true, wait: true});
            if (deferred) {
                deferred.done(_.bind(function() {
                    this.registerSubView(new dialogViews.DeploymentTaskDialog({model: this.model, action: this.action})).render();
                }, this));
            }
        },
        getReleasesForUpdate: function() {
            this.releases = new models.Releases();
            var releaseId = this.model.get('release_id');
            var operatingSystem =  this.model.get('release').get('operating_system');
            var version = this.model.get('release').get('version');
            this.releases.parse = function(response) {
                return _.filter(response, function(release) {
                    return _.contains(release.can_update_from_versions, version) && release.operating_system == operatingSystem && release.id != releaseId;
                });
            };
            this.releases.deferred = this.releases.fetch();
            this.releases.deferred.done(_.bind(this.render, this));
        },
        isLocked: function() {
            return this.model.get('status') == 'new' || this.constructor.__super__.isLocked.apply(this);
        },
        initialize:  function(options) {
            this.constructor.__super__.initialize.apply(this);
            this.getReleasesForUpdate();
        },
        render: function() {
            this.$el.html(this.template({
                cluster: this.model,
                releases: this.releases,
                isUpdateDisabled: this.isLocked(),
                descriptionKey: this.getDescription(this.action)})).i18n();
            this.stickit();
            return this;
        }
    });

    RollbackEnvironmentAction = Action.extend({
        action: 'rollback',
        className: 'span12 action-item-placeholder action-update',
        template: _.template(rollbackEnvironmentTemplate),
        applyAction: function() {
            var deferred = this.model.save({pending_release_id: this.model.get('release_id')}, {patch: true, wait: true});
            if (deferred) {
                deferred.done(_.bind(function() {
                    this.registerSubView(new dialogViews.DeploymentTaskDialog({model: this.model, action: this.action})).render();
                }, this));
            }
        },
        render: function() {
            this.$el.html(this.template({isRollbackDisabled: this.isLocked()}));
            return this;
        }
    });

    return ActionsTab;
});
