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

    components.Footer = React.Component.extend({
        displayName: 'Footer',
        render: function () {
            return (
                <div className="footer-box">
                    {_.contains(this.props.version.feature_groups, 'mirantis') &&
                        <div>
                            <a href="http://www.mirantis.com" target="_blank" className="footer-logo"></a>
                            <div className="footer-copyright pull-left" data-i18n="common.copyright"></div>
                        </div>
                    }
                    {this.props.version.release &&
                        <div className="footer-version pull-right">Version: {this.props.version.release}</div>
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
                        return <li key={index}><a href="{part[1]}">{$.t('breadcrumbs.' + breadcrumb[0], {defaultValue: breadcrumb[0]})}</a><span className="divider">/</span></li>;
                    }
                    return <li key={index} className="active">{$.t('breadcrumbs.' + breadcrumb, {defaultValue: breadcrumb})}</li>;
                })}
            </ul>;
        }
    });

    return components;
});
