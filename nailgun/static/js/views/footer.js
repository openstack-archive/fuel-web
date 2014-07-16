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

    var Footer = React.Component.extend({
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
                                    <li>
                                        <a data-locale="{locale.locale}">{locale.name}</a>
                                    </li>
                                })}
                            </ul>
                        </div>
                    </div>
                </div>
            );
        },
        setLocale: function(e) {
            var newLocale = _.find(this.props.locales, {locale: $(e.currentTarget).data('locale')});
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

    return Footer;
});
