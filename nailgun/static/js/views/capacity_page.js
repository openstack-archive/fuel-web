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
    'text!templates/capacity/page.html'
],
function(commonViews, models, capacityPageTemplate) {
    'use strict';

    var CapacityPage = commonViews.Page.extend({
        navbarActiveElement: 'support',
        breadcrumbsPath: [['Home', '#'], ['Support', '#support'], 'Capacity'],
        title: 'Capacity',
        updateInterval: 2000,
        template: _.template(capacityPageTemplate),
        events: {
            'click .download-logs:not(.disabled)': 'downloadLogs'
        },
        scheduleUpdate: function() {
            if (this.timeout) {
                this.timeout.clear();
            }
            if (_.isUndefined(this.task.get('progress')) || this.task.get('progress') < 100 ) {
                this.registerDeferred(this.timeout = $.timeout(this.updateInterval).done(_.bind(this.update, this)));
            } else {
                this.model = new models.CapacityLog();
                this.model.deferred = this.model.fetch();
                this.model.on('sync', this.render, this);
            }
        },
        update: function() {
            this.registerDeferred(this.task.fetch({url: '/api/tasks/'+ this.task.id}).always(_.bind(this.scheduleUpdate, this)));
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.task = new models.Task();
            this.task.save({}, {url: '/api/capacity/', method: 'PUT'});
            this.scheduleUpdate();
        },
        render: function() {
            this.$el.html(this.template());
            return this;
        }
    });

    return CapacityPage;
});
