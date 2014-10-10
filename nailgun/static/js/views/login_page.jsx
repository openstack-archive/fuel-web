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
    'react',
    'jsx!views/controls'
],
function($, React, controls) {
    'use strict';

    var LoginMixin, LoginPage, LoginForm, LoginCopyrights,
        cx = React.addons.classSet;

    LoginMixin = {
        login: function(username, password) {
            var keystoneClient = app.keystoneClient;

            keystoneClient.username = username;
            keystoneClient.password = password;

            return keystoneClient.authenticate({force: true})
                .done(_.bind(function() {
                    app.user.set({
                        authenticated: true,
                        username: keystoneClient.username,
                        password: keystoneClient.password
                    });
                    this.loginRedirect();
                }, this));
        },
        loginRedirect: function() {
            app.navigate('#', {trigger: true, replace: true});
        }
    };

    LoginPage = React.createClass({
        breadcrumbsPath: [],
        title: function() {
            return $.t('login_page.title');
        },
        render: function() {
            return (
                <div className="login-placeholder">
                    <div className="login-box">
                        <div className="login-logo-circle"></div>
                        <div className="login-logo"></div>
                        <div className="login-fields-box">
                            <LoginForm />
                        </div>
                    </div>
                    <LoginCopyrights />
                </div>
            );
        }
    });

    LoginForm = React.createClass({
        mixins: [
            LoginMixin
        ],
        componentDidMount: function() {
            if (app.user.get('authenticated')) {
                this.loginRedirect();
            } else {
                $(app.footer.getDOMNode()).hide();
                $(app.breadcrumbs.getDOMNode()).hide();
                $(app.navbar.getDOMNode()).hide();
            }
        },
        getInitialState: function() {
            return {
                hasError: false
            };
        },
        onChange: function(e) {
            this.setState({hasError: false});
        },
        onSubmit: function(e) {
            var username, password;

            e.preventDefault();

            username = this.refs.username.getDOMNode().value;
            password = this.refs.password.getDOMNode().value;

            this.login(username, password)
                .fail(_.bind(function() {
                    $('input[name=username]').focus();
                    this.setState({hasError: true});
                }, this));
        },
        render: function() {
            var errorDiv;

            if (this.state.hasError) {
                errorDiv = (
                    <div className="login-error-auth login-error-message">
                        <p className="text-center text-error">{$.t('login_page.login_error')}</p>
                    </div>
                );
            }

            return (
                <form className="form-horizontal" onSubmit={this.onSubmit}>
                    <fieldset>
                        <div className="control-group">
                            <label className="control-label">
                                <i className="icon-user"></i>
                            </label>
                            <div className="controls">
                                <input className="input-xlarge" type="text" name="username" ref="username" autofocus placeholder={$.t('login_page.username')} onChange={this.onChange} />
                                <span className="help-inline"></span>
                            </div>
                        </div>
                        <div className="control-group">
                            <label className="control-label">
                                <i className="icon-key"></i>
                            </label>
                            <div className="controls">
                                <input className="input-xlarge" type="password" name="password" ref="password" placeholder={$.t('login_page.password')} onChange={this.onChange} />
                                <span className="help-inline"></span>
                            </div>
                        </div>
                        {errorDiv}
                        <div className="control-group">
                            <div className="controls" style={{margin: 0, padding: 0, textAlign: 'center'}}>
                                <button type="submit" className="btn btn-success login-btn" disabled={this.state.hasError}>{$.t('login_page.log_in')}</button>
                            </div>
                        </div>
                    </fieldset>
                </form>
            );
        }
    });

    LoginCopyrights = React.createClass({
        render: function() {
            var release = app.version.get('release');

            return (
                <div className="login-copyrights">
                    <p className="text-center">{$.t('common.copyright')}</p>
                    <p className="text-center">Version: {release}</p>
                </div>
            );
        }
    });

    return LoginPage;
});
