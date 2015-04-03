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
        togglePopover: function(visible) {
            this.setState({popoverVisible: _.isBoolean(visible) ? visible : !this.state.popoverVisible});
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
        handleBodyClick: function(e) {
            if (_.all([this.refs.popover, this.refs.notifications], function(component) {
                return !$(e.target).closest(component.getDOMNode()).length;
            })) {
                _.defer(_.partial(this.togglePopover, false));
            }
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
            return {
                popoverVisible: false
            };
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
                                    <li className='lang-icon'><div className='lang-text'>EN</div></li>
                                    <li className={'usage-icon ' + (this.props.statistics.get('unallocated') ? '' : 'new')}>
                                        {!!this.props.statistics.get('unallocated') &&
                                            <div className='unused'>{this.props.statistics.get('unallocated')}</div>
                                        }
                                        <div className='total'>{this.props.statistics.get('total')}</div>
                                    </li>
                                    {this.props.version.get('auth_required') && this.props.user.get('authenticated') &&
                                        <li className='user-icon'></li>
                                    }
                                    <li className='notice-icon' ref='notifications' onClick={this.togglePopover}>
                                        {unreadNotificationsCount ? <span className='badge'>{unreadNotificationsCount}</span> : null}
                                    </li>
                                </ul>
                            </div>
                        </nav>
                    </div>
                </div>
            );/*

                                <Notifications ref='notifications'
                                    notifications={this.props.notifications}
                                    togglePopover={this.togglePopover}
                                />
                                <NodeStats statistics={this.props.statistics} />
                            </ul>
                        </div>
                    </div>
                    <div className='notification-wrapper'>
                        {this.state.popoverVisible &&
                            <NotificationsPopover ref='popover'
                                notifications={this.props.notifications}
                                displayCount={this.props.notificationsDisplayCount}
                                togglePopover={this.togglePopover}
                                handleBodyClick={this.handleBodyClick}
                            />
                        }
                    </div>
                </div>
            );*/
        }
    });

    var NodeStats = React.createClass({
        mixins: [componentMixins.backboneMixin('statistics')],
        render: function() {
            return (
                <li className='navigation-bar-icon nodes-summary-container'>
                    <div className='statistic'>
                        {_.map(['total', 'unallocated'], function(prop) {
                            var value = this.props.statistics.get(prop);
                            return _.isUndefined(value) ? '' : [
                                <div className='stat-count'>{value}</div>,
                                <div className='stat-title' dangerouslySetInnerHTML={{__html: utils.linebreaks(_.escape(i18n('navbar.stats.' + prop, {count: value})))}}></div>
                            ];
                        }, this)}
                    </div>
                </li>
            );
        }
    });

    var NotificationsPopover = React.createClass({
        mixins: [componentMixins.backboneMixin('notifications')],
        getDefaultProps: function() {
            return {
                eventNamespace: 'click.click-notifications'
            };
        },
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
            $('html').on(this.props.eventNamespace, this.props.handleBodyClick);
            Backbone.history.on('route', _.partial(this.props.togglePopover, false), this);
        },
        componentWillUnmount: function() {
            $('html').off(this.props.eventNamespace);
            Backbone.history.off('route', this.props.togglePopover, this);
        },
        getInitialState: function() {
            return {unreadNotificationsIds: []};
        },
        render: function() {
            var showMore = (Backbone.history.getHash() != 'notifications') && this.props.notifications.length;
            var notifications = this.props.notifications.first(this.props.displayCount);
            return (
                <div className='message-list-placeholder'>
                    <ul className='message-list-popover'>
                        {this.props.notifications.length ? (
                            _.map(notifications, function(notification, index, collection) {
                                var unread = notification.get('status') == 'unread' || _.contains(this.state.unreadNotificationsIds, notification.id);
                                var nodeId = notification.get('node_id');
                                return [
                                    <li
                                        key={'notification' + notification.id}
                                        className={utils.classNames({'enable-selection': true, new: unread, clickable: nodeId}) + ' ' + notification.get('topic')}
                                        onClick={nodeId && _.bind(this.showNodeInfo, this, nodeId)}
                                    >
                                        <i className={{error: 'icon-attention', warning: 'icon-attention', discover: 'icon-bell'}[notification.get('topic')] || 'icon-info-circled'}></i>
                                        <span dangerouslySetInnerHTML={{__html: utils.urlify(notification.escape('message'))}}></span>
                                    </li>,
                                    (showMore || index < (collection.length - 1)) && <li key={'divider' + notification.id} className='divider'></li>
                                ];
                            }, this)
                        ) : <li key='no_notifications'>{i18n('notifications_popover.no_notifications_text')}</li>}
                    </ul>
                    {showMore && <div className='show-more-notifications'><a href='#notifications'>{i18n('notifications_popover.view_all_button')}</a></div>}
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
