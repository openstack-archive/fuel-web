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
            'submit': 'login',
            'keydown input': 'onKeyDown'
        },
        onKeyDown: function() {
             this.$('.login-error-message').hide();
             this.$('.login-btn').attr('disabled', false);
        },
        login: function() {
            this.$('.login-btn').attr('disabled', true);
            this.$('.login-error-message').hide();
            var keystoneClient = app.keystoneClient;
            keystoneClient.username = this.$('input[name=username]').val();
            keystoneClient.password = this.$('input[name=password]').val();
            keystoneClient.authenticate({force: true})
                .done(_.bind(function() {
                    app.user.set({
                        authenticated: true,
                        username: keystoneClient.username,
                        password: keystoneClient.password
                    });
                    app.navigate('#', {trigger: true, replace: true});
                }, this))
                .fail(_.bind(function() {
                    this.$('input:first').focus();
                    this.$('.login-error-message').show();
                }, this));
        },
        initialize: function(options) {
            _.defaults(this, options);
            if (app.user.get('authenticated')) {
                app.navigate('#', {trigger: true, replace: true});
                return;
            }
        },
        render: function() {
            if (!app.user.get('authenticated')) {
                this.$el.html(this.template({version: app.version})).i18n();
                _.defer(_.bind(function() {
                    this.$('[autofocus]:first').focus();
                }, this));
                app.footer.$el.hide();
                app.breadcrumbs.$el.hide();
                app.navbar.$el.hide();
            }
            return this;
        }
    });

    return LoginPage;
});
