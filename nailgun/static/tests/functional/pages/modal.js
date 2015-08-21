define([
    'intern/chai!assert'
],
    function(assert) {
    'use strict';
        function ModalWindow(remote) {
            this.remote = remote;
        }

        ModalWindow.prototype = {
            constructor: ModalWindow,
            waitToOpen: function() {
                return this.remote
                    .setFindTimeout(2000)
                    .findByCssSelector('div.modal-content')
                        .end();
            },
            checkTitle: function(expectedTitle) {
                return this.remote
                    .findByCssSelector('h4.modal-title')
                        .getVisibleText()
                        .then(function(title) {
                            assert.equal(title, expectedTitle, 'Unexpected modal window title');
                        })
                        .end();
            },
            close: function() {
                return this.remote
                    .findByCssSelector('.modal-header button.close')
                        .click()
                        .end();
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
                var CommonPage = require('tests/functional/pages/common'),
                    common = new CommonPage(this.remote);

                return common.waitForElementDeletion('div.modal-content');
            }
        };
        return ModalWindow;
    }
);
