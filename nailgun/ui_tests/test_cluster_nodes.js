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
casper.start();
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
    this.test.assertExists('.cluster-toolbar .btn-configure-disks:disabled', 'Button Configure Disks is disabled');
    this.test.assertExists('.cluster-toolbar .btn-configure-interfaces:disabled', 'Button Configure Interfaces is disabled');
    this.test.assertExists('.cluster-toolbar .btn-add-nodes:not(:disabled)', 'Add Nodes button is enabled');
    this.test.assertEvalEquals(function() {return $('.node-box').length}, 0, 'Number of available roles is correct');
});

casper.then(function() {
    this.test.comment('Testing node adding with controller role');
    this.click('.cluster-toolbar  .btn-add-nodes');
    this.test.assertSelectorAppears('.roles-panel', 'Add controller nodes screen appears');
    this.then(function() {
        this.test.assertEvalEquals(function() {return $('.node-box .node-content').length}, 1, 'Number of unallocated nodes is correct');
        this.evaluate(function() {
            $('input[name="controller"]').click();
            $('.node-checkbox input[type=checkbox]').click(); // clicks all available nodes, this.click clicks only one
        });
        this.click('.btn-apply');
        this.test.assertSelectorAppears('.cluster-toolbar .btn-add-nodes', 'Return to nodes tab');
        this.test.assertEvalEquals(function() {return $('.node-box').length}, 1, 'Number of available roles is correct');

    });
});

casper.then(function() {
    this.test.comment('Testing stop deployment');
    this.test.assertExists('.deployment-control .deploy-btn:not(:disabled)', 'Deploy changes button is enabled');
    this.click('.deployment-control .deploy-btn'); // "Deploy changes" button click
    this.test.assertSelectorAppears('.modal', 'Deployment dialog opens');
    this.then(function() {
        this.click('.modal .start-deployment-btn'); // "Start Deployment" button click
    });
    this.test.assertSelectorDisappears('.modal', 'Deployment dialog closes after clicking Start Deployment');
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
        this.test.assertExists('.deployment-control .deploy-btn:not(:disabled)', 'Deploy changes button is enabled');
        this.test.assertExists('.alert-success', 'Success alert message appears');
    });
});

casper.then(function() {
    this.test.comment('Testing Tabs locking after deployment stop');
    var countIsReadyNodes = this.evaluate(function() { // get count of Nodes with Ready status
        return $('.node-box.ready').length;
    });
    if ( countIsReadyNodes > 0) { // there are ready nodes, we should check that "Network" and "Settings" tab are locked
        this.test.comment('- there are ready nodes in list');
        this.loadPage('#cluster/1/network').waitForSelector('#tab-network > *');
        casper.then(function() {
            var countTextInputs = this.evaluate(function() { return $('input[type=text]').length; });
            this.test.assertEvalEquals(function() {return $('input[type=text]:disabled').length}, countTextInputs, 'All text inputs are disabled. Network Tab is Locked');
        });
        this.loadPage('#cluster/1/settings').waitForSelector('#tab-settings > *');
        casper.then(function() {
            var countTextInputs = this.evaluate(function() { return $('input[type=text]').length; });
            this.test.assertEvalEquals(function() {return $('input[type=text]:disabled').length}, countTextInputs, 'All text inputs are disabled. Settings Tab is Locked');
        });
        // TODO: add "Health Check" Tab checking - it should be Unlocked in this scenario
    }
    else { // there are no ready nodes, we should check that "Network" and "Settings" tab are unlocked
        this.test.comment('- there are no ready nodes in list');
        this.loadPage('#cluster/1/network').waitForSelector('#tab-network > *');
        casper.then(function() {
            this.test.assertExists('input[type=text]:not(:disabled)', 'All text inputs are enabled. Network Tab is unlocked');
        });
        this.loadPage('#cluster/1/settings').waitForSelector('#tab-settings > *');
        casper.then(function() {
            this.test.assertExists('input[type=text]:not(:disabled)', 'All text inputs are enabled. Settings Tab is unlocked');
            //this.capture("ui_tests/_stop_deployment.png");
        });
        // TODO: add "Health Check" Tab checking - it should be locked in this scenario
    }
});

/*
casper.then(function() {
    this.test.comment('Testing deployment');
    this.click('.deployment-control .deploy-btn');
    this.test.assertSelectorAppears('.modal', 'Deployment dialog opens');
    this.then(function() {
        this.click('.modal .start-deployment-btn');
    });
    this.test.assertSelectorDisappears('.modal', 'Deployment dialog closes after clicking Start Deployment');
    this.test.assertSelectorAppears('.deployment-control .progress', 'Deployment progress bar appears');
    this.then(function() {
        this.test.assertDoesntExist('.node-list .btn-add-nodes:not(.disabled)', 'All Add Node buttons are disabled');
        this.test.assertDoesntExist('.node-list .btn-delete-nodes:not(.disabled)', 'All Delete Node buttons are disabled');
        this.test.info('Waiting for deployment readiness...');
    });
    this.test.assertSelectorDisappears('.deployment-control .progress', 'Deployment progress bar disappears', 60000);
    this.then(function() {
        this.test.assertDoesntExist('.summary .change-cluster-mode-btn:not(.disabled)', 'Cluster mode is not changeable');
        this.test.assertExists('.node-list .btn-add-nodes:not(.disabled)', 'Add Node buttons are enabled again');
        this.test.assertExists('.node-list .btn-delete-nodes:not(.disabled)', 'Delete Node buttons are enabled again');
        this.test.assertSelectorHasText('.task-result', 'Success', 'Message about successful deployment appeared');
    });
});

*/
casper.run(function() {
    this.test.done();
});