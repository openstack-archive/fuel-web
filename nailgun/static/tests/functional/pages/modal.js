define([
    'underscore',
    'intern/chai!assert',
    'tests/functional/pages/common',
    '../../helpers'
],
    function(_, assert, Common, Helpers) {
    'use strict';
        function ModalWindow(remote) {
            this.remote = remote;
            this.common = new Common(remote);
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
            },
            close: function() {
                return this.remote
                    .findByCssSelector('.modal-header button.close')
                        .click()
                        .end();
            },
            clickFooterButton: function(buttonText) {
                this.remote
                    .findAllByCssSelector('.modal-footer button')
                    .then(function(buttons) {
                        return buttons.forEach(function(button) {
                            return button.getVisibleText()
                                .then(function(buttonTitle) {
                                    if (buttonTitle == buttonText) button.click().end();
                                });
                        });
                    });
            },
            waitToClose: function() {
                return this.common.waitForElementDeletion('div.modal-content');
            }
        };
        return ModalWindow;
    }
);
