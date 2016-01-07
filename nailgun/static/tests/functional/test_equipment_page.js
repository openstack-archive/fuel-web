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
/*eslint no-var: 0*/
define([
    'intern!object',
    'tests/functional/pages/common',
    'tests/functional/pages/node',
    'tests/functional/pages/modal'
], function(registerSuite, Common, NodeComponent, ModalWindow) {
    'use strict';

    registerSuite(function() {
        var common,
            node,
            modal;

        return {
            name: 'Equipment Page',
            setup: function() {
                common = new Common(this.remote);
                node = new NodeComponent(this.remote);
                modal = new ModalWindow(this.remote);

                return this.remote
                    .then(function() {
                        return common.getIn();
                    })
                    .then(function() {
                        return common.createCluster('Env#1');
                    })
                    .then(function() {
                        return common.addNodesToCluster(2, ['Controller']);
                    })
                    // go back to Environments page
                    .clickLinkByText('Environments')
                    .waitForCssSelector('.clusters-page', 2000)
                    .then(function() {
                        return common.createCluster('Env#2');
                    })
                    .then(function() {
                        return common.addNodesToCluster(2, ['Compute', 'Virtual']);
                    })
                    // go back to Environments page
                    .clickLinkByText('Environments')
                    .waitForCssSelector('.clusters-page', 2000)
                    // go to Equipment page
                    .clickLinkByText('Equipment')
                    .waitForCssSelector('.equipment-page', 5000);
            },
            'Equipment page is rendered correctly': function() {
                return this.remote
                    .assertElementsExist('.node', 8, 'All Fuel nodes are presented')
                    .assertElementNotExists('.control-buttons-box .btn', 'No management buttons presented')
                    .assertElementsExist('.nodes-group', 4, 'The page has default sorting by node status');
            },
            'Check action buttons': function() {
                return this.remote
                    .assertElementNotExists('.node .btn-discard', 'No discard changes button on a node')
                    .assertElementExists('.node.offline .node-remove-button', 'Removing of offline nodes is available on the page')
                    .clickByCssSelector('.node.pending_addition > label')
                    .assertElementNotExists('.control-buttons-box .btn', 'No management buttons for selected node')
                    .assertElementExists('.node-list-management-buttons .btn-labels:not(:disabled)', 'Nodes can be labelled on the page')
                    .assertElementsExist('.node.pending_addition .btn-view-logs', 4, 'View logs button is presented for assigned to any environment nodes')
                    .assertElementNotExists('.node:not(.pending_addition) .btn-view-logs', 'View logs button is not presented for unallocated nodes')
                    .clickByCssSelector('.node .node-settings')
                    .then(function() {
                        return modal.waitToOpen();
                    })
                    .assertElementNotExists('.btn-edit-disks', 'No disks configuration buttons in node pop-up')
                    .assertElementNotExists('.btn-edit-networks', 'No interfaces configuration buttons in node pop-up')
                    .then(function() {
                        return modal.close();
                    })
                    .clickByCssSelector('label.compact')
                    .then(function() {
                        return node.openCompactNodeExtendedView();
                    })
                    .assertElementNotExists('.node-popover .node-buttons .btn:not(.btn-view-logs)', 'No action buttons in node extended view in compact mode');
            }
        };
    });
});
