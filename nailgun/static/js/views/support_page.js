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
        loaded: false,
        template: _.template(supportPageTemplate),
        events: {
            'click .download-logs': 'downloadLogs'
        },
        scheduleUpdate: function() {
            var task = this.logsPackageTasks.findTask({name: 'dump'});
            if (this.timeout) {
                this.timeout.clear();
            }
            if (_.isUndefined(task) || task.get('progress') < 100 ) {
                this.registerDeferred(this.timeout = $.timeout(this.updateInterval).done(_.bind(this.update, this)));
            } else {
                this.render();
            }
        },
        update: function() {
            this.registerDeferred(this.logsPackageTasks.fetch().always(_.bind(this.scheduleUpdate, this)));
        },
        downloadLogs: function() {
            var task = new models.LogsPackage();
            task.save({}, {method: 'PUT'});
            this.$('.download-logs, .donwload-logs-link, .download-logs-error').addClass('hide');
            this.$('.genereate-logs').removeClass('hide');
            this.logsPackageTasks.reset();
            this.logsPackageTasks.fetch();
            this.scheduleUpdate();
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.model = new models.FuelKey();
            this.model.fetch();
            this.model.on('change', this.render, this);
            this.logsPackageTasks = new models.Tasks();
            // Check for task was created earlier
            this.logsPackageTasks.once('sync', this.checkCompletedTask, this);
            this.logsPackageTasks.fetch();
        },
        checkCompletedTask: function() {
            var task = this.logsPackageTasks.findTask({name: 'dump'});
            if (!_.isUndefined(task) && task.get('progress') < 100) {
                this.scheduleUpdate();
            } else {
                this.loaded = true;
                this.render();
            }
        },
        renderRegistrationLink: function() {
            if (!_.isUndefined(this.model.get('key'))) {
                this.$('.registration-link').attr('href', 'http://fuel.mirantis.com/create-subscriber/?key=' + this.model.get('key'));
            }
        },
        render: function() {
            var task = this.logsPackageTasks.findTask({name: 'dump'});
            this.$el.html(this.template({task: task, loaded: this.loaded}));
            this.renderRegistrationLink();
            return this;
        }
    });

    return SupportPage;
});
