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
    'tests/functional/pages/node',
    'tests/functional/pages/modal',
    'tests/functional/pages/common',
    'tests/functional/pages/cluster',
    'tests/helpers'
], function(registerSuite, assert, NodeComponent, ModalWindow, Common, ClusterPage) {
    'use strict';

    registerSuite(function() {
        var common,
            node,
            modal,
            clusterPage,
            clusterName,
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
                    });
            },
            'Standard node panel': function() {
                return this.remote
                    .then(function() {
                        return common.addNodesToCluster(1, ['Controller']);
                    })
                    .findByCssSelector('label.standard.active')
                        // standard mode chosen by default
                        .end()
                    .findByClassName('node-box')
                        // role list is shown on node standard panel
                        .findByCssSelector('.role-list')
                            .end()
                        .click()
                        // node gets selected upon clicking
                        .findByCssSelector('.checkbox-group input[type=checkbox]:checked')
                            .end()
                        .end()
                    .findByCssSelector('button.btn-delete-nodes:not(:disabled)')
                        // Delete Nodes and
                        .end()
                    .findByCssSelector('button.btn-edit-roles:not(:disabled)')
                        // ... Edit Roles buttons appear upon node selection
                        .end()
                    .then(function() {
                        return node.renameNode(nodeNewName);
                    })
                    .then(function() {
                        return common.assertElementTextEqualTo('.node .name p', nodeNewName, 'Node name has been updated');
                    })
                    .clickByCssSelector('.node .btn-view-logs')
                    // check redirect to Logs tab
                    .waitForCssSelector('.logs-tab', 2000)
                    .then(function() {
                        return clusterPage.goToTab('Nodes');
                    })
                    .waitForCssSelector('.node-list', 2000)
                    .then(function() {
                        return node.discardNode();
                    })
                    .then(function() {
                        return common.assertElementNotExists('.node', 'Node has been removed');
                    });
            },
            'Node pop-up': function() {
                var newHostname = 'node-123';
                return this.remote
                    .then(function() {
                        return common.addNodesToCluster(1, ['Controller']);
                    })
                    .then(function() {
                        return node.openNodePopup();
                    })
                    .then(function() {
                        return common.assertElementTextEqualTo('.modal-header h4.modal-title', nodeNewName, 'Node pop-up has updated node name');
                    })
                    // disks can be configured for cluster node
                    .findByCssSelector('.modal .btn-edit-disks')
                        .end()
                    // interfaces can be configured for cluster node
                    .findByCssSelector('.modal .btn-edit-networks')
                        .end()
                    .clickByCssSelector('.change-hostname .btn-link')
                    // change the hostname
                    .findByCssSelector('.change-hostname [type=text]')
                        .clearValue()
                        .type(newHostname)
                        .pressKeys('\uE007')
                        .end()
                    .then(function() {
                        return common.assertElementTextEqualTo('span.node-hostname', newHostname, 'Node hostname has been updated');
                    })
                    .then(function() {
                        return modal.close();
                    });
            },
            'Compact node panel': function() {
                return this.remote
                    // switch to compact view mode
                    .clickByCssSelector('label.compact')
                    .findByCssSelector('.compact-node div.node-checkbox')
                        .click()
                        // check self node is selectable
                        .findByCssSelector('i.glyphicon-ok')
                            .end()
                        .end()
                    .clickByCssSelector('.compact-node .node-name p')
                    .then(function() {
                        return common.assertElementNotExists('.compact-node .node-name-input', 'Node can not be renamed from compact panel');
                    })
                    .then(function() {
                        return common.assertElementNotExists('.compact-node .role-list', 'Role list is not shown on node compact panel');
                    });
            },
            'Compact node extended view': function() {
                var newName = 'Node new new name';
                return this.remote
                    .then(function() {
                        return node.openCompactNodeExtendedView();
                    })
                    .clickByCssSelector('.node-name [type=checkbox]')
                    .then(function() {
                        return common.assertElementExists('.compact-node .node-checkbox i.glyphicon-ok', 'Node compact panel is checked');
                    })
                    .then(function() {
                        return node.openNodePopup(true);
                    })
                    .then(function() {
                        return common.assertElementNotExists('.node-popover', 'Node popover is closed when node pop-up opened');
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
                        return node.renameNode(newName, true);
                    })
                    .then(function() {
                        return common.assertElementTextEqualTo('.node-popover .name p', newName, 'Node name has been updated from extended view');
                    })
                    .then(function() {
                        return node.discardNode(true);
                    })
                    .then(function() {
                        return common.assertElementNotExists('.node', 'Node has been removed');
                    });
            },
            'Additional tests for unallocated node': function() {
                return this.remote
                    .clickByCssSelector('button.btn-add-nodes')
                    .waitForCssSelector('.node-list', 2000)
                    .then(function() {
                        return node.openCompactNodeExtendedView();
                    })
                    .then(function() {
                        return common.assertElementNotExists('.node-popover .role-list', 'Unallocated node does not have roles assigned');
                    })
                    .then(function() {
                        return common.assertElementNotExists('.node-popover .node-buttons .btn', 'There are no action buttons in unallocated node extended view');
                    })
                    .then(function() {
                        return node.openNodePopup(true);
                    })
                    .then(function() {
                        return common.assertElementNotExists('.modal .btn-edit-disks', 'Disks can not be configured for unallocated node');
                    })
                    .then(function() {
                        return common.assertElementNotExists('.modal .btn-edit-networks', 'Interfaces can not be configured for unallocated node');
                    })
                    .then(function() {
                        return modal.close();
                    });
            }
        };
    });
});
