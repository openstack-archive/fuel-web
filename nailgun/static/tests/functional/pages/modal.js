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
    '../../helpers'
], function() {
    'use strict';
        function ModalWindow(remote) {
            this.remote = remote;
        }

        ModalWindow.prototype = {
            constructor: ModalWindow,
            waitToOpen: function() {
                return this.remote
                    .waitForCssSelector('div.modal-content', 2000);
            },
            checkTitle: function(expectedTitle) {
                return this.remote
                    .assertElementContainsText('h4.modal-title', expectedTitle, 'Unexpected modal window title');
            },
            close: function() {
                var self = this;
                return this.remote
                    .clickByCssSelector('.modal-header button.close')
                    .then(function() {
                        return self.waitToClose();
                    });
            },
            clickFooterButton: function(buttonText) {
                return this.remote
                    .findAllByCssSelector('.modal-footer button')
                        .then(function(buttons) {
                            return buttons.reduce(function(result, button) {
                                return button.getVisibleText()
                                    .then(function(buttonTitle) {
                                        if (buttonTitle == buttonText)
                                            return button.isEnabled()
                                                .then(function(isEnabled) {
                                                    if (isEnabled) {
                                                        return button.click();
                                                    } else
                                                        throw Error('Unable to click disabled button "' + buttonText + '"');
                                                });
                                        return result;
                                    });
                            }, null);
                        });
            },
            waitToClose: function() {
                return this.remote
                    .waitForElementDeletion('div.modal-content', 5000);
            }
        };
        return ModalWindow;
    }
);
