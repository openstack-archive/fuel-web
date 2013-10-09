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
        hasChanges: false,
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
            var equal = _.isEqual(this.settings, this.previousSettings);
            this.defaultButtonsState(equal);
            this.hasChanges = !equal;
        },
        applyChanges: function() {
            this.disableControls();
            return this.model.get('settings').save({editable: this.settings}, {patch: true, wait: true, url: _.result(this.model, 'url') + '/attributes'})
                .always(_.bind(function() {
                    this.render();
                    this.model.fetch();
                }, this))
                .done(_.bind(this.setInitialData, this))
                .fail(_.bind(function() {
                    this.defaultButtonsState(false);
                    utils.showErrorDialog({title: 'OpenStack Settings'});
                }, this));
        },
        revertChanges: function() {
            this.settings = _.cloneDeep(this.previousSettings);
            this.hasChanges = false;
            this.render();
        },
        loadDefaults: function() {
            var defaults = new models.Settings();
            this.disableControls();
            defaults.fetch({url: _.result(this.model, 'url') + '/attributes/defaults'}).always(_.bind(function() {
                this.settings = defaults.get('editable');
                this.render();
                this.checkForChanges();
            }, this));
        },
        setInitialData: function() {
            this.settings = _.cloneDeep(this.model.get('settings').get('editable'));
            this.previousSettings = _.cloneDeep(this.settings);
            this.hasChanges = false;
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            this.$el.html(this.template({cluster: this.model, locked: this.isLocked()}));
            if (this.model.get('settings').deferred.state() != 'pending') {
                this.$('.settings').html('');
                var settingGroups = _.keys(this.settings);
                var order = this.model.get('settings').preferredOrder;
                settingGroups.sort(function(a, b) {
                    return _.indexOf(order, a) - _.indexOf(order, b);
                });
                _.each(settingGroups, function(settingGroup) {
                    var settingGroupView = new SettingGroup({
                        legend: settingGroup,
                        settings: this.settings[settingGroup],
                        tab: this
                    });
                    this.registerSubView(settingGroupView);
                    this.$('.settings').append(settingGroupView.render().el);
                }, this);
            }
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
            'keyup input[type=text], input[type=password]': 'makeChanges',
            'change input[type=checkbox]:not(.show-password), input[type=radio]': 'makeChanges',
            'click span.add-on': 'showPassword'
        },
        makeChanges: function(e) {
            var target = $(e.currentTarget);
            var settingName = target.attr('name');
            var settingGroup = target.parents('.settings-group').data('settings-group');
            var setting = this.tab.settings[settingGroup][settingName];
            setting.value = setting.type == 'checkbox' ? target.is(':checked') : target.val();
            if (settingName == 'murano') {
                this.tab.settings[settingGroup].heat.value = setting.value;
            } else if (this.tab.model.get('mode') != 'multinode') {
                if (settingName == 'objects_ceph' && setting.value) {
                    this.tab.settings[settingGroup].images_ceph.value = setting.value;
                    this.render();
                } else if (settingName == 'images_ceph' && !setting.value) {
                    this.tab.settings[settingGroup].objects_ceph.value = setting.value;
                    this.render();
                }
            }
            this.tab.checkForChanges();
        },
        showPassword: function(e) {
            var input = this.$(e.currentTarget).prev();
            input.attr('type', input.attr('type') == 'text' ? 'password' : 'text');
            this.$(e.currentTarget).find('i').toggle();
        },
        initialize: function(options) {
            _.defaults(this, options);
        },
        render: function() {
            this.$el.html(this.template({
                settings: this.settings,
                legend: this.legend,
                locked: this.tab.isLocked()
            }));
            return this;
        }
    });

    return SettingsTab;
});
