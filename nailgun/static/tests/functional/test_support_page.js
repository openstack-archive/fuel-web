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
    'tests/helpers',
    'tests/functional/pages/common',
    'tests/functional/pages/modal'
], function(registerSuite, assert, helpers, Common, ModalWindow) {
    'use strict';

    registerSuite(function() {
        var common,
            modal;

        return {
            name: 'Support Page',
            setup: function() {
                common = new Common(this.remote);
                modal = new ModalWindow(this.remote);

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
                    .then(function() {
                        return common.assertElementExists('.tracking input[name=send_anonymous_statistic]:checked', 'Save Statistics checkbox is checked by default');
                    })
                    .then(function() {
                        return common.assertElementDisabled('.tracking .btn', '"Save changes" button is disabled until statistics checkbox uncheck');
                    });
            },
            'Diagnostic snapshot link generation': function() {
                return this.remote
                    .clickByCssSelector('.snapshot .btn')
                    .waitForCssSelector('.snapshot .ready', 5000)
            },
            'Usage statistics option saving': function() {
                return this.remote
                    // Uncheck "Send usage statistics" checkbox
                    .clickByCssSelector('.tracking input[name=send_anonymous_statistic]')
                    .then(function() {
                        return common.assertElementEnabled('.tracking .btn', '"Save changes" button is enabled after changing "Send usage statistics" checkbox value');
                    })
                    .clickByCssSelector('.tracking .btn')
                    // Button "Save changes" becomes disabled after saving the changes
                    .waitForCssSelector('.tracking .btn:disabled', 1000)
                    .then(function() {
                        return common.assertElementExists('.tracking input[name=send_anonymous_statistic]:not(:checked)', 'Save Statistics checkbox is unchecked');
                    })
            },
            'Discard changes': function() {
                return this.remote
                    // Check the "Send usage statistics" checkbox
                    .clickByCssSelector('.tracking input[name=send_anonymous_statistic]')
                    .then(function() {
                        return common.assertElementEnabled('.tracking .btn', '"Save changes" button is enabled');
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
                    .then(function() {
                        // check if changes saved successfully
                        return common.assertElementExists('.tracking input[name=send_anonymous_statistic]:checked', 'Save Statistics checkbox is checked');
                    })
                    // Uncheck the "Send usage statistics" checkbox value
                    .clickByCssSelector('.tracking input[name=send_anonymous_statistic]')
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
                    .then(function() {
                        // check if changes was not saved and checkbox is still checked
                        return common.assertElementExists('.tracking input[name=send_anonymous_statistic]:checked', 'Save Statistics checkbox is checked');
                    })
                    // Uncheck the "Send usage statistics" checkbox value
                    .clickByCssSelector('.tracking input[name=send_anonymous_statistic]')
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
                    .then(function() {
                        // We are still on the Support page, and checkbox is unchecked
                        return common.assertElementExists('.tracking input[name=send_anonymous_statistic]:not(:checked)', 'Save Statistics checkbox is unchecked');
                    });
            }
        };
    });
});
