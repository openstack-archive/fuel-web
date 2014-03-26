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
            return !_.isEqual(this.settings.toJSON().editable, this.initialSettings);
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
            return this.settings.save(null, {patch: true, wait: true})
                .done(_.bind(this.updateInitialSettings, this))
                .always(_.bind(function() {
                    this.render();
                    this.model.fetch();
                }, this))
                .fail(_.bind(function() {
                    this.defaultButtonsState(false);
                    utils.showErrorDialog({title: $.t('cluster_page.settings_tab.title')});
                }, this));
        },
        revertChanges: function() {
            this.loadInitialSettings();
        },
        beforeTearDown: function() {
            this.loadInitialSettings();
        },
        loadDefaults: function() {
            this.disableControls();
            this.settings.fetch({url: _.result(this.settings, 'url') + '/defaults'}).always(_.bind(function() {
                this.render();
                this.calculateButtonsState();
            }, this));
        },
        updateInitialSettings: function() {
            this.initialSettings = _.cloneDeep(this.settings.attributes);
        },
        loadInitialSettings: function() {
            this.settings.set(this.initialSettings);
        },
        onSettingChange: function() {
            this.$('input.error').removeClass('error');
            this.$('.description').show();
            this.$('.validation-error').hide();
            this.settings.isValid();
            this.calculateButtonsState();
        },
        composeBindings: function() {
            var bindings = {};
            _.each(this.settings.attributes, function(group, groupName) {
                if (this.settings.get(groupName + '.metadata.toggleable')) {
                    bindings['input[name="' + groupName + '.enabled' + '"]'] = groupName + '.metadata.enabled';
                }
                _.each(group, function(setting, settingName) {
                    if (settingName == 'metadata') {return;}
                    bindings['input[name="' + groupName + '.' + settingName + '"]'] = {
                        observe: groupName + '.' + settingName + '.value',
                        attributes: [{name: 'disabled', observe: groupName + '.' + settingName + '.disabled'}]
                    };
                }, this);
            }, this);
            this.stickit(this.settings, bindings);
        },
        checkDependentSettings: function(settingPath, composeListeners, callback) {
            var hasActiveDependentSetting = false;
            _.each(this.settings.attributes, function(group, groupName) {
                _.each(group, function(setting, settingName) {
                    var isDependent = _.filter(setting.depends, function(dependency) {return !_.isUndefined(dependency['settings:' + settingPath]); }).length;
                    if (isDependent) {
                        hasActiveDependentSetting = hasActiveDependentSetting || setting.value;
                        if (composeListeners) {
                            utils.parseModelPath(groupName + '.' + settingName + '.value', this.models).change(callback);
                        }
                    }
                }, this);
            }, this);
            return hasActiveDependentSetting;
        },
        calculateSettingDisabledState: function(groupName, settingName, composeListeners) {
            var settingPath = groupName + '.' + settingName;
            this.models = {
                settings: this.settings,
                cluster: this.model,
                default: this.settings
            };
            var disable = false;
            var callback = _.bind(function() { this.calculateSettingDisabledState(groupName, settingName); }, this);
            _.each(utils.parseModelPath(settingPath + '.depends', this.models).get(), function(dependency) {
                var path = _.keys(dependency)[0] + '.value';
                disable = disable || utils.parseModelPath(path, this.models).get() != _.values(dependency)[0];
                if (composeListeners) {
                    utils.parseModelPath(path, this.models).change(callback);
                }
            }, this);
            disable = disable || this.checkDependentSettings(settingPath, composeListeners, callback);
            _.each(utils.parseModelPath(settingPath + '.conflicts', this.models).get(), function(conflict) {
                var path = _.keys(conflict)[0] + '.value';
                disable = disable || utils.parseModelPath(path, this.models).get() == _.values(conflict)[0];
                if (composeListeners) {
                    utils.parseModelPath(path, this.models).change(callback);
                }
            }, this);
            if (utils.parseModelPath(groupName + '.metadata.toggleable', this.models).get()) {
                disable = disable || !utils.parseModelPath(groupName + '.metadata.enabled', this.models).get();
                if (composeListeners) {
                    utils.parseModelPath(groupName + '.metadata.enabled', this.models).change(callback);
                }
            }
            utils.parseModelPath(settingPath + '.disabled', this.models).set(disable);
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            this.$el.html(this.template({
                loading: this.loading,
                locked: this.isLocked()
            })).i18n();
            if (this.loading.state() != 'pending') {
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
                this.composeBindings();
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
            this.settings = this.model.get('settings');
            this.settings.on('change', this.onSettingChange, this);
            this.settings.on('invalid', function(model, errors) {
                _.each(errors, function(error) {
                    var input = this.$('input[name="' + error.field + '"]');
                    input.addClass('error').parent().siblings('.validation-error').text(error.message);
                    input.parent().siblings('.parameter-description').toggle();
                }, this);
            }, this);
            (this.loading = this.settings.fetch({cache: true})).done(_.bind(this.updateInitialSettings, this));
            if (this.loading.state() == 'pending') {
                this.loading.done(_.bind(function() {
                    _.each(this.settings.attributes, function(group, groupName) {
                        _.each(group, function(setting, settingName) {
                            this.calculateSettingDisabledState(groupName, settingName, true);
                        }, this);
                    }, this);
                    this.render();
                }, this));
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
