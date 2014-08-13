/*
 * Copyright 2013 Mirantis, Inc.
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
casper.start().authenticate();
casper.createCluster({name: 'Test Cluster'});
var nodes = [
    {status: 'discover', manufacturer: 'Dell', mac: 'C0:8D:DF:52:76:F1'}
];
nodes.forEach(function(node) {
    casper.createNode(node);
});

casper.loadPage('#cluster/1/nodes').waitForSelector('#tab-nodes > *');

casper.then(function() {
    this.test.comment('Testing cluster page');
    this.test.assertExists('.deployment-control .deploy-btn.disabled', 'Deploy changes button is disabled');
    this.test.assertExists('.cluster-toolbar .btn-configure-disks:disabled', 'Button Configure Disks is disabled');
    this.test.assertExists('.cluster-toolbar .btn-configure-interfaces:disabled', 'Button Configure Interfaces is disabled');
    this.test.assertExists('.cluster-toolbar .btn-add-nodes:not(:disabled)', 'Add Nodes button is enabled');
    this.test.assertEvalEquals(function() {return $('.node-box').length}, 0, 'Number of available nodes is correct');
});

casper.then(function() {
    this.test.comment('Testing adding node with controller role');
    this.click('.cluster-toolbar  .btn-add-nodes');
    this.test.assertSelectorAppears('.roles-panel', 'Add controller nodes screen appears');
    this.then(function() {
        this.test.assertEvalEquals(function() {return $('.node-box .node-content').length}, 1, 'Number of unallocated nodes is correct');
        this.evaluate(function() {
            $('input[name="controller"]').click(); // check the controller role
            $('.node-checkbox input[type=checkbox]').click(); // check one node
        });
        this.click('.btn-apply');
    });
    this.test.assertSelectorAppears('.cluster-toolbar .btn-add-nodes', 'Return to nodes tab');
    this.then(function() {
        this.test.assertEvalEquals(function() {return $('.node-box').length}, 1, 'Number of available roles is correct');
        this.test.assertExists('.deployment-control .deploy-btn:not(.disabled)', 'Deploy changes button is enabled now');
    });
});

casper.loadPage('#cluster/1/actions').waitForSelector('#tab-actions > *');

casper.then(function() {
    this.test.comment('Testing Reset button exist and disabled');
    this.test.assertExists('.action-item-controls .reset-environment-btn:disabled', 'Reset button exist and disabled');
});

casper.loadPage('#cluster/1/nodes').waitForSelector('#tab-nodes > *');

casper.then(function() {
    this.test.comment('Testing stop deployment');
    this.test.assertExists('.deployment-control .deploy-btn:not(.disabled)', 'Deploy changes button is enabled');
    this.click('.deployment-control .deploy-btn'); // "Deploy changes" button click
    this.test.assertSelectorAppears('.modal', 'Deployment dialog opens');
    this.then(function() {
        this.click('.modal .start-deployment-btn'); // "Start Deployment" button click
    });
    this.test.assertSelectorDisappears('.modal', 'Deployment dialog closes after clicking Start Deployment');
    this.test.assertSelectorDisappears('.deployment-control .deploy-btn', 'Deploy changes button disappears');
    this.test.assertSelectorAppears('.deployment-control .progress-success', 'Deployment progress-success bar appears');
    this.test.assertSelectorAppears('.deployment-control .stop-deployment-btn', 'Stop deployment button appears');
    this.then(function() {
        this.click('.deployment-control .stop-deployment-btn'); // "Stop Deployment" button click
    });
    this.test.assertSelectorAppears('.modal', 'Stop Deployment dialog opens');
    this.then(function() {
        this.click('.modal .stop-deployment-btn'); // "Stop Deployment" on modal screen button click
    });
    this.test.assertSelectorDisappears('.modal', 'Stop deployment dialog closes after clicking Stop button');
    this.test.assertSelectorAppears('.deployment-control .progress-striped', 'Deployment progress-stopping bar appears');
    this.test.assertSelectorDisappears('.deployment-control .progress-striped', 'Deployment progress-stopping bar disappears', 60000);
    this.then(function() {
        this.test.assertExists('.deployment-control .deploy-btn:not(.disabled)', 'Deploy changes button is enabled again');
        this.test.assertExists('.alert-success', 'Success stopping deployment alert message appears');
    });
    this.loadPage('#cluster/1/actions').waitForSelector('#tab-actions > *');
    this.then(function() {
        this.test.assertExists('.action-item-controls .reset-environment-btn:not(:disabled)', 'Reset button exist and enabled after stopped deployment');
    });
});

casper.loadPage('#cluster/1/nodes').waitForSelector('#tab-nodes > *');

casper.then(function() {
    this.test.comment('Testing Tabs locking after deployment stop and there are no Ready Nodes');
    this.test.assertEvalEquals(function() {return $('.node-box.ready').length}, 0, 'Number of ready nodes is correct');
    this.loadPage('#cluster/1/network').waitForSelector('#tab-network > *');
    this.then(function() {
        this.test.assertExists('.network-settings:not(.changes-locked)', 'Network Tab is unlocked');
    });
    this.loadPage('#cluster/1/settings').waitForSelector('#tab-settings > *');
    this.then(function() {
        this.test.assertExists('.openstack-settings:not(.changes-locked)', 'Settings Tab is unlocked');
    });
    // TODO: add "Health Check" Tab checking - it should be locked in this scenario
});

casper.loadPage('#cluster/1/nodes').waitForSelector('#tab-nodes > *');

casper.then(function() {
    this.test.comment('Testing deployment process');
    this.test.assertExists('.deployment-control .deploy-btn:not(.disabled)', 'Deploy changes button is enabled');
    this.click('.deployment-control .deploy-btn'); // "Deploy changes" button click
    this.test.assertSelectorAppears('.modal', 'Deployment dialog opens');
    this.then(function() {
        this.click('.modal .start-deployment-btn'); // "Start Deployment" button click
    });
    this.test.assertSelectorDisappears('.modal', 'Deployment dialog closes after clicking Start Deployment');
    this.test.assertSelectorDisappears('.deployment-control .deploy-btn', 'Deploy changes button disappears');
    this.test.assertSelectorAppears('.deployment-control .progress-success', 'Deployment progress-success bar appears');
    this.test.assertSelectorAppears('.deployment-control .stop-deployment-btn', 'Stop deployment button appears');
    this.waitForSelector('.node-box.ready', function() { // We are waiting till node become ready
        this.test.assertEvalEquals(function() {return $('.node-box.ready').length}, 1, 'Number of ready nodes is correct');
    }, function() { this.test.comment("Timeout reached"); }, 60000);
    this.test.assertSelectorDisappears('.deployment-control .progress-success', 'Deployment progress-stopping bar disappears', 60000);
    this.then(function() {
        this.test.assertExists('.alert-success', 'Success deployment process finish message appears');
        this.test.assertExists('.deployment-control .deploy-btn.disabled', 'Deploy changes button is disabled');
        var countIsReadyNodes = this.evaluate(function() { // get count of Nodes with Ready status
            return $('.node-box.ready').length;
        });
        this.test.assertEvalEquals(function() {return $('.node-box .node-content').length}, countIsReadyNodes, 'All nodes in list are ready');
    });
});

casper.then(function() {
    this.test.comment('Testing Tabs locking after deployment finished completely');
    this.loadPage('#cluster/1/network').waitForSelector('#tab-network > *');
    this.then(function() {
        this.test.assertExists('.network-settings.changes-locked', 'Network Tab is Locked');
    });
    this.loadPage('#cluster/1/settings').waitForSelector('#tab-settings > *');
    this.then(function() {
        this.test.assertExists('.openstack-settings.changes-locked', 'Settings Tab is Locked');
    });
    // TODO: add "Health Check" Tab checking - it should be Unlocked in this scenario
});

casper.loadPage('#cluster/1/actions').waitForSelector('#tab-actions > *');

casper.then(function() {
    this.test.comment('Testing Reset button');
    this.test.assertExists('.action-item-controls .reset-environment-btn:not(:disabled)', 'Reset button exist and enabled after successful finished deployment');
    this.click('.action-item-controls .reset-environment-btn'); // "Reset" button click
    this.test.assertSelectorAppears('.modal', 'Reset dialog opens');
    this.then(function() {
        this.click('.modal .reset-environment-btn'); // "Reset environment" button click
    });
    this.test.assertSelectorDisappears('.modal', 'Reset dialog closes after clicking Reset button');
    this.test.assertSelectorDisappears('.deployment-control .deploy-btn', 'Deploy changes button disappears');
    this.test.assertSelectorAppears('.deployment-control .progress-striped', 'Reset progress bar appears');
    this.test.assertSelectorDisappears('.deployment-control .progress-striped', 'Reset progress bar disappears', 60000);
    this.loadPage('#cluster/1/nodes').waitForSelector('#tab-nodes > *');
    this.then(function() {
        this.test.assertExists('.deployment-control .deploy-btn:not(.disabled)', 'Deploy changes button is enabled again');
        this.test.assertExists('.alert-success', 'Success reset message appears');
        this.test.assertEvalEquals(function() {return $('.node-box .node-content').length}, 1, 'Number of count nodes is correct');
        this.test.assertEvalEquals(function() {return $('.node-box.ready').length}, 0, 'Number of ready nodes is correct');
    });
    this.loadPage('#cluster/1/actions').waitForSelector('#tab-actions > *');
    this.then(function() {
        this.test.assertSelectorAppears('.action-item-controls .reset-environment-btn:disabled', 'Reset button is disabled after successful reset');
    });
});

casper.run(function() {
    this.test.done();
});