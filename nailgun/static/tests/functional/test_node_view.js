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
    'tests/functional/pages/node',
    'tests/functional/pages/modal',
    'tests/functional/pages/common',
    'tests/functional/pages/cluster'
], function(_, registerSuite, assert, NodeComponent, ModalWindow, Common, ClusterPage) {
    'use strict';

    registerSuite(function() {
        var common,
            node,
            modal,
            clusterPage,
            clusterName,
            nodesAmount = 3,
            nodeNewName = 'Node new name';

        return {
            name: 'Node view tests',
            setup: function() {
                common = new Common(this.remote);
                node = new NodeComponent(this.remote);
                modal = new ModalWindow(this.remote);
                clusterPage = new ClusterPage(this.remote);
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
            'Standard node panel': function() {
                return this.remote
                    .findByCssSelector('label.standard')
                        // Standard mode chosen by default
                        .end()
                    .findByClassName('node-box')
                        // role list is shown on node standard panel
                        .findByCssSelector('.role-list')
                            .end()
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
                    .then(function() {
                        return node.renameNode(nodeNewName);
                    })
                    .findByCssSelector('.node .name p')
                        .getVisibleText()
                        .then(function(nodeName) {
                            assert.equal(nodeName, nodeNewName, 'Node name has been updated');
                        })
                        .end()
                    // click node View Logs button
                    .findByCssSelector('.node .btn-view-logs')
                        .click()
                        .end()
                    // check redirect to Logs tab
                    .findByCssSelectorWithTimeout('.logs-tab', 3000)
                    .then(function() {
                        return clusterPage.goToTab('Nodes');
                    })
                    .then(function() {
                        return node.discardNode();
                    })
                    .findAllByCssSelector('.node')
                        .then(function(nodes) {
                            assert.equal(nodes.length, nodesAmount - 1, 'Node has been removed');
                        });
            },
            'Node pop-up': function() {
                var newHostname = 'node-123';
                return this.remote
                    .then(function() {
                        return node.openNodePopup();
                    })
                    .findByCssSelector('.modal-header h4.modal-title')
                        .getVisibleText()
                        .then(function(nodeName) {
                            assert.equal(nodeName, nodeNewName, 'Node pop-up has updated node name');
                        })
                        .end()
                    // disks can be configured for cluster node
                    .findByCssSelector('.modal .btn-edit-disks')
                        .end()
                    // interfaces can be configured for cluster node
                    .findByCssSelector('.modal .btn-edit-networks')
                        .end()
                    // click Edit Hostname button
                    .findByCssSelector('.change-hostname .btn-link')
                        .click()
                        .end()
                    // change the hostname
                    .findByCssSelector('.change-hostname [type=text]')
                        .clearValue()
                        .type(newHostname)
                        .pressKeys('\uE007')
                        .end()
                    .findByCssSelector('span.node-hostname')
                        .getVisibleText()
                        .then(function(hostname) {
                            assert.equal(hostname, newHostname, 'Node hostname has been updated');
                        })
                        .end()
                    .then(function() {
                        return modal.close();
                    });
            },
            'Compact node panel': function() {
                return this.remote
                    .findByCssSelector('label.compact')
                        // Switch to compact view mode
                        .click()
                        .end()
                    .findByCssSelector('.compact-node')
                        //  click node name
                        .findByCssSelector('.node-name p')
                            .click()
                            .end()
                        .then(function() {
                            return common.elementNotExists('.compact-node .node-name-input', 'Node can not be renamed from its compact panel');
                        })
                        // role list is not shown on node compact panel
                        .findByCssSelector('.role-list')
                            .end()
                        .findByCssSelector('div.node-checkbox')
                            .click()
                            // Check self node is selectable
                            .findByCssSelector('i.glyphicon-ok')
                                .end()
                            .end();
            },
            'Compact node extended view': function() {
                var newName = 'Node new new name';
                return this.remote
                    .findByCssSelector('label.compact')
                        // Switch to compact view mode
                        .click()
                        .end()
                    .then(function() {
                        return node.openCompactNodeExtendedView();
                    })
                    // check node from extended view
                    .findByCssSelector('.node-name [type=checkbox]')
                        .click()
                        .end()
                    .then(function() {
                        return common.elementExists('.compact-node .node-checkbox i.glyphicon-ok', 'Node compact panel is checked');
                    })
                    .then(function() {
                        return node.openNodePopup(true);
                    })
                    .then(function() {
                        return common.elementNotExists('.node-popover', 'Node popover is closed when node pop-up opened');
                    })
                    .then(function() {
                        // close node pop-up
                        return modal.close();
                    })
                    .then(function() {
                        return node.openCompactNodeExtendedView();
                    })
                    .findByCssSelector('.node-popover')
                        // role list is shown in cluster node extended view
                        .findByCssSelector('.role-list')
                            .end()
                        // cluster node action buttons are presented in extended view
                        .findByCssSelector('.node-buttons')
                            .end()
                        .end()
                    .then(function() {
                        return node.renameNode(newName);
                    })
                    .findByCssSelector('.node-popover .name p')
                        .getVisibleText()
                        .then(function(nodeName) {
                            assert.equal(nodeName, newName, 'Node name has been updated from extended view');
                        })
                        .end()
                    .then(function() {
                        return node.discardNode(true);
                    })
                    .findAllByCssSelector('.node')
                        .then(function(nodes) {
                            assert.equal(nodes.length, nodesAmount - 2, 'Node has been removed');
                        });
            },
            'Additional tests for unallocated node': function() {
                return this.remote
                    // go to Add Nodes screen
                    .findByCssSelector('button.btn-add-nodes')
                        .click()
                        .end()
                    // wait for Add Nodes screen opened
                    .findByCssSelectorWithTimeout('.role-panel')
                    .then(function() {
                        return node.openCompactNodeExtendedView();
                    })
                    .then(function() {
                        return common.elementNotExists('.node-popover .role-list', 'Unallocated node does not have roles assigned');
                    })
                    .then(function() {
                        return common.elementNotExists('.node-popover .node-buttons', 'There are no action buttons in unallocated node extended view');
                    })
                    .then(function() {
                        return node.openNodePopup(true);
                    })
                    .then(function() {
                        return common.elementNotExists('.modal .btn-edit-disks', 'Disks can not be configured for unallocated node');
                    })
                    .then(function() {
                        return common.elementNotExists('.modal .btn-edit-networks', 'Interfaces can not be configured for unallocated node');
                    });
            }
        };
    });
});
