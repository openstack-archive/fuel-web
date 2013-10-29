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
    'views/common',
    'models',    
    'text!templates/support/page.html'
],
function(commonViews, models, supportPageTemplate) {
    'use strict';

    var SupportPage = commonViews.Page.extend({
        navbarActiveElement: 'support',
        breadcrumbsPath: [['Home', '#'], 'Support'],
        title: 'Support',
        updateInterval: 2000,
        template: _.template(supportPageTemplate),
        events: {
            'click .download-logs': 'downloadLogs'
        },
        scheduleUpdate: function() {
            var task = this.logsPackageTasks.findTask({name: 'dump'});
            if (this.timeout) {
                this.timeout.clear();
            }
            if (!task || task.get('progress') < 100) {
                this.registerDeferred(this.timeout = $.timeout(this.updateInterval).done(_.bind(this.update, this)));
            } else {
                this.render();
            }
        },
        update: function() {
            var task = this.logsPackageTasks.findTask({name: 'dump'});
            if (task) {
                this.registerDeferred(task.fetch().always(_.bind(this.scheduleUpdate, this)));
            }
        },
        downloadLogs: function() {
            var task = new models.LogsPackage();
            this.logsPackageTasks.reset()
            task.save({}, {method: 'PUT'}).always(
                _.bind(function() {
                    this.logsPackageTasks.fetch().done(_.bind(this.scheduleUpdate, this));
                }, this));
            this.$('.download-logs, .donwload-logs-link, .download-logs-error').addClass('hide');
            this.$('.genereate-logs').removeClass('hide');
            this.render();
            this.scheduleUpdate();
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.fuelKey = new models.FuelKey();
            this.fuelKey.fetch();
            this.fuelKey.on('change', this.render, this);
            this.logsPackageTasks = new models.Tasks();
            // Check for task was created earlier
            this.logsPackageTasks.once('sync', this.checkCompletedTask, this);
            this.logsPackageTasks.deferred = this.logsPackageTasks.fetch();
        },
        checkCompletedTask: function() {
            this.logsPackageTasks.deferred = null;
            var task = this.logsPackageTasks.findTask({name: 'dump'});
            if (task && task.get('progress') < 100) {
                this.scheduleUpdate();
            } else {
                this.render();
            }
        },
        render: function() {
            this.$el.html(this.template({tasks: this.logsPackageTasks, fuelKey: this.fuelKey}));
            return this;
        }
    });

    return SupportPage;
});
