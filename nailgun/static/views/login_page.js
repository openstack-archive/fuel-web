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

import $ from 'jquery';
import i18n from 'i18n';
import React from 'react';
import ReactDOM from 'react-dom';
import utils from 'utils';
import dispatcher from 'dispatcher';

var LoginPage = React.createClass({
  statics: {
    title: i18n('login_page.title'),
    hiddenLayout: true
  },
  render() {
    return (
      <div className='login-page'>
        <div className='container col-md-4 col-md-offset-4 col-xs-10 col-xs-offset-1'>
          <div className='box'>
            <div className='login-head' />
            <div className='logo' />
            <div className='fields-box'>
              <LoginForm />
            </div>
          </div>
        </div>
        <div className='footer col-xs-12'>
          <p className='text-center'>{i18n('common.version')}: {app.version.get('release')}</p>
        </div>
      </div>
    );
  }
});

var LoginForm = React.createClass({
  login(username, password) {
    var keystoneClient = app.keystoneClient;

    return keystoneClient.authenticate(username, password, {force: true})
      .fail((xhr) => {
        $(ReactDOM.findDOMNode(this.refs.username)).focus();

        var status = xhr && xhr.status;
        var error = 'login_error';
        if (status === 401) {
          error = 'credentials_error';
        // no status (connection refused) or 5xx error
        } else if (!status || String(status)[0] === '5') {
          error = 'keystone_unavailable_error';
        }
        this.setState({error: i18n('login_page.' + error)});
      })
      .then(() => {
        app.user.set({
          authenticated: true,
          username: username,
          token: keystoneClient.token
        });

        if (password === keystoneClient.DEFAULT_PASSWORD) {
          dispatcher.trigger('showDefaultPasswordWarning');
        }

        return app.fuelSettings.fetch({cache: true});
      })
      .then(() => {
        var nextUrl = '';
        if (app.router.returnUrl) {
          nextUrl = app.router.returnUrl;
          delete app.router.returnUrl;
        }
        app.navigate(nextUrl, {trigger: true});
      });
  },
  componentDidMount() {
    $(ReactDOM.findDOMNode(this.refs.username)).focus();
  },
  getInitialState() {
    return {
      actionInProgress: false,
      error: null
    };
  },
  onChange() {
    this.setState({error: null});
  },
  onSubmit(e) {
    e.preventDefault();

    var username = ReactDOM.findDOMNode(this.refs.username).value;
    var password = ReactDOM.findDOMNode(this.refs.password).value;

    this.setState({actionInProgress: true});

    this.login(username, password)
      .fail(() => {
        this.setState({actionInProgress: false});
      });
  },
  render() {
    var httpsUsed = location.protocol === 'https:';
    var httpsPort = 8443;
    var httpsLink = 'https://' + location.hostname + ':' + httpsPort;

    return (
      <form className='form-horizontal' onSubmit={this.onSubmit}>
        <div className='form-group'>
          <label className='control-label col-xs-2'>
            <i className='glyphicon glyphicon-user'></i>
          </label>
          <div className='col-xs-8'>
            <input
              className='form-control input-sm'
              type='text'
              name='username'
              ref='username'
              placeholder={i18n('login_page.username')}
              onChange={this.onChange}
            />
          </div>
        </div>
        <div className='form-group'>
          <label className='control-label col-xs-2'>
            <i className='glyphicon glyphicon-lock'></i>
          </label>
          <div className='col-xs-8'>
            <input
              className='form-control input-sm'
              type='password'
              name='password'
              ref='password'
              placeholder={i18n('login_page.password')}
              onChange={this.onChange}
            />
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
        {this.state.error &&
          <div className='login-error'>{this.state.error}</div>
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

export default LoginPage;
