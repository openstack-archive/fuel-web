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
    'views/common',
    'text!templates/login/page.html'
],
function(commonViews, loginPageTemplate) {
    'use strict';

    var LoginPage = commonViews.Page.extend({
        breadcrumbsPath: [],
        title: function() {
            return $.t('login_page.title');
        },
        template: _.template(loginPageTemplate),
        events: {
            'click .login-btn': 'login',
            'keydown': 'onKeyDown',
            'click .login-language-box li a': 'setLocale'
        },
        onKeyDown: function(e) {
            if (e.keyCode == 13) {
               this.login();
            }
        },
        login: function() {
            this.$('.login-error-message').hide();
            var keystoneClient = app.keystoneClient;
            keystoneClient.username = this.$('input[name=username]').val();
            keystoneClient.password = this.$('input[name=password]').val();
            keystoneClient.updateToken({force: true})
                .done(_.bind(function() {
                    app.user.set({
                        authenticated: true,
                        username: keystoneClient.username,
                        token: keystoneClient.token
                    });
                    app.navigate('#', {trigger: true, replace: true});
                }, this))
                .fail(_.bind(function() {
                    this.$('.login-error-message').show();
                }, this));
        },
        setLocale: function(e) {
            console.log('set locale');
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
            _.defaults(this, options);
            this.locales = this.getAvailableLocales();
            this.setDefaultLocale();
            if (app.user.get('authenticated')) {
                app.navigate('#', {trigger: true, replace: true});
                return;
            }
        },
        render: function() {
            this.$el.html(this.template({
                locales: this.locales,
                currentLocale: this.getCurrentLocale()
            })).i18n();
            _.defer(_.bind(function() {
                this.$('[autofocus]:first').focus();
            }, this));
            return this;
        }
    });

    return LoginPage;
});
