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
    'react'
],
function($, _, i18n, React) {
    'use strict';

    var LoginPage = React.createClass({
        statics: {
            title: i18n('login_page.title'),
            hiddenLayout: true
        },
        render: function() {
            return (
                <div className='login-placeholder'>
                    <div className='login-box'>
                        <div className='login-logo-circle'></div>
                        <div className='login-logo'></div>
                        <div className='login-fields-box'>
                            <LoginForm />
                        </div>
                    </div>
                </div>
            );
        }
    });

    var LoginForm = React.createClass({
        login: function(username, password) {
            var keystoneClient = app.keystoneClient;

            return keystoneClient.authenticate(username, password, {force: true})
                .fail(_.bind(function() {
                    $(this.refs.username.getDOMNode()).focus();
                    this.setState({hasError: true});
                }, this))
                .then(_.bind(function() {
                    app.user.set({
                        authenticated: true,
                        username: username,
                        token: keystoneClient.token
                    });
                    return $.when(app.version.fetch({cache: true}), app.settings.fetch({cache: true}));
                }, this))
                .done(_.bind(function() {
                    app.navigate('', {trigger: true});
                }));
        },
        componentDidMount: function() {
            $(this.refs.username.getDOMNode()).focus();
        },
        getInitialState: function() {
            return {
                actionInProgress: false,
                hasError: false
            };
        },
        onChange: function() {
            this.setState({hasError: false});
        },
        onSubmit: function(e) {
            var username, password;

            e.preventDefault();

            username = this.refs.username.getDOMNode().value;
            password = this.refs.password.getDOMNode().value;

            this.setState({actionInProgress: true});

            this.login(username, password)
                .fail(_.bind(function() {
                    this.setState({actionInProgress: false});
                }, this));
        },
        render: function() {
            var loginButtonDisabled = this.state.hasError || this.state.actionInProgress;

            return (
                <form className='form-horizontal' onSubmit={this.onSubmit}>
                    <fieldset>
                        <div className='control-group'>
                            <label className='control-label'>
                                <i className='icon-user'></i>
                            </label>
                            <div className='controls'>
                                <input className='input-xlarge' type='text' name='username' ref='username' placeholder={i18n('login_page.username')} onChange={this.onChange} />
                            </div>
                        </div>
                        <div className='control-group'>
                            <label className='control-label'>
                                <i className='icon-key'></i>
                            </label>
                            <div className='controls'>
                                <input className='input-xlarge' type='password' name='password' ref='password' placeholder={i18n('login_page.password')} onChange={this.onChange} />
                            </div>
                        </div>
                        {this.state.hasError && (
                                <div className='login-error-auth login-error-message'>
                                    <p className='text-center text-error'>{i18n('login_page.login_error')}</p>
                                </div>
                            )
                        }
                        <div className='control-group'>
                            <div id='login-button-control' className='controls'>
                                <button type='submit' className='btn btn-success login-btn' disabled={loginButtonDisabled}>{i18n('login_page.log_in')}</button>
                            </div>
                        </div>
                    </fieldset>
                </form>
            );
        }
    });

    return LoginPage;
});
