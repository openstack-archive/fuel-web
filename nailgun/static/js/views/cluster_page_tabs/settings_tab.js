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
            return !_.isEqual(this.settings.toJSON(), this.initialSettings.toJSON());
        },
        events: {
            'click .btn-apply-changes:not([disabled])': 'applyChanges',
            'click .btn-revert-changes:not([disabled])': 'revertChanges',
            'click .btn-load-defaults:not([disabled])': 'loadDefaults'
        },
        calculateButtonsState: function() {
            var hasChanges = this.hasChanges();
            this.$('.btn-revert-changes').attr('disabled', !hasChanges);
            this.$('.btn-apply-changes').attr('disabled', !hasChanges || this.settings.validationError);
            this.$('.btn-load-defaults').attr('disabled', this.isLocked());
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
            this.settings.fetch({url: _.result(this.settings, 'url') + '/defaults'}).always(_.bind(this.render, this));
        },
        updateInitialSettings: function() {
            this.initialSettings.set(this.settings.attributes);
        },
        loadInitialSettings: function() {
            this.settings.set(this.initialSettings.attributes);
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
                    bindings['input[name="' + groupName + '.enabled' + '"]'] = {
                        observe: groupName + '.metadata.enabled',
                        attributes: [{name: 'disabled', onGet: _.bind(this.isLocked, this)}]
                    };
                }
                _.each(group, function(setting, settingName) {
                    if (settingName == 'metadata') {return;}
                    var settingPath = groupName + '.' + settingName;
                    bindings['input[name="' + settingPath + '"]'] = {
                        observe: settingPath + '.value',
                        attributes: [{
                            name: 'disabled',
                            observe: [groupName + '.metadata.enabled', settingPath + '.disabled'],
                            onGet: _.bind(function(value) {
                                var isSettingGroupDisabled = !(_.isUndefined(value[0]) || value[0]);
                                return this.isLocked() || isSettingGroupDisabled || value[1];
                            }, this)
                        }]
                    };
                    _.each(setting.values, function(option, index) {
                        bindings['input[name="' + settingPath + '"][value="' + option.data + '"]'] = {
                            attributes: [{
                                name: 'disabled',
                                observe: [groupName + '.metadata.enabled', settingPath + '.disabled', settingPath + '.values'],
                                onGet: _.bind(function(value) {
                                    var isSettingGroupDisabled = !(_.isUndefined(value[0]) || value[0]);
                                    return this.isLocked() || isSettingGroupDisabled || value[1] || value[2][index].disabled;
                                }, this)
                            }]
                        };
                    }, this);
                }, this);
            }, this);
            this.stickit(this.settings, bindings);
        },
        handleCondition: function(groupName, settingName, callback, condition, isDisabled, isConflict) {
            var path = _.keys(condition)[0];
            var isEqual = utils.parseModelPath(path, this.configModels).get() == condition[path];
            isDisabled = isDisabled || isConflict ? isEqual : !isEqual;
            if (this.composeListeners) {
                utils.parseModelPath(path, this.configModels).change(callback);
            }
            return isDisabled;
        },
        checkDependentSettings: function(settingPath, callback) {
            var disabled = false;
            _.each(this.settings.attributes, function(group, groupName) {
                _.each(group, function(setting, settingName) {
                    // setting is disabled if it's dependent setting is chosen
                    var isActiveDependentSetting = false;
                    var isDependentSetting = !!_.filter(setting.depends, function(dep) {return dep['settings:' + settingPath + '.value'];}).length;
                    isActiveDependentSetting = isActiveDependentSetting || (setting.value === true && isDependentSetting);
                    _.each(setting.values, function(option) {
                        var isDependentOption = !!_.filter(option.depends, function(dep) {return dep['settings:' + settingPath + '.value'];}).length;
                        isDependentSetting = isDependentSetting || isDependentOption;
                        isActiveDependentSetting = isActiveDependentSetting || (setting.value == option.data && isDependentOption);
                    });
                    if (isDependentSetting && this.composeListeners) {
                        this.settings.on('change:' + groupName + '.' + settingName + '.value', callback);
                    }
                    disabled = disabled || isActiveDependentSetting;
                }, this);
            }, this);
            return disabled;
        },
        calculateSettingDisabledState: function(groupName, settingName) {
            var settingPath = groupName + '.' + settingName;
            var isSettingDisabled = false;
            var callback = _.bind(this.calculateSettingDisabledState, this, groupName, settingName);
            var handleCondition = _.bind(this.handleCondition, this, groupName, settingName, callback);
            _.each(this.settings.get(settingPath + '.depends'), function(dependency) {
                isSettingDisabled = handleCondition(dependency, isSettingDisabled, false);
            });
            isSettingDisabled = isSettingDisabled || this.checkDependentSettings(settingPath, callback);
            _.each(this.settings.get(settingPath + '.conflicts'), function(conflict) {
                isSettingDisabled = handleCondition(conflict, isSettingDisabled, true);
            });
            this.settings.set(settingPath + '.disabled', isSettingDisabled);
            _.each(this.settings.get(settingPath + '.values'), function(value, index) {
                var isOptionDisabled = false;
                _.each(value.depends, function(dependency) {
                    isOptionDisabled = handleCondition(dependency, isOptionDisabled, false);
                });
                _.each(value.conflicts, function(conflict) {
                    isOptionDisabled = handleCondition(conflict, isOptionDisabled, true);
                });
                var settingValues = _.cloneDeep(this.settings.get(settingPath + '.values'));
                settingValues[index].disabled = isOptionDisabled;
                this.settings.set(settingPath + '.values', settingValues);
            }, this);
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
                this.settings.isValid();
                this.calculateButtonsState();
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
            this.initialSettings = new models.Settings();
            this.settings = this.model.get('settings');
            this.settings.on('invalid', function(model, errors) {
                _.each(errors, function(error) {
                    var input = this.$('input[name="' + error.field + '"]');
                    input.addClass('error').parent().siblings('.validation-error').text(error.message);
                    input.parent().siblings('.parameter-description').toggle();
                }, this);
            }, this);
            this.configModels = {settings: this.settings, cluster: this.model, default: this.settings};
            (this.loading = this.settings.fetch({cache: true})).done(_.bind(function() {
                this.updateInitialSettings();
                this.composeListeners = true;
                _.each(this.settings.attributes, function(group, groupName) {
                    _.each(group, function(setting, settingName) {
                        this.calculateSettingDisabledState(groupName, settingName);
                    }, this);
                }, this);
                this.composeListeners = false;
                this.settings.on('change', this.onSettingChange, this);
            }, this));
            if (this.loading.state() == 'pending') {
                this.loading.done(_.bind(this.render, this));
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
