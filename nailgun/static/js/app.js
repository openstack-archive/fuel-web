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
    'js/coccyx_mixins',
    'models',
    'keystone_client',
    'jsx!views/root',
    'jsx!views/login_page',
    'jsx!views/welcome_page',
    'jsx!views/cluster_page',
    'jsx!views/clusters_page',
    'jsx!views/releases_page',
    'jsx!views/notifications_page',
    'jsx!views/support_page',
    'jsx!views/capacity_page',

    'react.backbone',
    'stickit',
    'routefilter',
    'bootstrap',
    'jquery-timeout',
    'less!/static/css/styles',
    'backbone-lodash-monkeypatch'

],
function($, _, i18n, Backbone, React, utils, layoutComponents, Coccyx, coccyxMixins, models, KeystoneClient, RootComponent, LoginPage, WelcomePage, ClusterPage, ClustersPage, ReleasesPage, NotificationsPage, SupportPage, CapacityPage) {
    'use strict';

    var AppRouter = Backbone.Router.extend({
        routes: {
            login: 'login',
            logout: 'logout',
            welcome: 'welcome',
            clusters: 'listClusters',
            'cluster/:id(/:tab)(/:opt1)(/:opt2)': 'showCluster',
            releases: 'listReleases',
            notifications: 'showNotifications',
            support: 'showSupportPage',
            capacity: 'showCapacityPage',
            '*default': 'default'
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
            this.statistics = new models.NodesStatistics();
            this.notifications = new models.Notifications();

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
                return this.settings.fetch()
                    .done(_.bind(function(data) {
                        //FIXME: it needs to move master_node_uid into tracking section
                        this.masterNodeUid = data.master_node_uid;
                    }, this));
            }, this)).always(_.bind(function() {
                this.renderLayout();
                Backbone.history.start();
            }, this));
        },
        renderLayout: function() {
            this.rootComponent = utils.universalMount(RootComponent, _.pick(this, 'version', 'user', 'statistics', 'notifications'), $('#main-container'));
        },
        loadPage: function(Page, options) {
            return (Page.fetchData ? Page.fetchData.apply(Page, options) : $.Deferred().resolve()).done(_.bind(function(pageOptions) {
                this.setPage(Page, pageOptions);
            }, this));
        },
        setPage: function(Page, options) {
            this.page = this.rootComponent.setPage(Page, options);
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
        default: function() {
            this.navigate('clusters', {trigger: true, replace: true});
        },
        login: function() {
            this.loadPage(LoginPage);
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
        welcome: function() {
            this.loadPage(WelcomePage);
        },
        showCluster: function() {
            this.loadPage(ClusterPage, arguments).fail(_.bind(this.default, this));
        },
        listClusters: function() {
            this.loadPage(ClustersPage);
        },
        listReleases: function() {
            this.loadPage(ReleasesPage);
        },
        showNotifications: function() {
            this.loadPage(NotificationsPage);
        },
        showSupportPage: function() {
            this.loadPage(SupportPage);
        },
        showCapacityPage: function() {
            this.loadPage(CapacityPage);
        }
    });

    return {
        initialize: function() {
            return new AppRouter();
        }
    };
});
