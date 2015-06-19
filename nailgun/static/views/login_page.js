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
    'react',
    'dispatcher',
    'utils'
],
function($, _, i18n, React, dispatcher, utils) {
    'use strict';

    var LoginPage = React.createClass({
        statics: {
            title: i18n('login_page.title'),
            hiddenLayout: true
        },
        render: function() {
            return (
                <div className='login-page'>
                    <div className='login-box col-md-4 col-md-offset-4 col-xs-10 col-xs-offset-1'>
                        <div className='login-logo-circle'></div>
                        <div className='login-logo'></div>
                        <div className='login-fields-box'>
                            <LoginForm />
                        </div>
                    </div>
                    <div className='login-footer col-xs-12'>
                        {_.contains(app.version.get('feature_groups'), 'mirantis') &&
                            <p className='text-center'>{i18n('common.copyright')}</p>
                        }
                        <p className='text-center'>{i18n('common.version')}: {app.version.get('release')}</p>
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

                    if (password == keystoneClient.DEFAULT_PASSWORD) {
                        dispatcher.trigger('showDefaultPasswordWarning');
                    }

                    return app.settings.fetch({cache: true});
                }, this))
                .done(_.bind(function() {
                    var nextUrl = '';
                    if (app.router.returnUrl) {
                        nextUrl = app.router.returnUrl;
                        delete app.router.returnUrl;
                    }
                    app.navigate(nextUrl, {trigger: true});
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
            e.preventDefault();

            var username = this.refs.username.getDOMNode().value;
            var password = this.refs.password.getDOMNode().value;

            this.setState({actionInProgress: true});

            this.login(username, password)
                .fail(_.bind(function() {
                    this.setState({actionInProgress: false});
                }, this));
        },
        render: function() {
            var httpsUsed = location.protocol == 'https:';
            var httpsPort = 8443;
            var httpsLink = 'https://' + location.hostname + ':' + httpsPort;

            return (
                <form className='form-horizontal' onSubmit={this.onSubmit}>
                    <div className='form-group'>
                        <label className='control-label col-xs-2'>
                            <i className='glyphicon glyphicon-user'></i>
                        </label>
                        <div className='col-xs-8'>
                            <input className='form-control input-sm' type='text' name='username' ref='username' placeholder={i18n('login_page.username')} onChange={this.onChange} />
                        </div>
                    </div>
                    <div className='form-group'>
                        <label className='control-label col-xs-2'>
                            <i className='glyphicon glyphicon-lock'></i>
                        </label>
                        <div className='col-xs-8'>
                            <input className='form-control input-sm' type='password' name='password' ref='password' placeholder={i18n('login_page.password')} onChange={this.onChange} />
                        </div>
                    </div>
                    {!httpsUsed &&
                        <div className='http-warning'>
                            <i className='glyphicon glyphicon-warning-sign'></i>
                            {i18n('login_page.http_warning')}
                            <br/>
                            <a href={httpsLink}>{i18n('login_page.http_warning_link')}</a>
                        </div>
                    }
                    {this.state.hasError &&
                        <div className='login-error'>{i18n('login_page.login_error')}</div>
                    }
                    <div className='form-group'>
                        <div className='col-xs-12 text-center'>
                            <button
                                type='submit'
                                className={utils.classNames({
                                    'btn login-btn': true,
                                    'btn-success': httpsUsed,
                                    'btn-warning': !httpsUsed
                                })}
                                disabled={this.state.actionInProgress}
                            >
                                {i18n('login_page.log_in')}
                            </button>
                        </div>
                    </div>
                </form>
            );
        }
    });

    return LoginPage;
});
