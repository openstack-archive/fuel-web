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
    'underscore',
    'intern!object',
    'intern/chai!assert',
    'tests/helpers',
    'tests/functional/pages/modal',
    'tests/functional/pages/common'
], function(_, registerSuite, assert, helpers, ModalWindow, Common) {
    'use strict';

    registerSuite(function() {
        var common,
            modal,
            clusterName,
            nodesAmount = 4;

        return {
            name: 'Cluster Nodes page',
            setup: function() {
                common = new Common(this.remote);
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
                        return common.addNodesToCluster(nodesAmount, ['Controller']);
                    });
            },
            teardown: function() {
                return this.remote
                    .then(function() {
                        return common.removeCluster(clusterName);
                    });
            },
            afterEach: function() {
                // Deselecting all nodes after every test
                return this.remote
                    .findByCssSelector('.select-all label')
                        .click()
                        .click()
                        .end();
            },
            'Standard View Mode': function() {
                var nodeNewName = 'Node new name';
                return this.remote
                    // Standard mode chosen by default
                    .findByCssSelector('label.standard.active')
                        .end()
                    .findByClassName('node-box')
                        .click()
                        // Node gets selected upon clicking
                        .findByCssSelector('.checkbox-group input[type=checkbox]:checked')
                            .end()
                        .end()
                    // Delete and
                    .findByCssSelector('button.btn-delete-nodes')
                        .end()
                    // ... Edit Roles buttons appear upon node selection
                    .findByCssSelector('button.btn-edit-roles')
                        .end()
                    .findByCssSelector('.node.selected')
                        .clickByCssSelector('.name p')
                        .findByCssSelector('input.node-name-input')
                            // Node name gets editable upon clicking on it
                            .clearValue()
                            .type(nodeNewName)
                            .pressKeys('\uE007')
                            .end()
                        .end()
                    .waitForCssSelector('.node.selected .name p', 500)
                    .then(function() {
                        return common.assertElementContainsText('.node.selected .name p', nodeNewName, 'Node name has been updated');
                    })
                    .clickByCssSelector('div.node-settings')
                    .then(function() {
                        return modal.waitToOpen();
                    })
                    .then(function() {
                        return common.assertElementContainsText('.modal-header h4.modal-title', nodeNewName, 'Node pop-up has updated node name');
                    })
                    .then(function() {
                        return modal.close();
                    });
            },
            'Compact View Mode': function() {
                return this.remote
                    .clickByCssSelector('label.compact')
                    .findByCssSelector('div.compact-node')
                        // Find a node
                        .findByCssSelector('div.node-checkbox')
                            .click()
                            .findByCssSelector('i.glyphicon-ok')
                                // Check self node is selectable
                                .end()
                            .end();
            },
            'Compact View Node Popover': function() {
                return this.remote
                    // Open node extended view
                    .clickByCssSelector('div.compact-node div.node-hardware p.btn')
                    // Open node pop-up
                    .clickByCssSelector('div.node-popover button.node-details')
                    .waitForElementDeletion('div.node-popover', 0)
                    .then(function() {
                        return modal.waitToOpen();
                    })
                    .then(function() {
                        return modal.close();
                    })
                    // open node extended view
                    .clickByCssSelector('div.compact-node div.node-hardware p.btn')
                    // discard node addition
                    .clickByCssSelector('div.node-popover button.btn-discard')
                    .then(function() {
                        // Deletion confirmation shows up
                        return modal.waitToOpen();
                    })
                    // Confirm deletion
                    .clickByCssSelector('div.modal-content button.btn-delete')
                    .then(function() {
                        return modal.waitToClose();
                    })
                    .findAllByCssSelector('div.compact-node')
                    .then(function(nodes) {
                        // Count nodes left
                        assert.equal(nodes.length, nodesAmount - 1, 'Node has been removed');
                    });
            }
        };
    });
});
