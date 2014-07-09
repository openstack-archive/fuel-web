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
    'coccyx',
    'js/coccyx_mixins',
    'models',
    'keystone_client',
    'views/common',
    'views/login_page',
    'views/cluster_page',
    'views/cluster_page_tabs/nodes_tab',
    'views/clusters_page',
    'views/releases_page',
    'views/notifications_page',
    'views/support_page',
    'views/capacity_page'
],
function(Coccyx, coccyxMixins, models, KeystoneClient, commonViews, LoginPage, ClusterPage, NodesTab, ClustersPage, ReleasesPage, NotificationsPage, SupportPage, CapacityPage) {
    'use strict';

    var AppRouter = Backbone.Router.extend({
        routes: {
            'login': 'login',
            'logout': 'logout',
            'clusters': 'listClusters',
            'cluster/:id': 'showCluster',
            'cluster/:id/:tab(/:opt1)(/:opt2)': 'showClusterTab',
            'releases': 'listReleases',
            'notifications': 'showNotifications',
            'support': 'showSupportPage',
            'capacity': 'showCapacityPage',
            '*default': 'listClusters'
        },
        initialize: function() {
            window.app = this;

            // add deferred-related mixins
            _.extend(Backbone.View.prototype, coccyxMixins);

            // reject deferreds on view teardown
            Coccyx.addTearDownCallback(function() {
                this.rejectRegisteredDeferreds();
            });

            // remove stickit bindings on teardown
            Coccyx.addTearDownCallback(function() {
                this.unstickit();
            });

            // this is needed for IE, which caches requests resulting in wrong results (e.g /ostf/testruns/last/1)
            $.ajaxSetup({ cache: false });


            var keystoneClient = this.keystoneClient = new KeystoneClient('/keystone', {
                cacheTokenFor: 10 * 60 * 1000,
                tenant: 'admin'
            });
            var version = this.version = new models.FuelVersion();

            version.fetch().done(_.bind(function() {
                this.user = new models.User({authenticated: !version.get('auth_required')});

                var originalSync = Backbone.sync;
                Backbone.sync = function(method, model, options) {
                    // our server doesn't support PATCH, so use PUT instead
                    if (method == 'patch') {
                        method = 'update';
                    }
                    if (version.get('auth_required') && !this.authExempt) {
                        // add keystone token to headers
                        return keystoneClient.authenticate()
                            .fail(function() {
                                app.logout();
                            })
                            .then(_.bind(function() {
                                options = options || {};
                                options.headers = options.headers || {};
                                options.headers['X-Auth-Token'] = keystoneClient.token;
                                return originalSync.call(this, method, model, options);
                            }, this));
                    }
                    return originalSync.call(this, method, model, options);
                };

                this.renderLayout();

                if (version.get('auth_required')) {
                    _.extend(keystoneClient, this.user.pick('username', 'password'));
                    keystoneClient.authenticate()
                        .done(function() {
                            app.user.set({authenticated: true});
                        })
                        .always(function() {
                            Backbone.history.start();
                        })
                        .fail(function() {
                            app.navigate('#login', {trigger: true});
                        });
                } else {
                    Backbone.history.start();
                }
            }, this));
        },
        renderLayout: function() {
            this.content = $('#content');
            this.navbar = new commonViews.Navbar({elements: [
                {label: 'environments', url: '#clusters'},
                {label: 'releases', url:'#releases'},
                {label: 'support', url:'#support'}
            ]});
            this.content.before(this.navbar.render().el);
            this.breadcrumbs = new commonViews.Breadcrumbs();
            this.content.before(this.breadcrumbs.render().el);
            this.footer = new commonViews.Footer();
            $('#footer').html(this.footer.render().el);
            this.content.find('.loading').addClass('layout-loaded');
        },
        setPage: function(NewPage, options) {
            if (this.page) {
                this.page.tearDown();
            }
            this.page = new NewPage(options);
            this.page.updateNavbar();
            this.page.updateBreadcrumbs();
            this.page.updateTitle();
            this.content.html(this.page.render().el);

        },
        // routes
        login: function() {
            this.setPage(LoginPage);
        },
        logout: function() {
            if (this.version.get('auth_required') && this.user.get('authenticated')) {
                this.user.set('authenticated', false);
                this.user.unset('username');
                this.user.unset('password');
                delete app.keystoneClient.userId;
                delete app.keystoneClient.username;
                delete app.keystoneClient.password;
                delete app.keystoneClient.token;
                delete app.keystoneClient.tokenUpdateTime;
            }
            _.defer(function() {
                app.navigate('#login', {trigger: true, replace: true});
            });
        },
        showCluster: function(id) {
            this.navigate('#cluster/' + id + '/nodes', {trigger: true, replace: true});
        },
        showClusterTab: function(id, activeTab) {
            if (!_.contains(ClusterPage.prototype.tabs, activeTab)) {
                this.showCluster(id);
                return;
            }

            var tabOptions = _.toArray(arguments).slice(2);

            if (activeTab == 'nodes') {
                // special case for nodes tab screen change
                try {
                    if (app.page.constructor == ClusterPage && app.page.model.id == id && app.page.tab.constructor == NodesTab) {
                        app.page.tab.routeScreen(tabOptions);
                        return;
                    }
                } catch (ignore) {}
            }

            var cluster, tasks;
            var render = function() {
                this.setPage(ClusterPage, {
                    model: cluster,
                    activeTab: activeTab,
                    tabOptions: tabOptions,
                    tasks: tasks
                });
            };

            if (app.page && app.page.constructor == ClusterPage && app.page.model.id == id) {
                // just another tab has been chosen, do not load cluster again
                cluster = app.page.model;
                tasks = app.page.tasks;
                render.call(this);
            } else {
                cluster = new models.Cluster({id: id});
                var settings = new models.Settings();
                settings.url = _.result(cluster, 'url') + '/attributes';
                cluster.set({settings: settings});
                tasks = new models.Tasks();
                tasks.fetch = function(options) {
                    return this.constructor.__super__.fetch.call(this, _.extend({data: {cluster_id: ''}}, options));
                };
                $.when(cluster.fetch(), cluster.get('settings').fetch(), cluster.fetchRelated('nodes'), cluster.fetchRelated('tasks'), tasks.fetch())
                    .then(_.bind(function(){
                        var networkConfiguration = new models.NetworkConfiguration();
                        networkConfiguration.url = _.result(cluster, 'url') + '/network_configuration/' + cluster.get('net_provider');
                        cluster.set({
                            networkConfiguration: networkConfiguration,
                            release: new models.Release({id: cluster.get('release_id')})
                        });
                        return cluster.get('release').fetch();
                    }, this))
                    .done(_.bind(render, this))
                    .fail(_.bind(this.listClusters, this));
            }
        },
        listClusters: function() {
            this.navigate('#clusters', {replace: true});
            var clusters = new models.Clusters();
            var nodes = new models.Nodes();
            var tasks = new models.Tasks();
            $.when(clusters.fetch(), nodes.deferred = nodes.fetch(), tasks.fetch()).always(_.bind(function() {
                clusters.each(function(cluster) {
                    cluster.set('nodes', new models.Nodes(nodes.where({cluster: cluster.id})));
                    cluster.get('nodes').deferred = nodes.deferred;
                    cluster.set('tasks', new models.Tasks(tasks.where({cluster: cluster.id})));
                }, this);
                this.setPage(ClustersPage, {collection: clusters});
            }, this));
        },
        listReleases: function() {
            var releases = new models.Releases();
            var tasks = new models.Tasks();
            tasks.fetch = function(options) {
                return this.constructor.__super__.fetch.call(this, _.extend({data: {cluster_id: ''}}, options));
            };
            $.when(releases.fetch(), tasks.fetch()).done(_.bind(function() {
                this.setPage(ReleasesPage, {
                    collection: releases,
                    tasks: tasks
                });
            }, this));
        },
        showNotifications: function() {
            this.setPage(NotificationsPage, {notifications: app.navbar.notifications});
        },
        showSupportPage: function() {
            this.setPage(SupportPage);
        },
        showCapacityPage: function() {
            this.setPage(CapacityPage);
        }
    });

    return {
        initialize: function() {
            return new AppRouter();
        }
    };
});
