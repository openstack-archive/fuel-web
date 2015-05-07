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
casper.start().authenticate().skipWelcomeScreen();
casper.createCluster({name: 'Test Cluster'});
var nodes = [
    {status: 'discover', manufacturer: 'Dell', mac: 'C0:8D:DF:52:76:F1', cluster_id: 1, roles: ['controller'], pending_addition: true}
];
nodes.forEach(function(node) {
    casper.createNode(node);
});

casper.loadPage('#cluster/1/nodes').waitForSelector('.nodes-tab > *');

casper.then(function() {
    this.test.comment('Testing node view modes');
    this.test.assertExists('.view-mode-switcher .standard.active', 'Environment has standard view mode by default');
    this.test.assertEvalEquals(function() {return $('.node').length}, 1, 'Environment has one node');
    this.test.assertEvalEquals(function() {return $('.compact-node').length}, 0, 'Environment node has standard view');
    this.click('.view-mode-switcher .compact');
    this.test.assertExists('.view-mode-switcher .compact.active', 'Compact node view mode is enabled');
    this.test.assertEvalEquals(function() {return $('.compact-node').length}, 1, 'Environment node has compact view');
    this.click('.node-name p');
    this.test.assertDoesntExist('.node-name input', 'Node can not be renamed from compact panel');
    this.click('.node');
    this.test.assertExists('.node-buttons .glyphicon', 'Node can be checked in compact view');
    this.click('.node-hardware p');
    this.test.assertSelectorAppears('.node-popover', 'Node expanded view appears', 1000);
    this.then(function() {
        this.click('.node-popover-buttons .node-details');
        this.test.assertSelectorAppears('.modal', 'Node pop-up is opened from node extended view');
        this.click('.modal-footer button');
    });
    this.then(function() {
        this.click('.node-popover .name p');
        this.test.assertExists('.node-popover .name input', 'Node can be renamed in extended panel');
        // TODO (jaranovich): need to test node remaming
        this.test.assertExists('.node-popover .role-list', 'Node roles are presented on extended panel');
        this.click('.node-popover .btn-discard');
    });
    this.test.assertSelectorDisappears('.node', 'Node was successfully removed from environment');
});

casper.run(function() {
    this.test.done();
});