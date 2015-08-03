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
    'jquery',
    'underscore',
    'i18n',
    'backbone',
    'react',
    'utils',
    'jsx!views/layout',
    'coccyx',
    'models',
    'keystone_client',
    'jsx!views/root',
    'jsx!views/login_page',
    'jsx!views/welcome_page',
    'jsx!views/cluster_page',
    'jsx!views/clusters_page',
    'jsx!views/releases_page',
    'jsx!views/plugins_page',
    'jsx!views/notifications_page',
    'jsx!views/support_page',
    'jsx!views/capacity_page',

    'react.backbone',
    'stickit',
    'routefilter',
    'bootstrap',
    'less!/static/styles/main'
],
function($, _, i18n, Backbone, React, utils, layoutComponents, Coccyx, models, KeystoneClient, RootComponent, LoginPage, WelcomePage, ClusterPage, ClustersPage, ReleasesPage, PluginsPage, NotificationsPage, SupportPage, CapacityPage) {
    'use strict';

    var Router = Backbone.Router.extend({
        routes: {
            login: 'login',
            logout: 'logout',
            welcome: 'welcome',
            clusters: 'listClusters',
            'cluster/:id(/:tab)(/:opt1)(/:opt2)': 'showCluster',
            releases: 'listReleases',
            plugins: 'listPlugins',
            notifications: 'showNotifications',
            support: 'showSupportPage',
            capacity: 'showCapacityPage',
            '*default': 'default'
        },
        initialize: function() {
            _.bindAll(this);
        },
        // pre-route hook
        before: function(currentRouteName) {
            var currentUrl = Backbone.history.getHash();
            var preventRouting = false;
            // remove trailing slash
            if (_.endsWith(currentUrl, '/')) {
                this.navigate(currentUrl.substr(0, currentUrl.length - 1), {trigger: true, replace: true});
                preventRouting = true;
            }
            // handle special routes
            if (!preventRouting) {
                var specialRoutes = [
                    {name: 'login', condition: function() {
                        var result = app.version.get('auth_required') && !app.user.get('authenticated');
                        if (result && currentUrl != 'login' && currentUrl != 'logout') app.router.returnUrl = currentUrl;
                        return result;
                    }},
                    {name: 'welcome', condition: function(previousUrl) {
                        return previousUrl != 'logout' && !app.settings.get('statistics.user_choice_saved.value');
                    }}
                ];
                _.each(specialRoutes, function(route) {
                    if (route.condition(currentRouteName)) {
                        if (currentRouteName != route.name) {
                            preventRouting = true;
                            this.navigate(route.name, {trigger: true, replace: true});
                        }
                        return false;
                    } else if (currentRouteName == route.name) {
                        preventRouting = true;
                        this.navigate('', {trigger: true});
                        return false;
                    }
                }, this);
            }
            return !preventRouting;
        },
        // routes
        default: function() {
            app.navigate('clusters', {trigger: true, replace: true});
        },
        login: function() {
            app.loadPage(LoginPage);
        },
        logout: function() {
            app.logout();
        },
        welcome: function() {
            app.loadPage(WelcomePage);
        },
        showCluster: function(clusterId, tab) {
            var tabs = _.pluck(ClusterPage.getTabs(), 'url');
            if (!tab || !_.contains(tabs, tab)) {
                app.navigate('cluster/' + clusterId + '/' + tabs[0], {trigger: true, replace: true});
            } else {
                app.loadPage(ClusterPage, arguments).fail(this.default);
            }
        },
        listClusters: function() {
            app.loadPage(ClustersPage);
        },
        listReleases: function() {
            app.loadPage(ReleasesPage);
        },
        listPlugins: function() {
            app.loadPage(PluginsPage);
        },
        showNotifications: function() {
            app.loadPage(NotificationsPage);
        },
        showSupportPage: function() {
            app.loadPage(SupportPage);
        },
        showCapacityPage: function() {
            app.loadPage(CapacityPage);
        }
    });

    function App() {
        // remove stickit bindings on teardown
        Coccyx.addTearDownCallback(function() {
            this.unstickit();
        });

        // this is needed for IE, which caches requests resulting in wrong results (e.g /ostf/testruns/last/1)
        $.ajaxSetup({cache: false});

        this.mountNode = $('#main-container');

        this.router = new Router();
        this.keystoneClient = new KeystoneClient('/keystone', {
            cacheTokenFor: 10 * 60 * 1000,
            tenant: 'admin'
        });
        this.version = new models.FuelVersion();
        this.settings = new models.FuelSettings();
        this.user = new models.User();
        this.statistics = new models.NodesStatistics();
        this.notifications = new models.Notifications();

        this.fetchData();
    }

    _.extend(App.prototype, {
        fetchData: function() {
            this.version.fetch().then(_.bind(function() {
                this.user.set({authenticated: !this.version.get('auth_required')});
                this.patchBackboneSync();
                if (this.version.get('auth_required')) {
                    _.extend(this.keystoneClient, this.user.pick('token'));
                    return this.keystoneClient.authenticate()
                        .done(_.bind(function() {
                            this.user.set({authenticated: true});
                        }, this));
                }
                return $.Deferred().resolve();
            }, this)).then(_.bind(function() {
                return this.settings.fetch();
            }, this)).then(null, _.bind(function() {
                if (this.version.get('auth_required') && !this.user.get('authenticated')) {
                    return $.Deferred().resolve();
                } else {
                    utils.showErrorDialog({
                        message: i18n('common.loading_error'),
                        keyboard: false,
                        backdrop: false
                    });
                    this.mountNode.remove();
                }
            }, this)).done(function() {
                Backbone.history.start();
            });
        },
        renderLayout: function() {
            var wrappedRootComponent = utils.universalMount(RootComponent, _.pick(this, 'version', 'user', 'statistics', 'notifications'), this.mountNode);
            // RootComponent is wrapped with React-DnD, extracting link to it using ref
            this.rootComponent = wrappedRootComponent.refs.child;
        },
        loadPage: function(Page, options) {
            return (Page.fetchData ? Page.fetchData.apply(Page, options) : $.Deferred().resolve()).done(_.bind(function(pageOptions) {
                if (!this.rootComponent) this.renderLayout();
                this.setPage(Page, pageOptions);
            }, this));
        },
        setPage: function(Page, options) {
            this.page = this.rootComponent.setPage(Page, options);
        },
        navigate: function() {
            this.router.navigate.apply(this.router, arguments);
        },
        logout: function() {
            if (this.user.get('authenticated') && this.version.get('auth_required')) {
                this.user.set('authenticated', false);
                this.user.unset('username');
                this.user.unset('token');

                this.keystoneClient.deauthenticate();
            }

            _.defer(function() {
                app.navigate('login', {trigger: true, replace: true});
            });
        },
        patchBackboneSync: function() {
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

                    return app.keystoneClient.authenticate()
                        .fail(function() {
                            app.logout();
                        })
                        .then(_.bind(function() {
                            options = options || {};
                            options.headers = options.headers || {};
                            options.headers['X-Auth-Token'] = app.keystoneClient.token;
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
        }
    });

    return (window.app = new App());
});
