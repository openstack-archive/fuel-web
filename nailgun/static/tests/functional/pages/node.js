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
    'tests/functional/pages/modal',
    'tests/functional/helpers'
], function(ModalWindow) {
    'use strict';

    function NodeComponent(remote) {
        this.remote = remote;
        this.modal = new ModalWindow(this.remote);
    }

    NodeComponent.prototype = {
        constructor: NodeComponent,
        openCompactNodeExtendedView: function() {
            var self = this;
            return this.remote
                .findByCssSelector('div.compact-node .node-hardware p:not(.btn)')
                    .then(function(element) {
                        return self.remote.moveMouseTo(element);
                    })
                    .end()
                // the following timeout as we have 0.3s transition for the button
                .sleep(500)
                .clickByCssSelector('div.compact-node .node-hardware p.btn')
                .waitForCssSelector('.node-popover', 1000);
        },
        openNodePopup: function(fromExtendedView) {
            var self = this,
                cssSelector = fromExtendedView ? '.node-popover' : '.node';
            return this.remote
                .findByCssSelector(cssSelector)
                    .clickByCssSelector('.node-settings')
                    .end()
                .then(function() {
                    return self.modal.waitToOpen();
                });
        },
        discardNode: function(fromExtendedView) {
            var self = this,
                cssSelector = fromExtendedView ? '.node-popover' : '.node';
            return this.remote
                .findByCssSelector(cssSelector)
                    .clickByCssSelector('.btn-discard')
                    .end()
                .then(function() {
                    // deletion confirmation shows up
                    return self.modal.waitToOpen();
                })
                // confirm deletion
                .clickByCssSelector('div.modal-content button.btn-delete')
                .then(function() {
                    return self.modal.waitToClose();
                });
        },
        renameNode: function(newName, fromExtendedView) {
            var cssSelector = fromExtendedView ? '.node-popover' : '.node';
            return this.remote
                .findByCssSelector(cssSelector)
                    .clickByCssSelector('.name p')
                    .findByCssSelector('input.node-name-input')
                        // node name gets editable upon clicking on it
                        .clearValue()
                        .type(newName)
                        .pressKeys('\uE007')
                        .end()
                    .waitForCssSelector('.name p', 1000)
                    .end();
        }
    };
    return NodeComponent;
});
