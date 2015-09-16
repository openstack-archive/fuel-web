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
    'tests/functional/pages/common',
    'tests/functional/pages/modal'
], function(registerSuite, assert, Common, ModalWindow) {
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
                    .then(function() {
                        return common.assertElementExists('.documentation-link', 'Fuel Documentation block is present');
                    })
                    .then(function() {
                        return common.assertElementExists('.snapshot', 'Diagnostic Snapshot block is present');
                    })
                    .then(function() {
                        return common.assertElementExists('.capacity-audit', 'Capacity Audit block is present');
                    })
                    .then(function() {
                        return common.assertElementExists('.tracking', 'Statistics block is present');
                    })
                    .findByCssSelector(sendStatisticsCheckbox)
                        .isSelected().then(function(checked) {
                            assert.isTrue(checked, 'Save Staticstics checkbox is checked');
                        })
                        .end()
                    .then(function() {
                        return common.assertElementDisabled(saveStatisticsSettingsButton, '"Save changes" button is disabled until statistics checkbox uncheck');
                    });
            },
            'Diagnostic snapshot link generation': function() {
                return this.remote
                    .clickByCssSelector('.snapshot .btn')
                    .waitForCssSelector('.snapshot .ready', 5000);
            },
            'Usage statistics option saving': function() {
                return this.remote
                    // Uncheck "Send usage statistics" checkbox
                    .clickByCssSelector(sendStatisticsCheckbox)
                    .then(function() {
                        return common.assertElementEnabled(saveStatisticsSettingsButton, '"Save changes" button is enabled after changing "Send usage statistics" checkbox value');
                    })
                    .clickByCssSelector(saveStatisticsSettingsButton)
                    // Button "Save changes" becomes disabled after saving the changes
                    .then(function() {
                        return common.assertElementDisabled(saveStatisticsSettingsButton, '"Save changes" button is disabled after saving changes');
                    });
            },
            'Discard changes': function() {
                return this.remote
                    // Check the "Send usage statistics" checkbox
                    .clickByCssSelector(sendStatisticsCheckbox)
                    .then(function() {
                        return common.assertElementEnabled(saveStatisticsSettingsButton, '"Save changes" button is enabled');
                    })
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
                    // Redirecting to Environments
                    .waitForCssSelector('.clusters-page', 1000)
                    // Go back to Support Page and ...
                    .clickLinkByText('Support')
                    // check if changes saved successfully
                    .findByCssSelector(sendStatisticsCheckbox)
                        .isSelected().then(function(checked) {
                            assert.isTrue(checked, 'Save Staticstics checkbox is checked');
                        })
                        .end()
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
                    // Redirecting to Environments
                    .waitForCssSelector('.clusters-page', 1000)
                    // Go back to Support Page and ...
                    .clickLinkByText('Support')
                    // check if changes was not saved and checkbox is still checked
                    .findByCssSelector(sendStatisticsCheckbox)
                        .isSelected().then(function(checked) {
                            assert.isTrue(checked, 'Save Staticstics checkbox is checked');
                        })
                        .end()
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
                    // We are still on the Support page, and checkbox is unchecked
                    .findByCssSelector(sendStatisticsCheckbox)
                        .isSelected().then(function(checked) {
                            assert.isFalse(checked, 'Save Staticstics checkbox is unchecked');
                        })
                        .end();
            }
        };
    });
});
