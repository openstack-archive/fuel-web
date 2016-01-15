/*
 * Copyright 2015 Mirantis, Inc.
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
  'tests/functional/helpers'
], function() {
  'use strict';

  function SettingsPage(remote) {
    this.remote = remote;
  }

  SettingsPage.prototype = {
    constructor: SettingsPage,
    waitForRequestCompleted: function() {
      return this.remote
        // Load Defaults button is locked during any request is in progress on the tab
        // so this is a hacky way to track request state
        .waitForElementDeletion('.btn-load-defaults:disabled', 2000);
    }
  };
  return SettingsPage;
});
