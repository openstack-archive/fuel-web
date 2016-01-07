/*
 * Copyright 2014 Mirantis, Inc.
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
    'views/controls',
    'component_mixins',
    'views/dialogs'
],
function($, _, i18n, Backbone, React, utils, models, controls, componentMixins, dialogs) {
    'use strict';

    let components = {};

    components.Navbar = React.createClass({
        mixins: [
            componentMixins.dispatcherMixin('updateNodeStats', 'updateNodeStats'),
            componentMixins.dispatcherMixin('updateNotifications', 'updateNotifications'),
            componentMixins.backboneMixin('user'),
            componentMixins.backboneMixin('version'),
            componentMixins.backboneMixin('statistics'),
            componentMixins.backboneMixin('notifications', 'update change:status'),
            componentMixins.pollingMixin(20)
        ],
        togglePopover: function(popoverName) {
            return _.memoize(_.bind(function(visible) {
                this.setState(function(previousState) {
                    let nextState = {};
                    let key = popoverName + 'PopoverVisible';
                    nextState[key] = _.isBoolean(visible) ? visible : !previousState[key];
                    return nextState;
                });
            }, this));
        },
        setActive: function(url) {
            this.setState({activeElement: url});
        },
        shouldDataBeFetched: function() {
            return this.props.user.get('authenticated');
        },
        fetchData: function() {
            return $.when(this.props.statistics.fetch(), this.props.notifications.fetch({limit: this.props.notificationsDisplayCount}));
        },
        updateNodeStats: function() {
            return this.props.statistics.fetch();
        },
        updateNotifications: function() {
            return this.props.notifications.fetch({limit: this.props.notificationsDisplayCount});
        },
        componentDidMount: function() {
            this.props.user.on('change:authenticated', function(model, value) {
                if (value) {
                    this.startPolling();
                } else {
                    this.stopPolling();
                    this.props.statistics.clear();
                    this.props.notifications.reset();
                }
            }, this);
        },
        getDefaultProps: function() {
            return {
                notificationsDisplayCount: 5,
                elements: [
                    {label: 'environments', url: '#clusters'},
                    {label: 'equipment', url: '#equipment'},
                    {label: 'releases', url: '#releases'},
                    {label: 'plugins', url: '#plugins'},
                    {label: 'support', url: '#support'}
                ]
            };
        },
        getInitialState: function() {
            return {};
        },
        scrollToTop: function() {
            $('html, body').animate({scrollTop: 0}, 'fast');
        },
        render: function() {
            let unreadNotificationsCount = this.props.notifications.where({status: 'unread'}).length;
            let authenticationEnabled = this.props.version.get('auth_required') && this.props.user.get('authenticated');
            return (
                <div className='navigation-box'>
                    <div className='navbar-bg'></div>
                        <nav className='navbar navbar-default' role='navigation'>
                            <div className='row'>
                                <div className='navbar-header col-xs-2'>
                                    <a className='navbar-logo' href='#'></a>
                                </div>
                                <div className='col-xs-6'>
                                    <ul className='nav navbar-nav pull-left'>
                                        {_.map(this.props.elements, function(element) {
                                            return (
                                                <li className={utils.classNames({active: this.props.activeElement == element.url.slice(1)})} key={element.label}>
                                                    <a href={element.url}>
                                                        {i18n('navbar.' + element.label, {defaultValue: element.label})}
                                                    </a>
                                                </li>
                                            );
                                        }, this)}
                                    </ul>
                                </div>
                                <div className='col-xs-4'>
                                    <ul className={utils.classNames({
                                        'nav navbar-icons pull-right': true,
                                        'with-auth': authenticationEnabled,
                                        'without-auth': !authenticationEnabled
                                    })}>
                                        <li
                                            key='language-icon'
                                            className='language-icon'
                                            onClick={this.togglePopover('language')}
                                        >
                                            <div className='language-text'>{i18n.getLocaleName(i18n.getCurrentLocale())}</div>
                                        </li>
                                        <li
                                            key='statistics-icon'
                                            className={'statistics-icon ' + (this.props.statistics.get('unallocated') ? '' : 'no-unallocated')}
                                            onClick={this.togglePopover('statistics')}
                                        >
                                            {!!this.props.statistics.get('unallocated') &&
                                                <div className='unallocated'>{this.props.statistics.get('unallocated')}</div>
                                            }
                                            <div className='total'>{this.props.statistics.get('total')}</div>
                                        </li>
                                        {authenticationEnabled &&
                                            <li
                                                key='user-icon'
                                                className='user-icon'
                                                onClick={this.togglePopover('user')}
                                            ></li>
                                        }
                                        <li
                                            key='notifications-icon'
                                            className='notifications-icon'
                                            onClick={this.togglePopover('notifications')}
                                        >
                                        <span className={utils.classNames({badge: true, visible: unreadNotificationsCount})}>
                                            {unreadNotificationsCount}
                                        </span>
                                        </li>

                                        {this.state.languagePopoverVisible &&
                                            <LanguagePopover
                                                key='language-popover'
                                                toggle={this.togglePopover('language')}
                                            />
                                        }
                                        {this.state.statisticsPopoverVisible &&
                                            <StatisticsPopover
                                                key='statistics-popover'
                                                statistics={this.props.statistics}
                                                toggle={this.togglePopover('statistics')}
                                            />
                                        }
                                        {this.state.userPopoverVisible &&
                                            <UserPopover
                                                key='user-popover'
                                                user={this.props.user}
                                                toggle={this.togglePopover('user')}
                                            />
                                        }
                                        {this.state.notificationsPopoverVisible &&
                                            <NotificationsPopover
                                                key='notifications-popover'
                                                notifications={this.props.notifications}
                                                displayCount={this.props.notificationsDisplayCount}
                                                toggle={this.togglePopover('notifications')}
                                            />
                                        }
                                    </ul>
                                </div>
                            </div>
                        </nav>
                    <div className='page-up' onClick={this.scrollToTop} />
                </div>
            );
        }
    });

    let LanguagePopover = React.createClass({
        changeLocale: function(locale, e) {
            e.preventDefault();
            this.props.toggle(false);
            _.defer(() => {
                i18n.setLocale(locale);
                location.reload();
            });
        },
        render: function() {
            let currentLocale = i18n.getCurrentLocale();
            return (
                <controls.Popover {...this.props} className='language-popover'>
                    <ul className='nav nav-pills nav-stacked'>
                        {_.map(i18n.getAvailableLocales(), function(locale) {
                            return (
                                <li key={locale} className={utils.classNames({active: locale == currentLocale})}>
                                    <a onClick={_.partial(this.changeLocale, locale)}>
                                        {i18n.getLanguageName(locale)}
                                    </a>
                                </li>
                            );
                        }, this)}
                    </ul>
                </controls.Popover>
            );
        }
    });

    let StatisticsPopover = React.createClass({
        mixins: [componentMixins.backboneMixin('statistics')],
        render: function() {
            return (
                <controls.Popover {...this.props} className='statistics-popover'>
                    <div className='list-group'>
                        <li className='list-group-item'>
                            <span className='badge'>{this.props.statistics.get('unallocated')}</span>
                            {i18n('navbar.stats.unallocated', {count: this.props.statistics.get('unallocated')})}
                        </li>
                        <li className='list-group-item text-success font-semibold'>
                            <span className='badge bg-green'>{this.props.statistics.get('total')}</span>
                            <a href='#equipment'>
                                {i18n('navbar.stats.total', {count: this.props.statistics.get('total')})}
                            </a>
                        </li>
                    </div>
                </controls.Popover>
            );
        }
    });

    let UserPopover = React.createClass({
        mixins: [componentMixins.backboneMixin('user')],
        showChangePasswordDialog: function() {
            this.props.toggle(false);
            dialogs.ChangePasswordDialog.show();
        },
        logout: function() {
            this.props.toggle(false);
            app.logout();
        },
        render: function() {
            return (
                <controls.Popover {...this.props} className='user-popover'>
                    <div className='username'>{i18n('common.username')}:</div>
                    <h3 className='name'>{this.props.user.get('username')}</h3>
                    <div className='clearfix'>
                        <button className='btn btn-default btn-sm pull-left' onClick={this.showChangePasswordDialog}>
                            <i className='glyphicon glyphicon-user'></i>
                            {i18n('common.change_password')}
                        </button>
                        <button className='btn btn-info btn-sm pull-right btn-logout' onClick={this.logout}>
                            <i className='glyphicon glyphicon-off'></i>
                            {i18n('common.logout')}
                        </button>
                    </div>
                </controls.Popover>
            );
        }
    });

    let NotificationsPopover = React.createClass({
        mixins: [componentMixins.backboneMixin('notifications')],
        showNodeInfo: function(id) {
            this.props.toggle(false);
            let node = new models.Node({id: id});
            node.fetch();
            dialogs.ShowNodeInfoDialog.show({node: node});
        },
        markAsRead: function() {
            let notificationsToMark = new models.Notifications(this.props.notifications.where({status: 'unread'}));
            if (notificationsToMark.length) {
                this.setState({unreadNotificationsIds: notificationsToMark.pluck('id')});
                notificationsToMark.toJSON = function() {
                    return notificationsToMark.map(function(notification) {
                        notification.set({status: 'read'});
                        return _.pick(notification.attributes, 'id', 'status');
                    }, this);
                };
                Backbone.sync('update', notificationsToMark);
            }
        },
        componentDidMount: function() {
            this.markAsRead();
        },
        getInitialState: function() {
            return {unreadNotificationsIds: []};
        },
        renderNotification: function(notification) {
            let topic = notification.get('topic'),
                nodeId = notification.get('node_id'),
                notificationClasses = {
                    notification: true,
                    'text-danger': topic == 'error',
                    'text-warning': topic == 'warning',
                    clickable: nodeId,
                    unread: notification.get('status') == 'unread' || _.contains(this.state.unreadNotificationsIds, notification.id)
                },
                iconClass = {
                    error: 'glyphicon-exclamation-sign',
                    warning: 'glyphicon-warning-sign',
                    discover: 'glyphicon-bell'
                }[topic] || 'glyphicon-info-sign';
            return (
                <div key={notification.id} className={utils.classNames(notificationClasses)}>
                    <i className={'glyphicon ' + iconClass}></i>
                    <p
                        dangerouslySetInnerHTML={{__html: utils.urlify(notification.escape('message'))}}
                        onClick={nodeId && _.partial(this.showNodeInfo, nodeId)}
                    />
                </div>
            );
        },
        render: function() {
            let showMore = Backbone.history.getHash() != 'notifications';
            let notifications = this.props.notifications.take(this.props.displayCount);
            return (
                <controls.Popover {...this.props} className='notifications-popover'>
                    {_.map(notifications, this.renderNotification)}
                    {showMore &&
                        <div className='show-more'>
                            <a href='#notifications'>{i18n('notifications_popover.view_all_button')}</a>
                        </div>
                    }
                </controls.Popover>
            );
        }
    });

    components.Footer = React.createClass({
        mixins: [componentMixins.backboneMixin('version')],
        render: function() {
            let version = this.props.version;
            return (
                <div className='footer'>
                    {_.contains(version.get('feature_groups'), 'mirantis') && [
                        <a key='logo' className='mirantis-logo-white' href='http://www.mirantis.com/' target='_blank'></a>,
                        <div key='copyright'>{i18n('common.copyright')}</div>
                    ]}
                    <div key='version'>{i18n('common.version')}: {version.get('release')}</div>
                </div>
            );
        }
    });

    components.Breadcrumbs = React.createClass({
        mixins: [
            componentMixins.dispatcherMixin('updatePageLayout', 'refresh')
        ],
        getInitialState: function() {
            return {path: this.getBreadcrumbsPath()};
        },
        getBreadcrumbsPath: function() {
            let page = this.props.Page;
            return _.isFunction(page.breadcrumbsPath) ? page.breadcrumbsPath(this.props.pageOptions) : page.breadcrumbsPath;
        },
        refresh: function() {
            this.setState({path: this.getBreadcrumbsPath()});
        },
        render: function() {
            return (
                <ol className='breadcrumb'>
                    {_.map(this.state.path, function(breadcrumb, index) {
                        if (!_.isArray(breadcrumb)) breadcrumb = [breadcrumb, null, {active: true}];
                        let text = breadcrumb[0];
                        let link = breadcrumb[1];
                        let options = breadcrumb[2] || {};
                        if (!options.skipTranslation) {
                            text = i18n('breadcrumbs.' + text, {defaultValue: text});
                        }
                        if (options.active) {
                            return <li key={index} className='active'>{text}</li>;
                        } else {
                            return <li key={index}><a href={link}>{text}</a></li>;
                        }
                    })}
                </ol>
            );
        }
    });

    components.DefaultPasswordWarning = React.createClass({
        render: function() {
            return (
                <div className='alert global-alert alert-warning'>
                    <button className='close' onClick={this.props.close}>&times;</button>
                    {i18n('common.default_password_warning')}
                </div>
            );
        }
    });

    components.BootstrapError = React.createClass({
        render: function() {
            return (
                <div className='alert global-alert alert-danger'>
                    {this.props.text}
                </div>
            );
        }
    });

    return components;
});
