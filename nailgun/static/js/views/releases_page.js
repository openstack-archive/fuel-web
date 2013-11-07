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
    'views/common',
    'views/dialogs',
    'text!templates/release/list.html',
    'text!templates/release/release.html'
],
function(utils, commonViews, dialogViews, releasesListTemplate, releaseTemplate) {
    'use strict';

    var ReleasesPage, Release;

    ReleasesPage = commonViews.Page.extend({
        navbarActiveElement: 'releases',
        breadcrumbsPath: [['home', '#'], 'releases'],
        title: $.t('release_page.title'),
        updateInterval: 5000,
        template: _.template(releasesListTemplate),
        scheduleUpdate: function() {
            if (this.tasks.filterTasks({name: 'redhat_setup', status: 'running'}).length) {
                if (this.timeout) {
                    this.timeout.clear();
                }
                this.registerDeferred(this.timeout = $.timeout(this.updateInterval).done(_.bind(this.update, this)));
            }
        },
        update: function() {
            this.registerDeferred(this.tasks.fetch().always(_.bind(this.scheduleUpdate, this)));
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.scheduleUpdate();
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            this.$el.html(this.template({releases: this.collection}));
            this.collection.each(function(release) {
                var releaseView = new Release({release: release, page: this});
                this.registerSubView(releaseView);
                this.$('.releases-table tbody').append(releaseView.render().el);
            }, this);
            this.$el.i18n();
            return this;
        }
    });

    Release = Backbone.View.extend({
        tagName: 'tr',
        template: _.template(releaseTemplate),
        'events': {
            'click .btn-rhel-setup': 'showRhelLicenseCredentials'
        },
        showRhelLicenseCredentials: function() {
            var dialog = new dialogViews.RhelCredentialsDialog({release: this.release});
            this.registerSubView(dialog);
            dialog.render();
        },
        checkForSetupCompletion: function() {
            var setupTask = this.page.tasks.findTask({name: 'redhat_setup', status: ['ready', 'error'], release: this.release.id});
            if (setupTask) {
                if (setupTask.get('status') == 'ready') {
                    setupTask.destroy();
                } else {
                    this.updateErrorMessage();
                }
                this.release.fetch();
                app.navbar.refresh();
            }
        },
        updateProgress: function() {
            var task = this.page.tasks.findTask({name: 'redhat_setup', status: 'running', release: this.release.id});
            if (task) {
                this.$('.bar').css('width', task.get('progress') + '%');
                this.$('.bar-title-progress').text(task.get('progress') + '%');
            }
        },
        updateErrorMessage: function() {
            var setupTask = this.page.tasks.findTask({name: 'redhat_setup', status: 'error', release: this.release.id});
            if (setupTask) {
                this.$('div.error').html(utils.urlify(setupTask.get('message')));
            }
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.page.tasks.each(this.bindTaskEvents, this);
            this.page.tasks.on('add', this.onNewTask, this);
            this.release.on('change', this.render, this);
        },
        bindTaskEvents: function(task) {
            if (task.get('name') == 'redhat_setup' && task.releaseId() == this.release.id) {
                if (task.get('status') == 'running') {
                    task.on('change:status', this.checkForSetupCompletion, this);
                    task.on('change:progress', this.updateProgress, this);
                }
                return task;
            }
            return null;
        },
        onNewTask: function(task) {
            if (this.bindTaskEvents(task)) {
                this.checkForSetupCompletion();
                this.updateProgress();
            }
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            this.$el.html(this.template({release: this.release})).i18n();
            this.updateProgress();
            this.updateErrorMessage();
            return this;
        }
    });

    return ReleasesPage;
});
