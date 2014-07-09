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
    'models',
    'views/dialogs',
    'text!templates/common/navbar.html',
    'text!templates/common/nodes_stats.html',
    'text!templates/common/notifications.html',
    'text!templates/common/notifications_popover.html',
    'text!templates/common/breadcrumb.html',
    'text!templates/common/footer.html'
],
function(utils, models, dialogViews, navbarTemplate, nodesStatsTemplate, notificationsTemplate, notificationsPopoverTemplate, breadcrumbsTemplate, footerTemplate) {
    'use strict';

    var views = {};

    views.Page = Backbone.View.extend({
        navbarActiveElement: null,
        breadcrumbsPath: null,
        title: null,
        updateNavbar: function() {
            app.navbar.setActive(_.result(this, 'navbarActiveElement'));
        },
        updateBreadcrumbs: function() {
            app.breadcrumbs.setPath(_.result(this, 'breadcrumbsPath'));
        },
        updateTitle: function() {
            var defaultTitle = $.t('common.title');
            var title = _.result(this, 'title');
            document.title = title ? defaultTitle + ' - ' + title : defaultTitle;
        }
    });

    views.Tab = Backbone.View.extend({
        initialize: function(options) {
            _.defaults(this, options);
        }
    });

    views.Navbar = Backbone.View.extend({
        className: 'container',
        template: _.template(navbarTemplate),
        updateInterval: 20000,
        notificationsDisplayCount: 5,
        events: {
            'click .change-password': 'showChangePasswordDialog'
        },
        showChangePasswordDialog: function(e) {
            e.preventDefault();
            this.registerSubView(new dialogViews.ChangePasswordDialog()).render();
        },
        setActive: function(url) {
            this.elements.each(function(element) {
                element.set({active: element.get('url') == '#' + url});
            });
        },
        scheduleUpdate: function() {
            this.registerDeferred($.timeout(this.updateInterval).done(_.bind(this.update, this)));
        },
        update: function() {
            this.refresh().always(_.bind(this.scheduleUpdate, this));
        },
        refresh: function() {
            if (app.user.get('authenticated')) {
                return $.when(this.statistics.fetch(), this.notifications.fetch({limit: this.notificationsDisplayCount}));
            }
            return $.Deferred().reject();
        },
        initialize: function(options) {
            this.elements = new Backbone.Collection(options.elements);
            this.elements.invoke('set', {active: false});
            this.elements.on('change:active', this.render, this);
            app.user.on('change:authenticated', function(model, value) {
                if (value) {
                    this.refresh();
                } else {
                    this.statistics.clear();
                    this.notifications.reset();
                }
                this.render();
            }, this);
            this.statistics = new models.NodesStatistics();
            this.notifications = new models.Notifications();
            this.update();
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            this.$el.html(this.template({
                elements: this.elements,
                user: app.user,
                version: app.version
            }));
            this.stats = new views.NodesStats({statistics: this.statistics, navbar: this});
            this.registerSubView(this.stats);
            this.$('.nodes-summary-container').html(this.stats.render().el);
            this.notificationsButton = new views.Notifications({collection: this.notifications, navbar: this});
            this.registerSubView(this.notificationsButton);
            this.$('.notifications').html(this.notificationsButton.render().el);
            this.popover = new views.NotificationsPopover({collection: this.notifications, navbar: this});
            this.registerSubView(this.popover);
            this.$('.notification-wrapper').html(this.popover.render().el);
            return this;
        }
    });

    views.NodesStats = Backbone.View.extend({
        template: _.template(nodesStatsTemplate),
        bindings: {
            '.total-nodes-count': {
                observe: 'total',
                onGet: 'returnValueOrNonBreakingSpace'
            },
            '.total-nodes-title': {
                observe: 'total',
                onGet: 'formatTitle',
                updateMethod: 'html'
            },
            '.unallocated-nodes-count': {
                observe: 'unallocated',
                onGet: 'returnValueOrNonBreakingSpace'
            },
            '.unallocated-nodes-title': {
                observe: 'unallocated',
                onGet: 'formatTitle',
                updateMethod: 'html'
            }
        },
        returnValueOrNonBreakingSpace: function(value) {
            return !_.isUndefined(value) ? value : '\u00A0';
        },
        formatTitle: function(value, options) {
            return !_.isUndefined(value) ? utils.linebreaks(_.escape($.t('navbar.stats.' + options.observe, {count: value}))) : '';
        },
        initialize: function(options) {
            _.defaults(this, options);
        },
        render: function() {
            this.$el.html(this.template({stats: this.statistics}));
            this.stickit(this.statistics);
            return this;
        }
    });

    views.Notifications = Backbone.View.extend({
        template: _.template(notificationsTemplate),
        events: {
            'click .icon-comment': 'togglePopover',
            'click .badge': 'togglePopover'
        },
        togglePopover: function(e) {
            this.navbar.popover.toggle();
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.collection.on('sync reset', this.render, this);
        },
        render: function() {
            this.$el.html(this.template({
                notifications: this.collection.where({status: 'unread'}),
                authenticated: app.user.get('authenticated')
            }));
            return this;
        }
    });

    views.NotificationsPopover = Backbone.View.extend({
        template: _.template(notificationsPopoverTemplate),
        templateHelpers: _.pick(utils, 'urlify'),
        visible: false,
        events: {
            'click .discover[data-node]' : 'showNodeInfo'
        },
        showNodeInfo: function(e) {
            this.toggle();
            var node = new models.Node({id: $(e.currentTarget).data('node')});
            node.deferred = node.fetch();
            var dialog = new dialogViews.ShowNodeInfoDialog({node: node});
            this.registerSubView(dialog);
            dialog.render();
        },
        toggle: function() {
            this.visible = !this.visible;
            this.render();
        },
        hide: function(e) {
            if (this.visible && (!e || (!$(e.target).closest(this.navbar.notificationsButton.el).length && !$(e.target).closest(this.el).length))) {
                this.visible = false;
                this.render();
            }
        },
        markAsRead: function() {
            var notificationsToMark = new models.Notifications(this.collection.where({status : 'unread'}));
            if (notificationsToMark.length) {
                notificationsToMark.toJSON = function() {
                    return notificationsToMark.map(function(notification) {
                        notification.set({status: 'read'}, {silent: true});
                        return _.pick(notification.attributes, 'id', 'status');
                    }, this);
                };
                Backbone.sync('update', notificationsToMark).done(_.bind(function() {
                    this.collection.trigger('sync');
                }, this));
            }
        },
        beforeTearDown: function() {
            this.unbindEvents();
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.collection.bind('add', this.render, this);
            this.eventNamespace = 'click.click-notifications';
        },
        bindEvents: function() {
            $('html').on(this.eventNamespace, _.bind(this.hide, this));
            Backbone.history.on('route', this.hide, this);
        },
        unbindEvents: function() {
            $('html').off(this.eventNamespace);
            Backbone.history.off('route', this.hide, this);
        },
        render: function() {
            if (this.visible) {
                this.$el.html(this.template(_.extend({
                    notifications: this.collection,
                    displayCount: this.navbar.notificationsDisplayCount,
                    showMore: (Backbone.history.getHash() != 'notifications') && this.collection.length
                }, this.templateHelpers))).i18n();
                this.markAsRead();
                this.bindEvents();
            } else {
                this.$el.html('');
                this.unbindEvents();
            }
            return this;
        }
    });

    views.Breadcrumbs = Backbone.View.extend({
        className: 'container',
        template: _.template(breadcrumbsTemplate),
        path: [],
        setPath: function(path) {
            this.path = path;
            this.render();
        },
        render: function() {
            this.$el.html(this.template({path: this.path}));
            return this;
        }
    });

    views.Footer = Backbone.View.extend({
        template: _.template(footerTemplate),
        events: {
            'click .footer-lang li a': 'setLocale'
        },
        setLocale: function(e) {
            var newLocale = _.find(this.locales, {locale: $(e.currentTarget).data('locale')});
            $.i18n.setLng(newLocale.locale, {});
            window.location.reload();
        },
        getAvailableLocales: function() {
            return _.map(_.keys($.i18n.options.resStore).sort(), function(locale) {
                return {locale: locale, name: $.t('language', {lng: locale})};
            }, this);
        },
        getCurrentLocale: function() {
            return _.find(this.locales, {locale: $.i18n.lng()});
        },
        setDefaultLocale: function() {
            var currentLocale = this.getCurrentLocale();
            if (!currentLocale) {
                $.i18n.setLng(this.locales[0].locale, {});
            }
        },
        initialize: function(options) {
            this.locales = this.getAvailableLocales();
            this.setDefaultLocale();
            app.version.on('sync', this.render, this);
        },
        render: function() {
            this.$el.html(this.template({
                version: app.version,
                locales: this.locales,
                currentLocale: this.getCurrentLocale()
            })).i18n();
            return this;
        }
    });

    return views;
});
