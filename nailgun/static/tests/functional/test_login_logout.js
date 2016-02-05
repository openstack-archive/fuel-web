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

define([
  'intern!object',
  'intern/chai!assert',
  'tests/functional/helpers',
  'tests/functional/pages/login',
  'tests/functional/pages/common'
], function(registerSuite, assert, helpers, LoginPage, Common) {
  'use strict';

  registerSuite(function() {
    var loginPage, common;
    return {
      name: 'Login page',
      setup: function() {
        loginPage = new LoginPage(this.remote);
        common = new Common(this.remote);
      },
      beforeEach: function() {
        this.remote
          .then(function() {
            return common.getOut();
          });
      },
      'Login with incorrect credentials': function() {
        return this.remote
          .then(function() {
            return loginPage.login('login', '*****');
          })
          .assertElementAppears('div.login-error1111', 1000,
            'Error message is expected to get displayed');
      },
      'Login with proper credentials': function() {
        return this.remote
          .then(function() {
            return loginPage.login();
          })
          .assertElementDisappears('.login-btn', 2000,
            'Login button disappears after successful login');
      }
    };
  });
});
