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
            this.settings.initialAttributes = this.settings.toJSON().editable;
        },
        loadInitialSettings: function() {
            this.settings.set(_.cloneDeep(this.settings.initialAttributes));
            this.updateSettings();
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
                var isGroupDisabled = _.bind(function(groupName) {
                    var groupData = this.settings.get(groupName + '.metadata');
                    if (groupData.enabled && (groupData.hasDependentRole || this.checkDependentSettings(groupName, 'metadata'))) {
                       return false;
                    }
                    return groupData.enabled === false || groupData.disabled;
                }, this);
                _.each(group, function(setting, settingName) {
                    if (settingName == 'metadata') {return;}
                    var settingPath = groupName + '.' + settingName;
                    bindings['[name="' + settingPath + '"]'] = {
                        observe: [settingPath + '.value', settingPath + '.visible'],
                        onGet: function(value) {
                            return value[0];
                        },
                        onSet: function(value) {
                            return [value, setting.visible];
                        },
                        visible: function() {
                            return setting.visible;
                        },
                        visibleFn: function($el, isVisible) {
                            $el.parents('.setting-container').toggleClass('hide', !isVisible);
                        },
                        attributes: [{
                            name: 'disabled',
                            observe: [groupName + '.metadata.*', settingPath + '.disabled'],
                            onGet: _.bind(function(value) {
                                var isSettingDisabled = value[1];
                                return this.isLocked() || isGroupDisabled(groupName) || isSettingDisabled;
                            }, this)
                        }]
                    };
                    _.each(setting.values, function(option, index) {
                        bindings['input[name="' + settingPath + '"][value="' + option.data + '"]'] = {
                            observe: [settingPath + '.visible', settingPath + '.values'],
                            onGet: function(value) {
                                return value[1];
                            },
                            visible: function(value) {
                                return setting.visible && value[index].visible;
                            },
                            visibleFn: function($el, isVisible) {
                                $el.parents('.parameter-box:first').toggleClass('hide', !isVisible);
                            },
                            attributes: [{
                                name: 'disabled',
                                observe: [groupName + '.metadata.*', settingPath + '.disabled', settingPath + '.values'],
                                onGet: _.bind(function(value) {
                                    var isSettingDisabled = value[1];
                                    var values = value[2];
                                    return this.isLocked() || isGroupDisabled(groupName) || isSettingDisabled || values[index].disabled;
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
        checkDependentSettings: function(groupName, settingName) {
            var unsupportedTypes = ['text', 'password'];
            var settingPath = groupName + '.' + settingName;
            var processedSetting = this.settings.get(settingPath);
            var valueAttribute = this.getValueAttribute(settingName);
            var notToggleableGroup = settingName == 'metadata' && !processedSetting.toggleable;
            if (notToggleableGroup || _.contains(unsupportedTypes, this.settings.get(settingPath).type)) {
                return false;
            }
            var isDependent = function(restriction) {
                return restriction.action == 'disable' && _.contains(restriction.condition, 'settings:' + settingPath);
            };
            // collect restrictions to check
            var restrictions = [];
            _.each(this.settings.attributes, function(group, groupName) {
                // FIXME(ja): invisible dependent settings and options should not be checked also
                if (this.checkRestrictions(group.metadata, 'hide')) { return; }
                _.each(group, function(setting, settingName) {
                    if (_.contains(unsupportedTypes, setting.type) || groupName + '.' + settingName == settingPath) { return; }
                    if (setting[this.getValueAttribute(settingName)] == true) { // for checkboxes and toggleable setting groups
                        restrictions.push(_.find(setting.restrictions, isDependent));
                    } else {
                        var activeOption = _.find(setting.values, {data: setting.value}); // for dropdowns and radio groups
                        if (activeOption) {
                            restrictions.push(_.find(activeOption.restrictions, isDependent));
                        }
                    }
                }, this);
            }, this);
            restrictions = _.compact(restrictions);
            if (restrictions.length) {
                var processedValues = _.without(_.pluck(processedSetting.values, 'data'), processedSetting[valueAttribute]) || [!processedSetting[valueAttribute]];
                var configModels = _.extend({}, this.configModels, {settings: new models.Settings(this.settings.toJSON().editable)});
                return _.any(restrictions, function(restriction) {
                    var suitableValues = _.filter(processedValues, function(value) {
                        configModels.settings.get(settingPath)[valueAttribute] = value;
                        return !utils.evaluateExpression(restriction.condition, configModels).value;
                    });
                    return !suitableValues.length;
                });
            }
            return false;
        },
        checkRestrictions: function(setting, action) {
            return _.any(_.where(setting.restrictions, {action: action}), function(restriction) {
                return utils.evaluateExpression(restriction.condition, this.configModels).value;
            }, this);
        },
        calculateSettingState: function(groupName, settingName) {
            var settingPath = groupName + '.' + settingName;
            var setting = this.settings.get(settingPath);
            this.settings.set(settingPath + '.disabled', setting.hasDependentRole || this.checkRestrictions(setting, 'disable') || this.checkDependentSettings(groupName, settingName));
            this.settings.set(settingPath + '.visible', !this.checkRestrictions(setting, 'hide'));
            _.each(setting.values, function(value, index) {
                var values = _.cloneDeep(setting.values);
                values[index].disabled = this.checkRestrictions(values[index], 'disable');
                values[index].visible = !this.checkRestrictions(values[index], 'hide');
                this.settings.set(settingPath + '.values', values);
            }, this);
        },
        composeListeners: function(groupName, settingName) {
            var settingPath = groupName + '.' + settingName;
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
                    var isDependent = function(restriction) {
                        return _.contains(restriction.condition, 'settings:' + settingPath);
                    };
                    if (_.any(collectRestrictions(setting), isDependent)) {
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
        updateSettings: function() {
            this.settings.expandRestrictions();
             _.each(this.settings.attributes, function(group, groupName) {
                _.each(group, function(setting, settingName) {
                    this.calculateSettingState(groupName, settingName);
                }, this);
            }, this);
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
            (this.loading = $.when(this.settings.fetch({cache: true}), this.model.get('networkConfiguration').fetch({cache: true}))).done(_.bind(function() {
                this.updateInitialSettings();
                this.configModels = {
                    cluster: this.model,
                    settings: this.settings,
                    networking_parameters: this.model.get('networkConfiguration').get('networking_parameters'),
                    version: app.version,
                    default: this.settings
                };
                this.settings.expandRestrictions();
                _.each(this.settings.attributes, function(group, groupName) {
                    _.each(group, function(setting, settingName) {
                        this.composeListeners(groupName, settingName);
                        this.checkDependentRoles(groupName, settingName);
                        this.calculateSettingState(groupName, settingName);
                    }, this);
                }, this);
                this.settings.on('change', this.onSettingChange, this);
                this.settings.on('sync', this.updateSettings, this);
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
