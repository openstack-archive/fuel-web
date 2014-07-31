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
    'react',
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
function(React, utils, models, commonViews, dialogViews, actionsTabTemplate, renameEnvironmentTemplate, resetEnvironmentTemplate, deleteEnvironmentTemplate, updateEnvironmentTemplate) {
    'use strict';
    var ActionsTab, Action, RenameEnvironmentAction, ResetEnvironmentAction, DeleteEnvironmentAction, UpdateEnvironmentAction;

    ActionsTab = React.createClass({
        mixins: [
            React.BackboneMixin('model')
        ],
        render: function() {
            return (
                <div className="wrapper">
                    <h3 className="span12">{$.t('cluster_page.actions_tab.title')}</h3>
                    <div className="row-fluid environment-actions">
                        <RenameEnvironmentAction cluster={this.props.model}/>
                    </div>
                </div>
            );
        }
    });

    RenameEnvironmentAction = React.createClass({
        applyAction: function() {
            var cluster = this.props.cluster;
            var name = this.state.text;
            if (name != cluster.get('name')) {
                var deferred = cluster.save({name: name}, {patch: true, wait: true});
                if (deferred) {
                    this.setState({disabled: true});
                    deferred
                        .fail(_.bind(function(response) {
                            if (response.status == 409) {
                                cluster.trigger('invalid', cluster, {name: response.responseText});
                            } else {
                                utils.showErrorDialog({title: $.t('cluster_page.actions_tab.rename_error.title')});
                            }
                        }, this))
                        .always(_.bind(function() {
                            this.setState({disabled: false});
                        }, this));
                }
            }
        },
        getInitialState: function() {
            return {text: this.props.cluster.get('name'), input_error_class: '', message_error_class: 'hide', disabled: false};
        },
        showValidationError: function(model, error) {
            this.setState({text: e.target.value, input_error_class: 'error', message_error_class: ''})
        },
        onClusterNameInputKeydown: function(e) {
            this.setState({text: e.target.value, input_error_class: '', message_error_class: 'hide'});
        },
        render: function() {
            return (
                <div className="span4 action-item-placeholder environment-action-form">
                      <h4>{$.t('cluster_page.actions_tab.rename_environment')}</h4>
                      <div className="action-item-controls">
                        <div className="action-body">
                          <input type="text" disabled={this.state.disabled} className={this.state.input_error_class} name="cluster_name" maxlength="50" onChange={this.onClusterNameInputKeydown} value={this.state.text} />
                          <div className="text-error {this.state.message_error_class}"></div>
                        </div>
                        <button className="btn btn-success action-btn rename-environment-btn" onClick={this.applyAction} disabled={this.state.disabled}><span>{$.t('common.rename_button')}</span></button>
                      </div>
                </div>
            );
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
            this.action = this.model.get('status') == 'update_error' ? 'rollback' : 'update';
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
