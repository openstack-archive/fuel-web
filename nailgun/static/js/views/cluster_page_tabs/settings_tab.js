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
            return !_.isEqual(this.settings.toJSON().editable, this.settings.initialAttributes);
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
                .done(_.bind(function() {
                    this.settings.initialAttributes = _.cloneDeep(this.settings.toJSON().editable);
                }, this))
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
            this.settings.set(this.model.get('settingDefaults').attributes);
            this.settings.processRestrictions(this.configModels);
        },
        loadInitialSettings: function() {
            this.settings.set(this.settings.initialAttributes);
            this.settings.processRestrictions(this.configModels);
        },
        onSettingChange: function() {
            this.$('input.error').removeClass('error');
            this.$('.parameter-description').removeClass('hide');
            this.$('.validation-error').addClass('hide');
            this.settings.isValid();
            this.calculateButtonsState();
        },
        composeBindings: function() {
            var bindings = {};
            _.each(this.settings.attributes, function(group, groupName) {
                if (group.metadata.toggleable) {
                    bindings['input[name="' + groupName + '.enabled' + '"]'] = {
                        observe: groupName + '.metadata.enabled',
                        attributes: [{
                            name: 'disabled',
                            observe: groupName + '.metadata.disabled',
                            onGet: _.bind(function(value) {
                                return value || this.isLocked();
                            }, this)
                        }]
                    };
                }
                bindings['div[data-settings-group="' + groupName + '"]'] = {
                    observe: groupName + '.metadata.visible',
                    visible: true,
                    visibleFn: function($el, isVisible) {
                        $el.parents('.fieldset-group').toggle(isVisible);
                    }
                };
                _.each(group, function(setting, settingName) {
                    if (settingName == 'metadata') {return;}
                    var settingPath = groupName + '.' + settingName;
                    bindings['input[name="' + settingPath + '"]'] = {
                        observe: settingPath + '.value',
                        visible: function() {
                            return setting.visible;
                        },
                        visibleFn: function($el, isVisible) {
                            $el.parents('.parameter-box:first').toggleClass('hide', !isVisible);
                        },
                        attributes: [{
                            name: 'disabled',
                            observe: [groupName + '.metadata.enabled', groupName + '.metadata.disabled', settingPath + '.disabled'],
                            onGet: _.bind(function(value) {
                                var isSettingGroupActive = value[0];
                                var isSettingGroupDisabled = value[1];
                                var isSettingDisabled = value[2];
                                return this.isLocked() || isSettingGroupActive === false || isSettingGroupDisabled || isSettingDisabled;
                            }, this)
                        }]
                    };
                    _.each(setting.values, function(option, index) {
                        bindings['input[name="' + settingPath + '"][value="' + option.data + '"]'] = {
                            observe: settingPath + '.visible',
                            visible: function() {
                                return setting.visible && option.visible;
                            },
                            visibleFn: function($el, isVisible) {
                                $el.parents('.parameter-box:first').toggleClass('hide', !isVisible);
                            },
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
        getValueAttribute: function(settingName) {
            return settingName == 'metadata' ? 'enabled' : 'value';
        },
        checkChangedDependentSettings: function(groupName, settingName) {
            var settingPath = groupName + '.' + settingName;
            var hasDependentRestriction = _.bind(function(setting) {
                return _.any(_.where(setting.restrictions, {action: 'disable'}), function(restriction) {
                    return _.contains(restriction.condition, 'settings:' + settingPath + '.' + this.getValueAttribute(settingName));
                }, this);
            }, this);
            return _.any(this.settings.attributes, function(group, groupName) {
                if (!group.metadata.visible) { return false; }
                return _.any(group, function(setting, settingName) {
                    if (groupName + '.' + settingName == settingPath || (settingName == 'metadata' && _.isUndefined(setting.toggleable))) { return false; }
                    var valueAttribute = this.getValueAttribute(settingName);
                    var hasChangedDependentSetting = hasDependentRestriction(setting) && setting[valueAttribute] != this.model.get('settingDefaults').get(groupName + '.' + settingName + '.' + valueAttribute);
                    var hasActiveDependentOption = _.any(setting.values, function(value) {
                        return setting.value == value.data && hasDependentRestriction(value);
                    });
                    return hasChangedDependentSetting || hasActiveDependentOption;
                }, this);
            }, this);
        },
        calculateSettingState: function(groupName, settingName) {
            var settingPath = groupName + '.' + settingName;
            var setting = this.settings.get(settingPath);
            var checkRestrictions = _.bind(function(setting, action) {
                return _.any(_.where(setting.restrictions, {action: action}), function(restriction) {
                    return utils.evaluateExpression(restriction.condition, this.configModels).value;
                }, this);
            }, this);
            this.settings.set(settingPath + '.disabled', setting.hasDependentRole || checkRestrictions(setting, 'disable') || this.checkChangedDependentSettings(groupName, settingName));
            this.settings.set(settingPath + '.visible', !checkRestrictions(setting, 'hide'));
            _.each(setting.values, function(value, index) {
                var values = _.cloneDeep(setting.values);
                values[index].disabled = checkRestrictions(values[index], 'disable');
                values[index].visible = !checkRestrictions(values[index], 'hide');
                this.settings.set(settingPath + '.values', values);
            }, this);
        },
        composeListeners: function(groupName, settingName) {
            var settingPath = groupName + '.' + settingName;
            var valueAttribute = this.getValueAttribute(settingName);
            var callback = _.bind(this.calculateSettingState, this, groupName, settingName);
            var collectRestrictions = function(setting) {
                return _.compact(_.flatten(_.union(setting.restrictions, _.pluck(setting.values, 'restrictions'))));
            };
            _.each(collectRestrictions(this.settings.get(settingPath)), function(restriction) {
                var evaluatedRestriction = utils.evaluateExpression(restriction.condition, this.configModels);
                _.invoke(evaluatedRestriction.modelPaths, 'change', callback);
            }, this);
            // handle dependent settings
            _.each(this.settings.attributes, function(group, groupName) {
                _.each(group, function(setting, settingName) {
                    if (groupName + '.' + settingName == settingPath) { return; }
                    var hasDependentRestriction = _.any(collectRestrictions(setting), function(restriction) {
                        return _.contains(restriction.condition, 'settings:' + settingPath + '.' + valueAttribute);
                    });
                    if (hasDependentRestriction) {
                        this.settings.on('change:' + groupName + '.' + settingName + '.' + this.getValueAttribute(settingName), callback);
                    }
                }, this);
            }, this);
        },
        checkDependentRoles: function(groupName, settingName) {
            var settingPath = groupName + '.' + settingName;
            var rolesData = this.model.get('release').get('roles_metadata');
            this.settings.get(settingPath).hasDependentRole = _.any(this.model.get('release').get('roles'), function(role) {
                var roleDependencies = _.map(rolesData[role].depends, utils.expandRestriction);
                var hasSatisfiedDependencies = _.any(roleDependencies, function(dependency) {
                    var evaluatedDependency = utils.evaluateExpression(dependency.condition, this.configModels);
                    return _.contains(dependency.condition, 'settings:' + settingPath) && evaluatedDependency.value;
                }, this);
                var assignedNodes = this.model.get('nodes').filter(function(node) { return node.hasRole(role); });
                return hasSatisfiedDependencies && assignedNodes.length;
            }, this);
        },
        renderSettingGroup: function(groupName) {
            var settings = this.settings.get(groupName);
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
            this.settings = this.model.get('settings');
            this.settings.on('invalid', function(model, errors) {
                _.each(errors, function(error) {
                    var input = this.$('input[name="' + error.field + '"]');
                    input.addClass('error');
                    input.parent().siblings('.description').addClass('hide');
                    input.parent().siblings('.validation-error').text(error.message).removeClass('hide');
                }, this);
            }, this);
            if (!this.model.has('settingDefaults')) {
                var settingDefaults = new models.Settings();
                settingDefaults.url = _.result(this.model, 'url') + '/attributes/defaults';
                this.model.set('settingDefaults', settingDefaults);
            }
            (this.loading = $.when(
                this.settings.fetch({cache: true}),
                this.model.get('settingDefaults').fetch({cache: true}),
                this.model.get('networkConfiguration').fetch({cache: true}))
            ).done(_.bind(function() {
                this.settings.initialAttributes = _.cloneDeep(this.settings.attributes);
                this.configModels = {
                    cluster: this.model,
                    settings: this.settings,
                    networking_parameters: this.model.get('networkConfiguration').get('networking_parameters'),
                    version: app.version,
                    default: this.settings
                };
                this.settings.processRestrictions(this.configModels);
                _.each(this.settings.attributes, function(group, groupName) {
                    _.each(group, function(setting, settingName) {
                        this.composeListeners(groupName, settingName);
                        this.checkDependentRoles(groupName, settingName);
                        this.calculateSettingState(groupName, settingName);
                    }, this);
                }, this);
                this.settings.on('change', this.onSettingChange, this);
                this.settings.on('sync', function(settings) {
                    settings.processRestrictions(this.configModels);
                }, this);
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
