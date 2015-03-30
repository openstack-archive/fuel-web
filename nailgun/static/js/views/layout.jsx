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
    'i18next',
    'backbone',
    'react',
    'utils',
    'models',
    'jsx!component_mixins',
    'jsx!views/dialogs'
],
function($, _, i18n, i18next, Backbone, React, utils, models, componentMixins, dialogs) {
    'use strict';

    var components = {};

    components.Navbar = React.createClass({
        mixins: [
            componentMixins.dispatcherMixin('updateNodeStats', 'updateNodeStats'),
            componentMixins.dispatcherMixin('updateNotifications', 'updateNotifications'),
            componentMixins.backboneMixin('user'),
            componentMixins.backboneMixin('version'),
            componentMixins.backboneMixin('statistics'),
            componentMixins.backboneMixin('notifications', 'add remove change:status'),
            componentMixins.pollingMixin(20)
        ],
        showChangePasswordDialog: function(e) {
            e.preventDefault();
            dialogs.ChangePasswordDialog.show();
        },
        togglePopover: function(popoverName) {
            return _.memoize(_.bind(function(visible) {
                this.setState(function(previousState) {
                    var nextState = {};
                    var key = popoverName + 'PopoverVisible';
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
                    {label: 'releases', url: '#releases'},
                    {label: 'support', url: '#support'}
                ]
            };
        },
        getInitialState: function() {
            return {};
        },
        render: function() {
            var unreadNotificationsCount = this.props.notifications.where({status: 'unread'}).length;
            return (
                <div className='navigation-box'>
                    <div className='navbar-bg'></div>
                    <div className='row'>
                        <nav className='navbar navbar-default' role='navigation'>
                            <div className='container-fluid'>
                                <div className='navbar-header'>
                                    <a className='navbar-logo' href='#'></a>
                                </div>
                                <ul className='nav navbar-nav'>
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
                                <ul className='nav navbar-icons navbar-right'>
                                    <li className='lang-icon'>
                                        <div className='lang-text'>EN</div>
                                    </li>
                                    <li
                                        className={'usage-icon ' + (this.props.statistics.get('unallocated') ? '' : 'no-unallocated')}
                                        onClick={this.togglePopover('statistics')}
                                    >
                                        {!!this.props.statistics.get('unallocated') &&
                                            <div className='unallocated'>{this.props.statistics.get('unallocated')}</div>
                                        }
                                        <div className='total'>{this.props.statistics.get('total')}</div>
                                        {this.state.statisticsPopoverVisible &&
                                            <StatisticsPopover
                                                statistics={this.props.statistics}
                                                toggle={this.togglePopover('statistics')}
                                            />
                                        }
                                    </li>
                                    {this.props.version.get('auth_required') && this.props.user.get('authenticated') &&
                                        <li className='user-icon' onClick={this.togglePopover('authentication')}>
                                            {this.state.authenticationPopoverVisible &&
                                                <AuthenticationPopover
                                                    user={this.props.user}
                                                    toggle={this.togglePopover('authentication')}
                                                />
                                            }
                                        </li>
                                    }
                                    <li className='notice-icon' onClick={this.togglePopover('notifications')}>
                                        {unreadNotificationsCount ? <span className='badge'>{unreadNotificationsCount}</span> : null}
                                        {this.state.notificationsPopoverVisible &&
                                            <NotificationsPopover
                                                notifications={this.props.notifications}
                                                displayCount={this.props.notificationsDisplayCount}
                                                toggle={this.togglePopover('notifications')}
                                            />
                                        }
                                    </li>
                                </ul>
                            </div>
                        </nav>
                    </div>
                </div>
            );
        }
    });

    var StatisticsPopover = React.createClass({
        mixins: [
            componentMixins.outerClickMixin,
            componentMixins.backboneMixin('statistics')
        ],
        render: function() {
            return (
                <div className='navbar-popover popover bottom in'>
                    <div className='arrow' />
                    <div className='popover-content'>
                        StatisticsPopover content
                    </div>
                </div>
            );
        }
    });

    var AuthenticationPopover = React.createClass({
        mixins: [
            componentMixins.outerClickMixin,
            componentMixins.backboneMixin('user')
        ],
        render: function() {
            return (
                <div className='navbar-popover popover bottom in'>
                    <div className='arrow' />
                    <div className='popover-content'>
                        AuthenticationPopover content
                    </div>
                </div>
            );
        }
    });

    var NotificationsPopover = React.createClass({
        mixins: [
            componentMixins.outerClickMixin,
            componentMixins.backboneMixin('notifications')
        ],
        showNodeInfo: function(id) {
            var node = new models.Node({id: id});
            node.fetch();
            dialogs.ShowNodeInfoDialog.show({node: node});
        },
        markAsRead: function() {
            var notificationsToMark = new models.Notifications(this.props.notifications.where({status: 'unread'}));
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
            var notificationClasses = {
                    'text-red': notification.get('topic') == 'error',
                    'text-orange': notification.get('topic') == 'warning',
                    unread: notification.get('status') == 'unread' || _.contains(this.state.unreadNotificationsIds, notification.id)
                },
                iconClass = {
                    error: 'glyphicon-exclamation-sign',
                    warning: 'glyphicon-warning-sign',
                    discover: 'glyphicon-bell'
                }[notification.get('topic')] || 'glyphicon-info-sign';
            return (
                <div
                    className={'notification ' + utils.classNames(notificationClasses)}
                    onClick={notification.get('node_id') && _.partial(this.showNodeInfo, notification.get('node_id'))}
                >
                    <i className={'glyphicon ' + iconClass}></i>
                    <span dangerouslySetInnerHTML={{__html: utils.urlify(notification.escape('message'))}}></span>
                </div>
            );
        },
        render: function() {
            var showMore = Backbone.history.getHash() != 'notifications';
            var notifications = this.props.notifications.first(this.props.displayCount);
            return (
                <div className='notifications-popover popover bottom in'>
                    <div className='arrow' />
                    <div className='popover-content'>
                        {_.map(notifications, function(notification, index) {
                            return [
                                !!index && <hr />,
                                this.renderNotification(notification)
                            ];
                        }, this)}
                        {showMore &&
                            <div className='show-more'>
                                <hr />
                                <a href='#notifications'>{i18n('notifications_popover.view_all_button')}</a>
                            </div>
                        }
                    </div>
                </div>
            );
        }
    });

    components.Footer = React.createClass({
        mixins: [componentMixins.backboneMixin('version')],
        render: function() {
            var version = this.props.version;
            return (
                <div className='footer'>
                    {_.contains(version.get('feature_groups'), 'mirantis') && [
                        <a key='logo' className="mirantis-logo-white" href='http://www.mirantis.com/' target='_blank'></a>,
                        <div key='copyright'>{i18n('common.copyright')}</div>
                    ]}
                    <div key='version'>Version: {version.get('release')}</div>
                </div>
            );
        }

        // FIXME(vkramskikh): restore functionality

        //setLocale: function(newLocale) {
        //    i18next.setLng(newLocale.locale, {});
        //    window.location.reload();
        //},
        //getAvailableLocales: function() {
        //    return _.map(_.keys(i18next.options.resStore).sort(), function(locale) {
        //        return {locale: locale, name: i18n('language', {lng: locale})};
        //    }, this);
        //},
        //getCurrentLocale: function() {
        //    return _.find(this.props.locales, {locale: i18next.lng()});
        //},
        //setDefaultLocale: function() {
        //    if (!this.getCurrentLocale()) {
        //        i18next.setLng(this.props.locales[0].locale, {});
        //    }
        //},
        //getDefaultProps: function() {
        //    return {locales: this.prototype.getAvailableLocales()};
        //},
        //componentWillMount: function() {
        //    this.setDefaultLocale();
        //}
    });

    components.Breadcrumbs = React.createClass({
        mixins: [
            componentMixins.dispatcherMixin('updatePageLayout', 'refresh')
        ],
        getInitialState: function() {
            return {path: this.getBreadcrumbsPath()};
        },
        getBreadcrumbsPath: function() {
            var page = this.props.Page;
            return _.isFunction(page.breadcrumbsPath) ? page.breadcrumbsPath(this.props.pageOptions) : page.breadcrumbsPath;
        },
        refresh: function() {
            this.setState({path: this.getBreadcrumbsPath()});
        },
        render: function() {
            return (
                <ol className='breadcrumb'>
                    {_.map(this.state.path, function(breadcrumb, index) {
                        if (_.isArray(breadcrumb)) {
                            if (breadcrumb[2]) {
                                return <li key={index} className='active'>{breadcrumb[0]}</li>;
                            }
                            return <li key={index}><a href={breadcrumb[1]}><strong>{i18n('breadcrumbs.' + breadcrumb[0], {defaultValue: breadcrumb[0]})}</strong></a></li>;
                        }
                        return <li key={index} className='active'>{i18n('breadcrumbs.' + breadcrumb, {defaultValue: breadcrumb})}</li>;
                    })}
                </ol>
            );
        }
    });

    return components;
});
