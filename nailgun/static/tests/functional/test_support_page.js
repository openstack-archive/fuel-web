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
  'tests/functional/pages/common',
  'tests/functional/pages/modal'
], function(registerSuite, Common, ModalWindow) {
  'use strict';

  registerSuite(function() {
    var common,
      modal,
      saveStatisticsSettingsButton, sendStatisticsCheckbox;

    return {
      name: 'Support Page',
      setup: function() {
        common = new Common(this.remote);
        modal = new ModalWindow(this.remote);
        saveStatisticsSettingsButton = '.tracking .btn';
        sendStatisticsCheckbox = '.tracking input[name=send_anonymous_statistic]';

        return this.remote
          .then(function() {
            return common.getIn();
          })
          // Go to Support page
          .clickLinkByText('Support');
      },
      'Support page is rendered correctly': function() {
        return this.remote
          .assertElementExists('.documentation-link', 'Fuel Documentation block is present')
          .assertElementExists('.snapshot', 'Diagnostic Snapshot block is present')
          .assertElementExists('.capacity-audit', 'Capacity Audit block is present')
          .assertElementExists('.tracking', 'Statistics block is present')
          .assertElementSelected(sendStatisticsCheckbox, 'Save Staticstics checkbox is checked')
          .assertElementDisabled(saveStatisticsSettingsButton,
            '"Save changes" button is disabled until statistics checkbox uncheck');
      },
      'Diagnostic snapshot link generation': function() {
        return this.remote
          .clickByCssSelector('.snapshot .btn')
          .assertElementAppears('.snapshot .ready', 5000, 'Diagnostic snapshot link is shown');
      },
      'Usage statistics option saving': function() {
        return this.remote
          // Uncheck "Send usage statistics" checkbox
          .clickByCssSelector(sendStatisticsCheckbox)
          .assertElementEnabled(saveStatisticsSettingsButton,
            '"Save changes" button is enabled after changing "Send usage statistics" ' +
            'checkbox value')
          .clickByCssSelector(saveStatisticsSettingsButton)
          .assertElementDisabled(saveStatisticsSettingsButton,
            '"Save changes" button is disabled after saving changes');
      },
      'Discard changes': function() {
        return this.remote
          // Check the "Send usage statistics" checkbox
          .clickByCssSelector(sendStatisticsCheckbox)
          .assertElementEnabled(saveStatisticsSettingsButton, '"Save changes" button is enabled')
          // Go to another page with not saved changes
          .clickLinkByText('Environments')
          .then(function() {
            return modal.waitToOpen();
          })
          .then(function() {
            // Check if Discard Changes dialog is open
            return modal.checkTitle('Confirm');
          })
          .then(function() {
            // Save the changes
            return modal.clickFooterButton('Save and Proceed');
          })
          .then(function() {
            return modal.waitToClose();
          })
          .assertElementAppears('.clusters-page', 1000, 'Redirecting to Environments')
          // Go back to Support Page and ...
          .clickLinkByText('Support')
          .assertElementSelected(sendStatisticsCheckbox,
            'Changes saved successfully and save staticstics checkbox is checked')
          // Uncheck the "Send usage statistics" checkbox value
          .clickByCssSelector(sendStatisticsCheckbox)
          // Go to another page with not saved changes
          .clickLinkByText('Environments')
          .then(function() {
            return modal.waitToOpen();
          })
          .then(function() {
            // Now Discard the changes
            return modal.clickFooterButton('Discard Changes');
          })
          .then(function() {
            return modal.waitToClose();
          })
          .assertElementAppears('.clusters-page', 1000, 'Redirecting to Environments')
          // Go back to Support Page and ...
          .clickLinkByText('Support')
          .assertElementSelected(sendStatisticsCheckbox,
            'Changes was not saved and save staticstics checkbox is checked')
          // Uncheck the "Send usage statistics" checkbox value
          .clickByCssSelector(sendStatisticsCheckbox)
          // Go to another page with not saved changes
          .clickLinkByText('Environments')
          .then(function() {
            return modal.waitToOpen();
          })
          .then(function() {
            // Click Cancel Button
            return modal.clickFooterButton('Cancel');
          })
          .then(function() {
            return modal.waitToClose();
          })
          .assertElementNotSelected(sendStatisticsCheckbox,
            'We are still on the Support page, and checkbox is unchecked');
      }
    };
  });
});
