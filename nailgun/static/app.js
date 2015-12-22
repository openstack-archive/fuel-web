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
    'models',
    'keystone_client',
    'views/root',
    'views/dialogs',
    'views/login_page',
    'views/welcome_page',
    'views/cluster_page',
    'views/clusters_page',
    'views/equipment_page',
    'views/releases_page',
    'views/plugins_page',
    'views/notifications_page',
    'views/support_page',
    'views/capacity_page',

    'backbone.routefilter',
    'bootstrap',
    './styles/main.less'
],
function($, _, i18n, Backbone, React, utils, models, KeystoneClient, RootComponent, dialogs, LoginPage, WelcomePage, ClusterPage, ClustersPage, EquipmentPage, ReleasesPage, PluginsPage, NotificationsPage, SupportPage, CapacityPage) {
    'use strict';

    class Router extends Backbone.Router {
        routes() {
            return {
                login: 'login',
                logout: 'logout',
                welcome: 'welcome',
                clusters: 'listClusters',
                'cluster/:id(/:tab)(/:opt1)(/:opt2)': 'showCluster',
                equipment: 'showEquipmentPage',
                releases: 'listReleases',
                plugins: 'listPlugins',
                notifications: 'showNotifications',
                support: 'showSupportPage',
                capacity: 'showCapacityPage',
                '*default': 'default'
            };
        }

        // pre-route hook
        before(currentRouteName) {
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
                    {name: 'login', condition: () => {
                        var result = app.version.get('auth_required') && !app.user.get('authenticated');
                        if (result && currentUrl != 'login' && currentUrl != 'logout') this.returnUrl = currentUrl;
                        return result;
                    }},
                    {name: 'welcome', condition: (previousUrl) => {
                        return previousUrl != 'logout' && !app.fuelSettings.get('statistics.user_choice_saved.value');
                    }}
                ];
                _.each(specialRoutes, (route) => {
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
                });
            }
            return !preventRouting;
        }

        // routes
        default() {
            this.navigate('clusters', {trigger: true, replace: true});
        }

        login() {
            app.loadPage(LoginPage);
        }

        logout() {
            app.logout();
        }

        welcome() {
            app.loadPage(WelcomePage);
        }

        showCluster(clusterId, tab) {
            var tabs = _.pluck(ClusterPage.getTabs(), 'url');
            if (!tab || !_.contains(tabs, tab)) {
                this.navigate('cluster/' + clusterId + '/' + tabs[0], {trigger: true, replace: true});
            } else {
                app.loadPage(ClusterPage, arguments).fail(() => this.default());
            }
        }

        listClusters() {
            app.loadPage(ClustersPage);
        }

        showEquipmentPage() {
            app.loadPage(EquipmentPage);
        }

        listReleases() {
            app.loadPage(ReleasesPage);
        }

        listPlugins() {
            app.loadPage(PluginsPage);
        }

        showNotifications() {
            app.loadPage(NotificationsPage);
        }

        showSupportPage() {
            app.loadPage(SupportPage);
        }

        showCapacityPage() {
            app.loadPage(CapacityPage);
        }
    }

    class App {
        constructor() {
            this.initialized = false;

            // this is needed for IE, which caches requests resulting in wrong results (e.g /ostf/testruns/last/1)
            $.ajaxSetup({cache: false});

            this.router = new Router();
            this.keystoneClient = new KeystoneClient('/keystone', {
                cacheTokenFor: 10 * 60 * 1000,
                tenant: 'admin'
            });
            this.version = new models.FuelVersion();
            this.fuelSettings = new models.FuelSettings();
            this.user = new models.User();
            this.statistics = new models.NodesStatistics();
            this.notifications = new models.Notifications();
            this.releases = new models.Releases();
            this.nodeNetworkGroups = new models.NodeNetworkGroups();
        }

        initialize() {
            this.initialized = true;
            this.mountNode = $('#main-container');

            document.title = i18n('common.title');

            return this.version.fetch()
                .then(() => {
                    this.user.set({authenticated: !this.version.get('auth_required')});
                    this.patchBackboneSync();
                    if (this.version.get('auth_required')) {
                        _.extend(this.keystoneClient, this.user.pick('token'));
                        return this.keystoneClient.authenticate()
                            .done(() => this.user.set({authenticated: true}));
                    }
                    return $.Deferred().resolve();
                })
                .then(() => {
                    return $.when(
                        this.fuelSettings.fetch(),
                        this.nodeNetworkGroups.fetch()
                    );
                })
                .then(null, () => {
                    if (this.version.get('auth_required') && !this.user.get('authenticated')) {
                        return $.Deferred().resolve();
                    } else {
                        this.mountNode.empty();
                        dialogs.NailgunUnavailabilityDialog.show({}, {preventDuplicate: true});
                    }
                })
                .then(() => Backbone.history.start());
        }

        renderLayout() {
            var wrappedRootComponent = React.render(
                React.createElement(
                    RootComponent,
                    _.pick(this, 'version', 'user', 'fuelSettings', 'statistics', 'notifications')
                ),
                this.mountNode[0]
            );
            // RootComponent is wrapped with React-DnD, extracting link to it using ref
            this.rootComponent = wrappedRootComponent.refs.child;
        }

        loadPage(Page, options = []) {
            return (Page.fetchData ? Page.fetchData(...options) : $.Deferred().resolve()).done((pageOptions) => {
                if (!this.rootComponent) this.renderLayout();
                this.setPage(Page, pageOptions);
            });
        }

        setPage(Page, options) {
            this.page = this.rootComponent.setPage(Page, options);
        }

        navigate(...args) {
            return this.router.navigate(...args);
        }

        logout() {
            if (this.user.get('authenticated') && this.version.get('auth_required')) {
                this.user.set('authenticated', false);
                this.user.unset('username');
                this.user.unset('token');

                this.keystoneClient.deauthenticate();
            }

            _.defer(() => this.navigate('login', {trigger: true, replace: true}));
        }

        patchBackboneSync() {
            var originalSync = Backbone.sync;
            if (originalSync.patched) return;
            Backbone.sync = function(method, model, options = {}) {
                // our server doesn't support PATCH, so use PUT instead
                if (method == 'patch') {
                    method = 'update';
                }
                // add auth token to header if auth is enabled
                if (app.version.get('auth_required') && !this.authExempt) {
                    return app.keystoneClient.authenticate()
                        .fail(() => app.logout())
                        .then(() => {
                            options.headers = options.headers || {};
                            options.headers['X-Auth-Token'] = app.keystoneClient.token;
                            return originalSync.call(this, method, model, options);
                        })
                        .fail((response) => {
                            if (response && response.status == 401) {
                                app.logout();
                            }
                        });
                }
                return originalSync.call(this, method, model, options);
            };
            Backbone.sync.patched = true;
        }
    }

    window.app = new App();

    $(() => app.initialize());

    return app;
});
