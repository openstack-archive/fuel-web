/*
 * Copyright 2016 Mirantis, Inc.
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
  'intern/dojo/node!lodash',
  'tests/functional/pages/modal',
  'tests/functional/helpers'
], function(_, ModalWindow) {
  'use strict';

  function NetworkPage(remote) {
    this.remote = remote;
    this.modal = new ModalWindow(this.remote);
  }

  NetworkPage.prototype = {
    constructor: NetworkPage,
    addNodeNetworkGroup: function(name) {
      var self = this;
      return this.remote
        .clickByCssSelector('.add-nodegroup-btn')
        .then(function() {
          return self.modal.waitToOpen();
        })
        .setInputValue('[name=node-network-group-name]', name)
        .then(function() {
          return self.modal.clickFooterButton('Add Group');
        })
        .then(function() {
          return self.modal.waitToClose();
        })
        .findByLinkText(name);
    },
    renameNodeNetworkGroup: function(oldName, newName) {
      var self = this;
      return this.remote
        .then(function() {
          if (oldName) {
            return self.goToNodeNetworkGroup(oldName);
          }
        })
        .clickByCssSelector('.glyphicon-pencil')
        .waitForCssSelector('.network-group-name input[type=text]', 2000)
        .findByCssSelector('.node-group-renaming input[type=text]')
          .clearValue()
          .type(newName)
          // Enter
          .type('\uE007')
          .end()
        .findByLinkText(newName);
    },
    goToNodeNetworkGroup: function(name) {
      return this.remote
        // FIXME (morale): we need to add some verificatoon here that
        // switch to other node network group was successful
        .findByCssSelector('ul.node_network_groups')
          .clickLinkByText(name)
          .end();
    }
  };
  return NetworkPage;
});
