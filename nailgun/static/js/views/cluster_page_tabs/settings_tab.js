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
        defaultButtonsState: function(buttonState) {
            this.$('.btn:not(.btn-load-defaults)').attr('disabled', buttonState);
            this.$('.btn-load-defaults').attr('disabled', false);
        },
        disableControls: function() {
            this.$('.btn, input, select').attr('disabled', true);
        },
        isLocked: function() {
            return this.model.get('status') != 'new' || !!this.model.task('deploy', 'running');
        },
        checkForChanges: function() {
            this.defaultButtonsState(!this.hasChanges());
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
            var defaults = new models.Settings();
            this.disableControls();
            defaults.fetch({url: _.result(this.model, 'url') + '/attributes/defaults'}).always(_.bind(function() {
                this.settings = new models.Settings(defaults.get('editable'));
                this.render();
                this.checkForChanges();
            }, this));
        },
        setInitialData: function() {
            this.previousSettings = _.cloneDeep(this.model.get('settings').get('editable'));
            this.settings = new models.Settings(this.previousSettings);
            // some hacks until settings dependecies are implemented
            this.settings.on('change:additional_components.murano.value', _.bind(function(model, value) {this.settings.set({'additional_components.heat.value': value});}, this));
            this.settings.on('change:storage.objects_ceph.value', _.bind(function(model, value) {if (value) {this.settings.set({'storage.images_ceph.value': value});}}, this));
            this.settings.on('change:storage.images_ceph.value', _.bind(function(model, value) {if (!value) {this.settings.set({'storage.objects_ceph.value': value});}}, this));
            this.settings.on('change', _.bind(this.checkForChanges, this));
        },
        composeBindings: function() {
            this.bindings = {};
            _.each(this.settings.attributes, function(settingsGroup, attr) {
                _.each(settingsGroup, function(setting, settingTitle) {
                    this.bindings['input[name=' + settingTitle + ']'] = attr + '.' + settingTitle + '.value';
                }, this);
            }, this);
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            this.$el.html(this.template({cluster: this.model, locked: this.isLocked()}));
            if (this.model.get('settings').deferred.state() != 'pending') {
                this.$('.settings').html('');
                var settingGroups = _.keys(this.settings.attributes);
                var order = this.model.get('settings').preferredOrder;
                settingGroups.sort(function(a, b) {
                    return _.indexOf(order, a) - _.indexOf(order, b);
                });
                _.each(settingGroups, function(settingGroup) {
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
                this.stickit(this.settings);
            }
            this.$el.i18n();
            return this;
        },
        bindTaskEvents: function(task) {
            return task.get('name') == 'deploy' ? task.on('change:status', this.render, this) : null;
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
            this.$el.html(this.template(this.options));
            return this;
        }
    });

    return SettingsTab;
});
