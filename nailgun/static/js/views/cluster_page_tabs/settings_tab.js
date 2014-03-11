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
    'text!templates/cluster/settings_tab.html',
    'text!templates/cluster/settings_group.html'
],
function(utils, models, commonViews, dialogViews, settingsTabTemplate, settingsGroupTemplate) {
    'use strict';
    var SettingsTab, SettingGroup;

    SettingsTab = commonViews.Tab.extend({
        template: _.template(settingsTabTemplate),
        hasChanges: function() {
            return !_.isEqual(this.settings.attributes, this.previousSettings);
        },
        events: {
            'click .btn-apply-changes:not([disabled])': 'applyChanges',
            'click .btn-revert-changes:not([disabled])': 'revertChanges',
            'click .btn-load-defaults:not([disabled])': 'loadDefaults'
        },
        calculateButtonsState: function() {
            this.$('.btn-revert-changes').attr('disabled', !this.hasChanges());
            this.$('.btn-apply-changes').attr('disabled', !this.hasChanges() || this.settings.validationError);
            this.$('.btn-load-defaults').attr('disabled', false);
        },
        disableControls: function() {
            this.$('.btn, input, select').attr('disabled', true);
        },
        isLocked: function() {
            return this.model.task({group: 'deployment', status: 'running'}) || !this.model.isAvailableForSettingsChanges();
        },
        applyChanges: function() {
            this.disableControls();
            return this.model.get('settings').save({editable: _.cloneDeep(this.settings.attributes)}, {patch: true, wait: true, url: _.result(this.model, 'url') + '/attributes'})
                .done(_.bind(this.setInitialData, this))
                .always(_.bind(function() {
                    this.render();
                    this.model.fetch();
                }, this))
                .fail(_.bind(function() {
                    this.defaultButtonsState(false);
                    utils.showErrorDialog({title: 'OpenStack Settings'});
                }, this));
        },
        revertChanges: function() {
            this.setInitialData();
            this.render();
        },
        loadDefaults: function() {
            this.disableControls();
            this.settings.fetch({url: _.result(this.model, 'url') + '/attributes/defaults'}).always(_.bind(function() {
                this.render();
                this.calculateButtonsState();
            }, this));
        },
        onSettingChange: function() {
            this.$('input.error').removeClass('error');
            this.$('.description').show();
            this.$('.validation-error').hide();
            this.settings.isValid();
            //this.checkDependencies();
            this.calculateButtonsState();
        },
        setInitialData: function() {
            this.previousSettings = _.cloneDeep(this.model.get('settings').get('editable'));
            this.settings = new models.Settings(this.previousSettings);
            this.settings.parse = function(response) {return response.editable;};
            this.settings.on('change', this.onSettingChange, this);
            this.settings.on('invalid', function(model, errors) {
                _.each(errors, function(error) {
                    var input = this.$('input[name="' + error.field + '"]');
                    input.addClass('error').parent().siblings('.validation-error').text(error.message);
                    input.parent().siblings('.parameter-description').toggle();
                }, this);
            }, this);
        },
        composeBindings: function() {
            this.bindings = {};
            _.each(this.settings.attributes, function(group, groupName) {
                if (this.settings.get(groupName + '.metadata.toggleable')) {
                    this.bindings['input[name="' + groupName + '.enabled' + '"]'] = groupName + '.metadata.enabled';
                }
                _.each(group, function(setting, settingName) {
                    if (settingName == 'metadata') {return;}
                    var settingBindings = this.bindings['input[name="' + groupName + '.' + settingName + '"]'] = {
                        observe: groupName + '.' + settingName + '.value'
                    };
                    if (this.settings.get(groupName + '.metadata.toggleable')) {
                        settingBindings.attributes = [{
                            name: 'disabled',
                            observe: groupName + '.metadata.enabled',
                            onGet: function(value) {
                                return !value;
                            }
                        }];
                    }
                    /*settingBindings.onSet = _.bind(function(value) {
                        _.each(setting.conflicts, function(conflict) {
                            var option = conflict.option.split(':');
                            this.$('input[name="' + option[1] + '"]').attr('disabled', value);
                        }, this);
                        _.each(this.settings, function(group, groupName) {
                            _.each(group, function(setting, settingName) {
                                // collect al settings, which dependes on it.
                            });
                        });
                    }, this);*/
                }, this);
            }, this);
            this.stickit(this.settings);
        },
        checkDependencies: function() {
            _.each(this.settings.attributes, function(group, groupName) {
                _.each(group, function(setting, settingName) {
                    _.each(setting.deps, function(dependency) {
                        var option = dependency.option.split(':');
                        var values = _.isUndefined(dependency.values) ? utils.composeList(dependency.values) : [true];
                        var disable;
                        if (option[0] == 'cluster') {
                            disable = !_.contains(values, this.model.get(option[1]));
                        } else if (option[0] == 'settings') {
                            disable = !_.contains(dependency.values, this.settings.get(option[1]).value);
                        }
                        this.$('input[name="' + groupName + '.' + settingName + '"]').attr('disabled', disable);
                    }, this);
                }, this);
            }, this);
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            this.$el.html(this.template({cluster: this.model, locked: this.isLocked()})).i18n();
            if (this.model.get('settings').deferred.state() != 'pending') {
                this.$('.settings').html('');
                var sortedSettings = _.sortBy(_.keys(this.settings.attributes), _.bind(function(setting) {
                    return this.settings.get(setting + '.metadata.weight');
                }, this));
                _.each(sortedSettings, function(settingGroup) {
                    var settingGroupView = new SettingGroup({
                        settings: this.settings.get(settingGroup),
                        groupName: settingGroup,
                        locked: this.isLocked()
                    });
                    this.registerSubView(settingGroupView);
                    this.$('.settings').append(settingGroupView.render().el);
                }, this);
            }
            if (this.settings) {
                this.composeBindings();
                //this.checkDependencies();
            }
            return this;
        },
        bindTaskEvents: function(task) {
            return task.match({group: 'deployment'}) ? task.on('change:status', this.render, this) : null;
        },
        onNewTask: function(task) {
            return this.bindTaskEvents(task) && this.render();
        },
        initialize: function(options) {
            this.model.on('change:status', this.render, this);
            this.model.get('tasks').each(this.bindTaskEvents, this);
            this.model.get('tasks').on('add', this.onNewTask, this);
            if (!this.model.get('settings')) {
                this.model.set({'settings': new models.Settings()}, {silent: true});
                this.model.get('settings').deferred = this.model.get('settings').fetch({url: _.result(this.model, 'url') + '/attributes'});
                this.model.get('settings').deferred
                    .done(_.bind(function() {
                        this.setInitialData();
                        this.render();
                    }, this));
            } else {
                this.setInitialData();
            }
        }
    });

    SettingGroup = Backbone.View.extend({
        template: _.template(settingsGroupTemplate),
        className: 'fieldset-group wrapper',
        events: {
            'click span.add-on': 'showPassword'
        },
        showPassword: function(e) {
            var input = this.$(e.currentTarget).prev();
            input.attr('type', input.attr('type') == 'text' ? 'password' : 'text');
            this.$(e.currentTarget).find('i').toggle();
        },
        render: function() {
            this.$el.html(this.template(this.options)).i18n();
            return this;
        }
    });

    return SettingsTab;
});
