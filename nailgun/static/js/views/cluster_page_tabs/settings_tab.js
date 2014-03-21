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
            return !_.isEqual(this.settings.attributes, this.initialSettings);
        },
        events: {
            'click .btn-apply-changes:not([disabled])': 'applyChanges',
            'click .btn-revert-changes:not([disabled])': 'revertChanges',
            'click .btn-load-defaults:not([disabled])': 'loadDefaults'
        },
        defaultButtonsState: function(buttonState) {
            this.$('.btn:not(.btn-load-defaults)').attr('disabled', buttonState);
            this.$('.btn-load-defaults').attr('disabled', false);
        },
        disableControls: function() {
            this.$('.btn, input, select').attr('disabled', true);
        },
        isLocked: function() {
            return this.model.task({group: 'deployment', status: 'running'}) || !this.model.isAvailableForSettingsChanges();
        },
        checkForChanges: function() {
            this.defaultButtonsState(!this.hasChanges());
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
                    utils.showErrorDialog({title: 'OpenStack Settings'});
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
                this.checkForChanges();
            }, this));
        },
        updateInitialSettings: function() {
            this.initialSettings = _.cloneDeep(this.settings.attributes);
        },
        loadInitialSettings: function() {
            this.settings.set(this.initialSettings);
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
                }, this);
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
                if (this.model.get('net_provider') == 'nova_network') {
                    this.$('input[name=murano]').attr('disabled', true);
                }
                this.composeBindings();
                this.stickit(this.settings);
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
            (this.loading = this.settings.fetch({cache: true})).done(_.bind(this.updateInitialSettings, this));
            if (this.loading.state() == 'pending') {
                this.loading.done(_.bind(this.render, this));
            }
            // some hacks until settings dependecies are implemented
            this.settings.on('change:storage.objects_ceph.value', _.bind(function(model, value) {if (value) {this.settings.set({'storage.images_ceph.value': value});}}, this));
            this.settings.on('change:storage.images_ceph.value', _.bind(function(model, value) {if (!value) {this.settings.set({'storage.objects_ceph.value': value});}}, this));
            this.settings.on('change:storage.volumes_lvm.value', _.bind(function(model, value) {if (value) {this.settings.set({'storage.volumes_ceph.value': !value});}}, this));
            this.settings.on('change:storage.volumes_ceph.value', _.bind(function(model, value) {if (value) {this.settings.set({'storage.volumes_lvm.value': !value});}}, this));
            this.settings.on('change', this.checkForChanges, this);
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
