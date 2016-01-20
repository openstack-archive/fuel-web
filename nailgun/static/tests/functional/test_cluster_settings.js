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
  'intern!object',
  'intern/chai!assert',
  'tests/functional/helpers',
  'tests/functional/pages/common',
  'tests/functional/pages/cluster',
  'tests/functional/pages/settings',
  'tests/functional/pages/modal'
], function(registerSuite, assert, helpers, Common, ClusterPage, SettingsPage, ModalWindow) {
  'use strict';

  registerSuite(function() {
    var common,
      clusterPage,
      settingsPage,
      modal,
      clusterName;

    return {
      name: 'Settings tab',
      setup: function() {
        common = new Common(this.remote);
        clusterPage = new ClusterPage(this.remote);
        settingsPage = new SettingsPage(this.remote);
        modal = new ModalWindow(this.remote);
        clusterName = common.pickRandomName('Test Cluster');

        return this.remote
          .then(function() {
            return common.getIn();
          })
          .then(function() {
            return common.createCluster(clusterName);
          })
          .then(function() {
            return clusterPage.goToTab('Settings');
          })
          // go to Storage subtab to use checkboxes for tests
          .clickLinkByText('Storage');
      },
      'Settings tab is rendered correctly': function() {
        return this.remote
          .assertElementNotExists('.nav .subtab-link-network',
            'Subtab for Network settings is not presented in navigation')
          .assertElementEnabled('.btn-load-defaults', 'Load defaults button is enabled')
          .assertElementDisabled('.btn-revert-changes', 'Cancel Changes button is disabled')
          .assertElementDisabled('.btn-apply-changes', 'Save Settings button is disabled');
      },
      'Check Save Settings button': function() {
        return this.remote
          // introduce change
          .clickByCssSelector('input[type=checkbox]')
          .assertElementAppears('.btn-apply-changes:not(:disabled)', 200,
            'Save Settings button is enabled if there are changes')
          // reset the change
          .clickByCssSelector('input[type=checkbox]')
          .assertElementAppears('.btn-apply-changes:disabled', 200,
            'Save Settings button is disabled if there are no changes');
      },
      'Check Cancel Changes button': function() {
        return this.remote
          // introduce change
          .clickByCssSelector('input[type=checkbox]')
          .waitForCssSelector('.btn-apply-changes:not(:disabled)', 200)
          // try to move out of Settings tab
          .clickLinkByText('Dashboard')
          .then(function() {
            // check Discard Chasnges dialog appears
            return modal.waitToOpen();
          })
          .then(function() {
            return modal.close();
          })
          // reset changes
          .clickByCssSelector('.btn-revert-changes')
          .assertElementDisabled('.btn-apply-changes',
            'Save Settings button is disabled after changes were cancelled');
      },
      'Check changes saving': function() {
        return this.remote
          // introduce change
          .clickByCssSelector('input[type=checkbox]')
          .waitForCssSelector('.btn-apply-changes:not(:disabled)', 200)
          .clickByCssSelector('.btn-apply-changes')
          .then(function() {
            return settingsPage.waitForRequestCompleted();
          })
          .assertElementDisabled('.btn-revert-changes',
            'Cancel Changes button is disabled after changes were saved successfully');
      },
      'Check loading of defaults': function() {
        return this.remote
          // load defaults
          .clickByCssSelector('.btn-load-defaults')
          .then(function() {
            return settingsPage.waitForRequestCompleted();
          })
          .assertElementEnabled('.btn-apply-changes',
            'Save Settings button is enabled after defaults were loaded')
          .assertElementEnabled('.btn-revert-changes',
            'Cancel Changes button is enabled after defaults were loaded')
          // revert the change
          .clickByCssSelector('.btn-revert-changes');
      },
      'The choice of subgroup is preserved when user navigates through the cluster tabs':
      function() {
        return this.remote
          .clickLinkByText('Logging')
          .then(function() {
            return clusterPage.goToTab('Dashboard');
          })
          .then(function() {
            return clusterPage.goToTab('Settings');
          })
          .assertElementExists('.nav-pills li.active a.subtab-link-logging',
          'The choice of subgroup is preserved when user navigates through the cluster tabs');
      },
      'The page reacts on invalid input': function() {
        return this.remote
          .clickLinkByText('General')
          // "nova" is forbidden username
          .setInputValue('[type=text][name=user]', 'nova')
          .assertElementAppears('.setting-section .form-group.has-error', 200,
            'Invalid field marked as error')
          .assertElementExists('.settings-tab .nav-pills > li.active i.glyphicon-danger-sign',
            'Subgroup with invalid field marked as invalid')
          .assertElementDisabled('.btn-apply-changes',
            'Save Settings button is disabled in case of validation error')
          // revert the change
          .clickByCssSelector('.btn-revert-changes')
          .assertElementNotExists('.setting-section .form-group.has-error',
            'Validation error is cleared after resetting changes')
          .assertElementNotExists('.settings-tab .nav-pills > li.active i.glyphicon-danger-sign',
            'Subgroup menu has default layout after resetting changes');
      },
      'Test repositories custom control': function() {
        var repoAmount;
        var self = this;
        return this.remote
          .clickLinkByText('General')
          // get amount of default repositories
          .findAllByCssSelector('.repos .form-inline')
            .then(function(elements) {
              repoAmount = elements.length;
            })
            .end()
          .assertElementNotExists('.repos .form-inline:nth-of-type(1) .btn-link',
            'The first repo can not be deleted')
          // delete some repo
          .clickByCssSelector('.repos .form-inline .btn-link')
          .then(function() {
            return self.remote.assertElementsExist('.repos .form-inline', repoAmount - 1,
              'Repo was deleted');
          })
          // add new repo
          .clickByCssSelector('.btn-add-repo')
          .then(function() {
            return self.remote.assertElementsExist('.repos .form-inline', repoAmount,
              'New repo placeholder was added');
          })
          .assertElementExists('.repos .form-inline .repo-name.has-error',
            'Empty repo marked as invalid')
          // revert the change
          .clickByCssSelector('.btn-revert-changes');
      }
    };
  });
});
