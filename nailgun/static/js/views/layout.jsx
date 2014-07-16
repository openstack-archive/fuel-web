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
    'react',
    'utils',
    'models'
],
function(React, utils, models) {
    'use strict';

    var components = {};

    components.Navbar = React.Component.extend({
        displayName: 'Navbar',
        updateInterval: 20000,
        notificationsDisplayCount: 5,
        showChangePasswordDialog: function(e) {
            e.preventDefault();
            //this.registerSubView(new dialogViews.ChangePasswordDialog()).render();
        },
        setActive: function(url) {
            this.setState({activeElement: url});
        },
        scheduleUpdate: function() {
            $.timeout(this.updateInterval).done(_.bind(this.update, this));
        },
        update: function() {
            this.refresh().always(_.bind(this.scheduleUpdate, this));
        },
        refresh: function() {
            if (this.props.user.get('authenticated')) {
                return $.when(this.props.statistics.fetch(), this.props.notifications.fetch({limit: this.notificationsDisplayCount}));
            }
            return $.Deferred().reject();
        },
        componentDidMount: function() {
            this.props.user.on('change:authenticated', function(model, value) {
                if (value) {
                    this.refresh();
                } else {
                    this.props.statistics.clear();
                    this.props.notifications.reset();
                }
            }, this);
            this.update();
        },
        getInitialState: function() {
            return {activeElement: null};
        },
        render: function() {
            return (
                <div>
                    <div className="user-info-box">
                        {this.props.version.get('auth_required') && this.props.user.get('authenticated') &&
                            <div>
                                <i className="icon-user"></i>
                                {this.props.user.get('username')}
                                <a className="change-password">{$.t('common.change_password')}</a>
                                <a href="#logout">{$.t('common.logout')}</a>
                            </div>
                        }
                    </div>
                    <div className="navigation-bar">
                        <div className="navigation-bar-box">
                            <ul className="navigation-bar-ul">
                                <li className="product-logo">
                                    <a href="#"><div className="logo"></div></a>
                                </li>
                                {_.map(this.props.elements, function(element) {
                                    return <li key={element.label}>
                                        <a className={React.addons.classSet({active: this.state.activeElement == element.url.slice(1)})} href={element.url}>{$.t('navbar.' + element.label, {defaultValue: element.label})}</a>
                                    </li>;
                                }, this)}
                                <li className="space"></li>
                                <li className="navigation-bar-icon notifications">
                                    <i className="icon-comment"></i>
                                    {this.props.notifications.length &&
                                        <span className="badge badge-warning">{this.props.notifications.length}</span>
                                    }
                                </li>
                                <li className="navigation-bar-icon nodes-summary-container">
                                    <div className="statistic">
                                        {_.map(['total', 'unallocated'], function(prop) {
                                            var value = this.props.statistics.get(prop);
                                            return _.isUndefined(value) ? '' : [
                                                <div className="stat-count">{value}</div>,
                                                <div className="stat-title" dangerouslySetInnerHTML={{__html: utils.linebreaks(_.escape($.t('navbar.stats.' + prop, {count: value})))}}></div>
                                            ];
                                        }, this)}
                                    </div>
                                </li>
                            </ul>
                        </div>
                    </div>
                    <div className="notification-wrapper"></div>
                </div>
            );
            //this.popover = new views.NotificationsPopover({collection: this.notifications, navbar: this});
            //this.registerSubView(this.popover);
            //this.$('.notification-wrapper').html(this.popover.render().el);
        }
    });

    components.Footer = React.Component.extend({
        displayName: 'Footer',
        render: function () {
            return (
                <div className="footer-box">
                    {_.contains(this.props.version.get('feature_groups'), 'mirantis') &&
                        <div>
                            <a href="http://www.mirantis.com" target="_blank" className="footer-logo"></a>
                            <div className="footer-copyright pull-left" data-i18n="common.copyright"></div>
                        </div>
                    }
                    {this.props.version.get('release') &&
                        <div className="footer-version pull-right">Version: {this.props.version.get('release')}</div>
                    }
                    <div className="footer-lang pull-right">
                        <div className="dropdown dropup">
                            <button className="dropdown-toggle current-locale btn btn-link" data-toggle="dropdown">{this.getCurrentLocale().name}</button>
                            <ul className="dropdown-menu locales">
                                {_.map(this.props.locales, function(locale) {
                                    return <li key={locale.name} onClick={_.bind(this.setLocale, this, locale)}>
                                        <a>{locale.name}</a>
                                    </li>
                                }, this)}
                            </ul>
                        </div>
                    </div>
                </div>
            );
        },
        setLocale: function(newLocale) {
            $.i18n.setLng(newLocale.locale, {});
            window.location.reload();
        },
        getAvailableLocales: function() {
            return _.map(_.keys($.i18n.options.resStore).sort(), function(locale) {
                return {locale: locale, name: $.t('language', {lng: locale})};
            }, this);
        },
        getCurrentLocale: function() {
            return _.find(this.props.locales, {locale: $.i18n.lng()});
        },
        setDefaultLocale: function() {
            if (!this.getCurrentLocale()) {
                $.i18n.setLng(this.props.locales[0].locale, {});
            }
        },
        getDefaultProps: function() {
            return {locales: this.getAvailableLocales()};
        },
        componentWillMount: function(options) {
            this.setDefaultLocale();
        }
    });

    components.Breadcrumbs = React.Component.extend({
        displayName: 'Breadcrumbs',
        setPath: function(path) {
            this.setProps({path: path});
        },
        render: function() {
            return <ul className="breadcrumb">
                {_.map(this.props.path, function(breadcrumb, index) {
                    if (_.isArray(breadcrumb)) {
                        if (breadcrumb[2]) {
                            return <li key={index} className="active">{breadcrumb[0]}</li>;
                        }
                        return <li key={index}><a href={breadcrumb[1]}>{$.t('breadcrumbs.' + breadcrumb[0], {defaultValue: breadcrumb[0]})}</a><span className="divider">/</span></li>;
                    }
                    return <li key={index} className="active">{$.t('breadcrumbs.' + breadcrumb, {defaultValue: breadcrumb})}</li>;
                })}
            </ul>;
        }
    });

    return components;
});
