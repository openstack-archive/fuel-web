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
    'models',
    'utils',
    'views/common',
    'views/dialogs',
    'views/wizard',
    'text!templates/clusters/page.html',
    'text!templates/clusters/cluster.html',
    'text!templates/clusters/new.html',
    'text!templates/clusters/register_trial.html'
],
function(models, utils, commonViews, dialogViews, wizard, clustersPageTemplate, clusterTemplate, newClusterTemplate, registerTrialTemplate) {
    'use strict';
    var ClustersPage, ClusterList, Cluster, RegisterTrial;

    ClustersPage = commonViews.Page.extend({
        navbarActiveElement: 'clusters',
        breadcrumbsPath: [['home', '#'], 'environments'],
        title: function() {
            return $.t('clusters_page.title');
        },
        template: _.template(clustersPageTemplate),
        render: function() {
            this.$el.html(this.template({clusters: this.collection})).i18n();
            var clustersView = new ClusterList({collection: this.collection});
            this.registerSubView(clustersView);
            this.$('.cluster-list').html(clustersView.render().el);
            if (_.contains(app.version.get('feature_groups'), 'mirantis') && !localStorage.trialRemoved) {
                var registerTrialView = new RegisterTrial();
                this.registerSubView(registerTrialView);
                this.$('.page-title').before(registerTrialView.render().el);
            }
            app.footer.$el.toggle(app.user.get('authenticated'));
            app.breadcrumbs.$el.toggle(app.user.get('authenticated'));
            app.navbar.$el.toggle(app.user.get('authenticated'));
            return this;
        }
    });

    ClusterList = Backbone.View.extend({
        className: 'roles-block-row',
        newClusterTemplate: _.template(newClusterTemplate),
        events: {
            'click .create-cluster': 'createCluster'
        },
        createCluster: function() {
            app.page.registerSubView(new wizard.CreateClusterWizard({collection: this.collection})).render();
        },
        initialize: function() {
            this.collection.on('sync add', this.render, this);
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            this.$el.html('');
            this.collection.each(_.bind(function(cluster) {
                var clusterView = new Cluster({model: cluster});
                this.registerSubView(clusterView);
                this.$el.append(clusterView.render().el);
            }, this));
            this.$el.append(this.newClusterTemplate());
            return this;
        }
    });

    Cluster = Backbone.View.extend({
        tagName: 'a',
        className: 'span3 clusterbox',
        template: _.template(clusterTemplate),
        templateHelpers: _.pick(utils, 'showDiskSize', 'showMemorySize'),
        updateInterval: 3000,
        scheduleUpdate: function() {
            if (this.model.task('cluster_deletion', ['running', 'ready']) || this.model.tasks({group: 'deployment', status: 'running'}).length) {
                this.registerDeferred($.timeout(this.updateInterval).done(_.bind(this.update, this)));
            }
        },
        update: function() {
            var deletionTask = this.model.task('cluster_deletion');
            var deploymentTask = this.model.task({group: 'deployment', status: 'running'});
            var request;
            if (deletionTask) {
                request = deletionTask.fetch();
                request.done(_.bind(this.scheduleUpdate, this));
                request.fail(_.bind(function(response) {
                    if (response.status == 404) {
                        this.model.collection.remove(this.model);
                        this.remove();
                        app.navbar.refresh();
                    }
                }, this));
                this.registerDeferred(request);
            } else if (deploymentTask) {
                request = deploymentTask.fetch();
                request.done(_.bind(function() {
                    if (deploymentTask.get('status') == 'running') {
                        this.updateProgress();
                        this.scheduleUpdate();
                    } else {
                        this.model.fetch();
                        app.navbar.refresh();
                    }
                }, this));
                this.registerDeferred(request);
            }
        },
        updateProgress: function() {
            var task = this.model.task({group: 'deployment', status: 'running'});
            if (task) {
                var progress = task.get('progress') || 0;
                this.$('.bar').css('width', (progress > 3 ? progress : 3) + '%');
            }
        },
        initialize: function() {
            this.model.on('change', this.render, this);
        },
        render: function() {
            this.$el.html(this.template(_.extend({
                cluster: this.model,
                deploymentTask: this.model.task({group: 'deployment', status: 'running'})
            }, this.templateHelpers))).i18n();
            this.updateProgress();
            if (this.model.task('cluster_deletion', ['running', 'ready'])) {
                this.$el.addClass('disabled-cluster');
                this.update();
            } else {
                this.$el.attr('href', '#cluster/' + this.model.id + '/nodes');
                if (this.model.task({group: 'deployment', status: 'running'})) {
                    this.update();
                }
            }
            return this;
        }
    });

    RegisterTrial = Backbone.View.extend({
        template: _.template(registerTrialTemplate),
        events: {
            'click .register-trial .close': 'closeTrialWarning'
        },
        bindings: {
            '.registration-link': {
                attributes: [{
                    name: 'href',
                    observe: 'key',
                    onGet: function(value) {
                        return !_.isUndefined(value) ? 'http://fuel.mirantis.com/create-subscriber/?key=' + value : '/';
                    }
                }]
            }
        },
        initialize: function() {
            this.fuelKey = new models.FuelKey();
            this.fuelKey.fetch();
            app.version.on('sync', this.render, this);
        },
        closeTrialWarning: function() {
            localStorage.setItem('trialRemoved', 'true');
            this.remove();
        },
        render: function() {
            this.$el.html(this.template()).i18n();
            this.stickit(this.fuelKey);
            return this;
        }
    });
    return ClustersPage;
});
