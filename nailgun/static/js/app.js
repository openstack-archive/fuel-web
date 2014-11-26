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
    'react',
    'utils',
    'jsx!views/layout',
    'coccyx',
    'js/coccyx_mixins',
    'models',
    'keystone_client',
    'views/common',
    'jsx!views/login_page',
    'jsx!views/welcome_page',
    'views/cluster_page',
    'views/cluster_page_tabs/nodes_tab',
    'jsx!views/clusters_page',
    'jsx!views/releases_page',
    'jsx!views/notifications_page',
    'jsx!views/support_page',
    'jsx!views/capacity_page'
],
function(React, utils, layoutComponents, Coccyx, coccyxMixins, models, KeystoneClient, commonViews, LoginPage, WelcomePage, ClusterPage, NodesTab, ClustersPage, ReleasesPage, NotificationsPage, SupportPage, CapacityPage) {
    'use strict';

    var AppRouter = Backbone.Router.extend({
        routes: {
            login: 'login',
            logout: 'logout',
            welcome: 'welcome',
            clusters: 'listClusters',
            'cluster/:id': 'showCluster',
            'cluster/:id/:tab(/:opt1)(/:opt2)': 'showClusterTab',
            releases: 'listReleases',
            notifications: 'showNotifications',
            support: 'showSupportPage',
            capacity: 'showCapacityPage',
            '*default': 'listClusters'
        },
        initialize: function() {
            window.app = this;

            if (navigator.userAgent.indexOf('Safari') != -1 && navigator.userAgent.indexOf('Chrome') == -1) {
                $('body').addClass('safari');
            }

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
            $.ajaxSetup({cache: false});

            var keystoneClient = this.keystoneClient = new KeystoneClient('/keystone', {
                cacheTokenFor: 10 * 60 * 1000,
                tenant: 'admin'
            });

            this.version = new models.FuelVersion();
            this.settings = new models.FuelSettings();
            this.user = new models.User();

            this.version.fetch().then(_.bind(function() {
                this.user.set({authenticated: !this.version.get('auth_required')});

                var originalSync = Backbone.sync;
                Backbone.sync = function(method, model, options) {
                    // our server doesn't support PATCH, so use PUT instead
                    if (method == 'patch') {
                        method = 'update';
                    }
                    if (app.version.get('auth_required') && !this.authExempt) {
                        // FIXME(vkramskikh): manually moving success/error callbacks
                        // to deferred-style callbacks. Everywhere in the code we use
                        // deferreds, but backbone uses success/error callbacks. It
                        // seems there is a bug somewhere: sometimes in long deferred
                        // chains with .then() success/error callbacks are called when
                        // deferred object is not resolved, so 'sync' event is
                        // triggered but dfd.state() still returns 'pending'. This
                        // leads to various bugs here and there.
                        var callbacks = {};

                        return keystoneClient.authenticate()
                            .fail(function() {
                                app.logout();
                            })
                            .then(_.bind(function() {
                                options = options || {};
                                options.headers = options.headers || {};
                                options.headers['X-Auth-Token'] = keystoneClient.token;
                                _.each(['success', 'error'], function(callback) {
                                    if (options[callback]) {
                                        callbacks[callback] = options[callback];
                                        delete options[callback];
                                    }
                                });
                                return originalSync.call(this, method, model, options);
                            }, this))
                            .done(function() {
                                if (callbacks.success) {
                                    callbacks.success.apply(callbacks.success, arguments);
                                }
                            })
                            .fail(function() {
                                if (callbacks.error) {
                                    callbacks.error.apply(callbacks.error, arguments);
                                }
                            })
                            .fail(function(response) {
                                if (response && response.status == 401) {
                                    app.logout();
                                }
                            });
                    }
                    return originalSync.call(this, method, model, options);
                };

                if (app.version.get('auth_required')) {
                    _.extend(keystoneClient, this.user.pick('token'));
                    return keystoneClient.authenticate()
                        .done(function() {
                            app.user.set({authenticated: true});
                        });
                }
                return $.Deferred().resolve();
            }, this)).then(_.bind(function() {
                return this.settings.fetch();
            }, this)).always(_.bind(function() {
                this.renderLayout();
                Backbone.history.start();
            }, this));
        },
        renderLayout: function() {
            this.content = $('#content');
            this.navbar = React.renderComponent(new layoutComponents.Navbar({
                elements: [
                    {label: 'environments', url: '#clusters'},
                    {label: 'releases', url: '#releases'},
                    {label: 'support', url: '#support'}
                ],
                user: this.user,
                version: this.version,
                statistics: new models.NodesStatistics(),
                notifications: new models.Notifications()
            }), $('#navbar')[0]);
            this.breadcrumbs = React.renderComponent(new layoutComponents.Breadcrumbs(), $('#breadcrumbs')[0]);
            this.footer = React.renderComponent(new layoutComponents.Footer({version: this.version}), $('#footer')[0]);
            this.content.find('.loading').addClass('layout-loaded');
        },
        updateTitle: function() {
            var newTitle = _.result(this.page, 'title');
            document.title = $.t('common.title') + (newTitle ? ' - ' + newTitle : '');
            this.breadcrumbs.update();
        },
        toggleElements: function(state) {
            app.footer.setState({hidden: !state});
            app.breadcrumbs.setState({hidden: !state});
            app.navbar.setState({hidden: !state});
        },
        setPage: function(NewPage, options) {
            if (this.page) {
                utils.universalUnmount(this.page);
            }
            this.page = utils.universalMount(new NewPage(options), this.content);
            this.navbar.setActive(_.result(this.page, 'navbarActiveElement'));
            this.updateTitle();
            this.toggleElements(!this.page.hiddenLayout);
        },
        // pre-route hook
        before: function(currentUrl) {
            var preventRouting = false;
            var specialRoutes = [
                {url: 'login', condition: function() {
                    return app.version.get('auth_required') && !app.user.get('authenticated');
                }},
                {url: 'welcome', condition: function() {
                    return !app.settings.get('statistics.user_choice_saved.value');
                }}
            ];
            _.each(specialRoutes, function(route) {
                if (route.condition()) {
                    if (currentUrl != route.url) {
                        preventRouting = true;
                        this.navigate(route.url, {trigger: true, replace: true});
                    }
                    return false;
                } else if (currentUrl == route.url) {
                    preventRouting = true;
                    this.navigate('', {trigger: true});
                    return false;
                }
            }, this);
            return !preventRouting;
        },
        // routes
        login: function() {
            this.setPage(LoginPage, {app: app});
        },
        logout: function() {
            if (this.user.get('authenticated') && this.version.get('auth_required')) {
                this.user.set('authenticated', false);
                this.user.unset('username');
                this.user.unset('token');

                this.keystoneClient.deauthenticate();
            }

            _.defer(function() {
                app.navigate('#login', {trigger: true, replace: true});
            });
        },
        welcome: function() {
            this.settings.fetch({cache: true}).done(_.bind(function() {
                this.setPage(WelcomePage, {settings: this.settings});
            }, this));
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
                    .then(_.bind(function() {
                        cluster.get('settings').processRestrictions();
                        var networkConfiguration = new models.NetworkConfiguration();
                        networkConfiguration.url = _.result(cluster, 'url') + '/network_configuration/' + cluster.get('net_provider');
                        cluster.set({
                            networkConfiguration: networkConfiguration,
                            release: new models.Release({id: cluster.get('release_id')})
                        });
                        return $.when(cluster.get('networkConfiguration').fetch(), cluster.get('release').fetch());
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
            $.when(clusters.fetch(), nodes.deferred = nodes.fetch(), tasks.fetch()).done(_.bind(function() {
                clusters.each(function(cluster) {
                    cluster.set('nodes', new models.Nodes(nodes.where({cluster: cluster.id})));
                    cluster.get('nodes').deferred = nodes.deferred;
                    cluster.set('tasks', new models.Tasks(tasks.where({cluster: cluster.id})));
                }, this);
                this.setPage(ClustersPage, {clusters: clusters});
            }, this));
        },
        listReleases: function() {
            var releases = new models.Releases();
            releases.fetch().done(_.bind(function() {
                this.setPage(ReleasesPage, {releases: releases});
            }, this));
        },
        showNotifications: function() {
            var notifications = app.navbar.props.notifications;
            notifications.fetch().done(_.bind(function() {
                this.setPage(NotificationsPage, {notifications: notifications});
            }, this));
        },
        showSupportPage: function() {
            var tasks = new models.Tasks();
            tasks.fetch().done(_.bind(function() {
                this.setPage(SupportPage, {tasks: tasks, settings: this.settings});
            }, this));
        },
        showCapacityPage: function() {
            var task = new models.Task();
            task.save({}, {url: '/api/capacity/', method: 'PUT'}).done(_.bind(function() {
                this.setPage(CapacityPage, {capacityLog: new models.CapacityLog()});
            }, this));
        }
    });

    return {
        initialize: function() {
            return new AppRouter();
        }
    };
});
