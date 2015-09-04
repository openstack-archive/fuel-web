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
    'tests/register_suite',
    'intern/chai!assert',
    'tests/functional/pages/modal',
    'tests/functional/pages/common'
], function(_, registerSuite, assert, ModalWindow, Common) {
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
                    .setFindTimeout(2000)
                    .findByCssSelector('label.standard')
                        // Standard mode chosen
                        .click()
                        .end()
                    .findByClassName('node-box')
                        .click()
                        // Node gets selected upon clicking
                        .findByCssSelector('.checkbox-group input[type=checkbox]:checked')
                            .end()
                        .end()
                    .findByCssSelector('button.btn-delete-nodes')
                        // Delete and
                        .end()
                    .findByCssSelector('button.btn-edit-roles')
                        // ... Edit Roles buttons appear upon node selection
                        .end()
                    .findByCssSelector('.node.selected')
                        .findByCssSelector('.name p')
                            .click()
                            .end()
                        .findByCssSelector('input.node-name-input')
                            // Node name gets editable upon clicking on it
                            .clearValue()
                            .type(nodeNewName)
                            .pressKeys('\uE007')
                            .end()
                        .findByCssSelector('.name p')
                            .getVisibleText()
                            .then(function(nodeName) {
                                assert.equal(nodeName, nodeNewName, 'Node name has been updated');
                            })
                            .end()
                        .end()
                    .findByCssSelector('div.node-settings')
                        .click()
                        .end()
                    .then(function() {
                        return modal.waitToOpen();
                    })
                    .findByCssSelector('.modal-header h4.modal-title')
                        .getVisibleText()
                        .then(function(nodeName) {
                            assert.equal(nodeName, nodeNewName, 'Node pop-up has updated node name');
                        })
                        .end()
                    .then(function() {
                        return modal.close();
                    })
                    .then(function() {
                        return modal.waitToClose();
                    });
            },
            'Compact View Mode': function() {
                return this.remote
                    .setFindTimeout(2000)
                    .findByCssSelector('label.compact')
                        // Standard mode chosen by default
                        .click()
                        .end()
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
                    .setFindTimeout(2000)
                    .findByCssSelector('label.compact')
                        // Standard mode chosen by default
                        .click()
                        .end()
                    .findByCssSelector('div.compact-node')
                        // Find a node
                        .findByCssSelector('div.node-hardware p.btn')
                            // Hardware pop-over
                            .click()
                            .end()
                        .end()
                    .findByCssSelector('div.node-popover')
                        .findByCssSelector('button.node-details')
                            // Open node extended view
                            .click()
                            .end()
                        .end()
                    .then(function() {
                        return common.waitForElementDeletion('div.node-popover');
                    })
                    .then(function() {
                        return modal.waitToOpen();
                    })
                    .then(function() {
                        return modal.close();
                    })
                    .then(function() {
                        return modal.waitToClose();
                    })
                    .findByCssSelector('div.compact-node div.node-hardware p.btn')
                        // Open popover again
                        .click()
                        .end()
                    .findByCssSelector('div.node-popover button.btn-discard')
                        // Discarding node addition
                        .click()
                        .end()
                    .then(function() {
                        // Deletion confirmation shows up
                        return modal.waitToOpen();
                    })
                    .findByCssSelector('div.modal-content button.btn-delete')
                        // Confirm deletion
                        .click()
                        .end()
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
