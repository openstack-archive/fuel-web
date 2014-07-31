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
    'text!templates/cluster/actions_tab.html',
    'text!templates/cluster/actions_rename.html',
    'text!templates/cluster/actions_reset.html',
    'text!templates/cluster/actions_delete.html',
    'text!templates/cluster/actions_update.html'
],
function(utils, models, commonViews, dialogViews, actionsTabTemplate, renameEnvironmentTemplate, resetEnvironmentTemplate, deleteEnvironmentTemplate, updateEnvironmentTemplate) {
    'use strict';

    var ActionsTab, Action, RenameEnvironmentAction, ResetEnvironmentAction, DeleteEnvironmentAction, UpdateEnvironmentAction;

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
                UpdateEnvironmentAction
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
            var task = this.model.task({group: 'deployment', status: 'running'});
            if (task) {
                if (_.contains(task.get('name'), action)) { return 'repeated_' + action + '_disabled'; }
                return action + '_disabled_for_deploying_cluster';
            }
            if ((action == 'reset' && this.model.get('status') == 'new') || (action == 'update' && this.model.get('status') != 'operational')) {
                return action + '_disabled_for_new_cluster';
            }
            return action + '_environment_description';
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.model.on('change:status', this.render, this);
            this.model.get('tasks').bindToView(this, [{group: 'deployment'}], function(task) {
                task.on('change:status', this.render, this);
            });
        },
        render: function() {
            this.$el.html(this.template({cluster: this.model, locked: this.isLocked()})).i18n();
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
                            } else {
                                utils.showErrorDialog({title: $.t('cluster_page.actions_tab.rename_error.title')});
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
            this.registerSubView(new dialogViews.ResetEnvironmentDialog({model: this.model, action: 'reset'})).render();
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

    var releases = new models.Releases();
    UpdateEnvironmentAction = Action.extend({
        className: 'span12 action-item-placeholder action-update',
        template: _.template(updateEnvironmentTemplate),
        releases: releases,
        stickitAction: function() {
            var releasesForUpdate = this.getReleasesForUpdate();
            var bindings = {
                '.action-btn': {
                    attributes: [{
                        name: 'disabled',
                        observe: 'pending_release_id',
                        onGet: function() {
                            return (this.action == 'update' && !releasesForUpdate.length) || this.isLocked();
                        }
                    }]
                }
            };
            if (this.action == 'update') {
                bindings['select[name=update_release]'] = {
                    observe: 'pending_release_id',
                    selectOptions: {
                        collection:function() {
                            return releasesForUpdate.map(function(release) {
                                return {value: release.id, label: release.get('name') + ' (' + release.get('version') + ')'};
                            });
                        }
                    },
                    visible: function() {
                        return releasesForUpdate.length && !this.isLocked();
                    }
                };
            }
            this.stickit(this.model, bindings);
        },
        applyAction: function() {
            var isDowngrade = _.contains(this.model.get('release').get('can_update_from_versions'), this.releases.findWhere({id: this.model.get('pending_release_id') || this.model.get('release_id')}).get('version'));
            this.registerSubView(new dialogViews.UpdateEnvironmentDialog({model: this.model, action: this.action, isDowngrade: isDowngrade})).render();
        },
        getReleasesForUpdate: function() {
            var releaseId = this.model.get('release_id');
            var operatingSystem = this.model.get('release').get('operating_system');
            var version = this.model.get('release').get('version');
            var releasesForDowngrade = this.model.get('release').get('can_update_from_versions');
            return this.releases.filter(function(release) {
                return (_.contains(releasesForDowngrade, release.get('version')) || _.contains(release.get('can_update_from_versions'), version)) && release.get('operating_system') == operatingSystem && release.get('id') != releaseId;
            });
        },
        isLocked: function() {
            return (this.model.get('status') != 'operational' && this.model.get('status') != 'update_error') || this.constructor.__super__.isLocked.apply(this);
        },
        initialize: function(options) {
            this.constructor.__super__.initialize.apply(this);
            this.model.on('change:release', this.stickitAction, this);
            if (!this.releases.length) {
                this.releases.deferred = this.releases.fetch();
                this.releases.deferred.done(_.bind(this.render, this));
            }
        },
        getDescription: function() {
            var releasesForUpdate = this.getReleasesForUpdate();
            if (this.action == 'update' && this.model.get('status') == 'operational' && releasesForUpdate.length == 0) {
                return 'no_releases_to_update_message';
            }
            if (this.action == 'rollback') {
                return 'rollback_message';
            }
            return this.constructor.__super__.getDescription.call(this, this.action);
        },
        render: function() {
            this.action = this.model.get('status') == 'update_error' ? 'rollback' : 'update';
            this.$el.html(this.template({
                action: this.action,
                cluster: this.model,
                releases: releases,
                locked: this.isLocked(),
                descriptionKey: this.getDescription()
            })).i18n();
            this.stickitAction();
            // Need to set pending_release_id cluster attr
            this.$('select[name=update_release]').trigger('change');
            return this;
        }
    });

    return ActionsTab;
});
