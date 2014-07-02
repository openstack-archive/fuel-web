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
    'view_mixins',
    'views/common',
    'views/dialogs',
    'text!templates/cluster/settings_tab.html',
    'text!templates/cluster/settings_group.html'
],
function(utils, models, viewMixins, commonViews, dialogViews, settingsTabTemplate, settingsGroupTemplate) {
    'use strict';
    var SettingsTab, SettingGroup;

    SettingsTab = commonViews.Tab.extend({
        template: _.template(settingsTabTemplate),
        mixins: [viewMixins.toggleablePassword],
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
                    this.calculateButtonsState();
                    utils.showErrorDialog({
                        title: $.t('cluster_page.settings_tab.settings_error.title'),
                        message: $.t('cluster_page.settings_tab.settings_error.saving_warning')
                    });
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
            this.settings.fetch({url: _.result(this.settings, 'url') + '/defaults'})
                .fail(function() {
                    utils.showErrorDialog({
                        title: $.t('cluster_page.settings_tab.settings_error.title'),
                        message: $.t('cluster_page.settings_tab.settings_error.load_defaults_warning')
                    });
                })
                .always(_.bind(this.render, this));
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
                if (!group.metadata.visible) { return; }
                if (group.metadata.toggleable) {
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
                                var isSettingGroupActive = value[0];
                                var isSettingDisabled = value[1];
                                return this.isLocked() || isSettingGroupActive === false || isSettingDisabled;
                            }, this)
                        }]
                    };
                    _.each(setting.values, function(option, index) {
                        bindings['input[name="' + settingPath + '"][value="' + option.data + '"]'] = {
                            attributes: [{
                                name: 'disabled',
                                observe: [groupName + '.metadata.enabled', settingPath + '.disabled', settingPath + '.values'],
                                onGet: _.bind(function(value) {
                                    var isSettingGroupActive = value[0];
                                    var isSettingDisabled = value[1];
                                    var settingValues = value[2];
                                    return this.isLocked() || isSettingGroupActive === false || isSettingDisabled || settingValues[index].disabled;
                                }, this)
                            }]
                        };
                    }, this);
                }, this);
            }, this);
            this.stickit(this.settings, bindings);
        },
        checkActiveDependentSettings: function(settingPath) {
            var isDependent = function(restriction) {
                return _.contains(restriction, 'settings:' + settingPath + '.value');
            };
            return _.any(this.settings.attributes, function(group, groupName) {
                if (!group.metadata.visible) { return false; }
                return _.any(group, function(setting, settingName) {
                    if (groupName + '.' + settingName == settingPath) { return false; }
                    var hasDependentOption = _.any(setting.values, function(value) {
                        return setting.value == value.data && _.any(value.restrictions, isDependent);
                    });
                    return hasDependentOption || (setting.value === true && _.any(setting.restrictions, isDependent));
                });
            });
        },
        calculateSettingDisabledState: function(settingPath) {
            var setting = this.settings.get(settingPath);
            var handleRestriction = _.bind(function(restriction) {
                return utils.evaluateExpression(restriction, this.configModels).value;
            }, this);
            this.settings.set(settingPath + '.disabled', setting.hasDependentRole || _.any(setting.restrictions, handleRestriction) || this.checkActiveDependentSettings(settingPath));
            if (!setting.disabled) {
                _.each(setting.values, function(value, index) {
                    var values = _.cloneDeep(setting.values);
                    values[index].disabled = _.any(value.restrictions, handleRestriction);
                    this.settings.set(settingPath + '.values', values);
                }, this);
            }
        },
        composeListeners: function(settingPath) {
            var callback = _.bind(this.calculateSettingDisabledState, this, settingPath);
            var collectRestrictions = function(setting) {
                return _.flatten(_.compact(setting.restrictions, _.pluck(setting.values, 'restrictions')));
            };
            _.each(collectRestrictions(this.settings.get(settingPath)), function(restriction) {
                var evaluatedRestriction = utils.evaluateExpression(restriction, this.configModels);
                _.invoke(evaluatedRestriction.modelPaths, 'change', callback);
            }, this);
            // handle dependent settings
            _.each(this.settings.attributes, function(group, groupName) {
                if (!group.metadata.visible) { return; }
                _.each(group, function(setting, settingName) {
                    if (groupName + '.' + settingName == settingPath) { return; }
                    var isDependent = _.any(collectRestrictions(setting), function(restriction) {
                        return _.contains(restriction, 'settings:' + settingPath + '.value');
                    });
                    if (isDependent) {
                        this.settings.on('change:' + groupName + '.' + settingName + '.value', callback);
                    }
                }, this);
            }, this);
        },
        checkDependentRoles: function(settingPath) {
            var setting = this.settings.get(settingPath);
            var rolesData = this.model.get('release').get('roles_metadata');
            setting.hasDependentRole = _.any(this.model.get('release').get('roles'), function(role) {
                var hasSatisfiedDependencies = _.any(rolesData[role].depends, function(dependency) {
                    var dependencyValue = dependency.condition['settings:' + settingPath + '.value'];
                    return !_.isUndefined(dependencyValue) && dependencyValue == setting.value;
                });
                var assignedNodes = this.model.get('nodes').filter(function(node) { return node.hasRole(role); });
                return hasSatisfiedDependencies && assignedNodes.length;
            }, this);
        },
        renderSettingGroup: function(groupName) {
            var settings = this.settings.get(groupName);
            if (!settings.metadata.visible) { return; }
            var settingGroupView = new SettingGroup({
                settings: settings,
                groupName: groupName,
                locked: this.isLocked()
            });
            this.registerSubView(settingGroupView);
            this.$('.settings').append(settingGroupView.render().el);
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
                _.each(sortedSettings, this.renderSettingGroup, this);
                this.composeBindings();
                this.onSettingChange();
            }
            return this;
        },
        initialize: function(options) {
            this.model.on('change:status', this.render, this);
            this.model.get('tasks').bindToView(this, [{group: 'deployment'}], function(task) {
                task.on('change:status', this.render, this);
            });
            this.initialSettings = new models.Settings();
            this.settings = this.model.get('settings');
            this.settings.on('invalid', function(model, errors) {
                _.each(errors, function(error) {
                    var input = this.$('input[name="' + error.field + '"]');
                    input.addClass('error').parent().siblings('.validation-error').text(error.message).show();
                    input.parent().siblings('.description').hide();
                }, this);
            }, this);
            (this.loading = $.when(this.settings.fetch({cache: true}), this.model.get('networkConfiguration').fetch({cache: true}))).done(_.bind(function() {
                this.updateInitialSettings();
                this.configModels = {
                    cluster: this.model,
                    settings: this.settings,
                    networking_parameters: this.model.get('networkConfiguration').get('networking_parameters'),
                    default: this.settings
                };
                this.settings.processRestrictions(this.model);
                _.each(this.settings.attributes, function(group, groupName) {
                    if (!group.metadata.visible) { return; }
                    _.each(group, function(setting, settingName) {
                        var settingPath = groupName + '.' + settingName;
                        this.composeListeners(settingPath);
                        this.checkDependentRoles(settingPath);
                        this.calculateSettingDisabledState(settingPath);
                    }, this);
                }, this);
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
        render: function() {
            this.$el.html(this.template(this.options)).i18n();
            return this;
        }
    });

    return SettingsTab;
});
