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
casper.start().authenticate().skipWelcomeScreen();
casper.createCluster({name: 'Test Cluster'});
var nodes = [
    {status: 'discover', manufacturer: 'Dell', mac: 'C0:8D:DF:52:76:F1'}
];
nodes.forEach(function(node) {
    casper.createNode(node);
});

casper.loadPage('#cluster/1/dashboard').waitForSelector('.dashboard-tab > *');

casper.then(function() {
    this.test.comment('Testing cluster page');
    this.test.assertDoesntExist('.deploy-btn:disabled', 'Deploy changes button is hidden');
});

casper.loadPage('#cluster/1/nodes').waitForSelector('.nodes-tab > *');

casper.then(function() {
    this.test.assertExists('.btn-configure-disks:disabled', 'Button Configure Disks is disabled');
    this.test.assertExists('.btn-configure-interfaces:disabled', 'Button Configure Interfaces is disabled');
    this.test.assertExists('.btn-add-nodes:not(:disabled)', 'Add Nodes button is enabled');
    this.test.assertEvalEquals(function() {return $('.node').length}, 0, 'Number of environment nodes is correct');
});

casper.then(function() {
    this.test.comment('Testing adding node with controller role');
    this.click('.btn-add-nodes');
    this.test.assertSelectorAppears('.node', 'Add Nodes screen appeared and unallocated nodes loaded');
    this.then(function() {
        this.test.assertEvalEquals(function() {return $('.node').length}, 9, 'Number of unallocated nodes is correct');
        this.click('input[name=controller]');
        this.click('.node input[type=checkbox]');
        this.test.assertSelectorAppears('.node .role-list > ul', 'Controller role is applied to the node');
    });
    this.then(function() {
        this.click('.btn-apply');
        this.test.assertSelectorDisappears('.role-panel', 'Return to nodes tab');
    });
    this.then(function() {
        this.test.assertEvalEquals(function() {return $('.node').length}, 1, 'Number of available roles is correct');
    });
});

casper.loadPage('#cluster/1/dashboard').waitForSelector('.dashboard-tab > *');

casper.then(function() {
    this.test.assertExists('.deploy-btn:not(:disabled)', 'Deploy changes button is enabled now');
    this.test.comment('Testing Reset button is hidden');
    this.test.assertDoesntExist('.reset-environment-btn', 'Reset button does not exist');
});

casper.then(function() {
    this.test.comment('Testing stop deployment');
    this.test.assertExists('.deploy-btn:not(:disabled)', 'Deploy changes button is enabled');
    this.click('.deploy-btn'); // "Deploy changes" button click
    this.test.assertSelectorAppears('.modal', 'Deployment dialog opens');
    this.then(function() {
        this.click('.modal .start-deployment-btn'); // "Start Deployment" button click
    });
    this.test.assertSelectorDisappears('.modal', 'Deployment dialog closes after clicking Start Deployment');
    this.test.assertSelectorDisappears('.deploy-btn', 'Deploy changes button disappears');
    this.then(function() {
        this.test.assertSelectorAppears('.deploy-process .progress-bar', 'Deployment progress bar appears');
        this.test.assertSelectorAppears('.stop-deployment-btn', 'Stop deployment button appears');
    });
    this.then(function() {
        this.click('.stop-deployment-btn'); // "Stop Deployment" button click
    });
    this.test.assertSelectorAppears('.modal', 'Stop Deployment dialog opens');
    this.then(function() {
        this.click('.modal .stop-deployment-btn'); // "Stop Deployment" on modal screen button click
    });
    this.then(function() {
        this.test.assertSelectorDisappears('.modal', 'Stop deployment dialog closes after clicking Stop button');
        this.test.assertSelectorAppears('.deploy-process .progress-bar', 'Deployment progress bar appears');
        this.test.assertSelectorDisappears('.deploy-process .progress-bar', 'Deployment progress bar disappears', 60000);
    });
    this.then(function() {
        this.test.assertSelectorAppears('.deploy-btn:not(:disabled)', 'Deploy changes button is enabled again');
        this.test.assertSelectorAppears('.alert-success', 'Success stopping deployment alert message appears');
    });
    this.loadPage('#cluster/1/dashboard').waitForSelector('.dashboard-tab > *');
    this.then(function() {
        this.test.assertExists('.reset-environment-btn:not(:disabled)', 'Reset button exist and enabled after stopped deployment');
    });
});

casper.loadPage('#cluster/1/nodes').waitForSelector('.nodes-tab > *');

casper.then(function() {
    this.test.comment('Testing Tabs locking after deployment stop and there are no Ready Nodes');
    this.test.assertEvalEquals(function() {return $('.node.ready').length}, 0, 'Number of ready nodes is correct');
    this.loadPage('#cluster/1/network').waitForSelector('.network-tab > *');
    this.then(function() {
        this.test.assertDoesntExist('.network-tab .changes-locked', 'Network Tab is unlocked');
    });
    this.loadPage('#cluster/1/settings').waitForSelector('.settings-tab > *');
    this.then(function() {
        this.test.assertExists('input[name=tenant]:not(:disabled)', 'Settings Tab is unlocked');
    });
    // TODO: add "Health Check" Tab checking - it should be locked in this scenario
});

casper.loadPage('#cluster/1/dashboard').waitForSelector('.dashboard-tab > *');

casper.then(function() {
    this.test.comment('Testing deployment process');
    this.test.assertExists('.deploy-btn:not(:disabled)', 'Deploy changes button is enabled');
    this.click('.deploy-btn'); // "Deploy changes" button click
    this.test.assertSelectorAppears('.modal', 'Deployment dialog opens');
    this.then(function() {
        this.click('.modal .start-deployment-btn'); // "Start Deployment" button click
    });
    this.test.assertSelectorDisappears('.modal', 'Deployment dialog closes after clicking Start Deployment');
    this.test.assertSelectorDisappears('.deploy-btn', 'Deploy changes button disappears');
    this.test.assertSelectorAppears('.deploy-process .progress-bar', 'Deployment progress bar appears');
    this.test.assertSelectorAppears('.stop-deployment-btn', 'Stop deployment button appears');
    this.waitForSelector('.node.ready', function() { // We are waiting till node become ready
        this.test.assertEvalEquals(function() {return $('.node.ready').length}, 1, 'Number of ready nodes is correct');
    }, function() { this.test.comment('Timeout reached'); }, 60000);
    this.test.assertSelectorDisappears('.deploy-process .progress-bar', 'Deployment progress bar disappears', 60000);
    this.then(function() {
        this.test.assertExists('.alert-success', 'Success deployment process finish message appears');
        this.test.assertExists('.deploy-btn:disabled', 'Deploy changes button is disabled');
        var countIsReadyNodes = this.evaluate(function() { // get count of Nodes with Ready status
            return $('.node.ready').length;
        });
        this.test.assertEvalEquals(function() {return $('.node').length}, countIsReadyNodes, 'All nodes in list are ready');
    });
});

casper.then(function() {
    this.test.comment('Testing Tabs locking after deployment finished completely');
    this.loadPage('#cluster/1/network').waitForSelector('.network-tab > *');
    this.then(function() {
        this.test.assertExists('.network-tab .changes-locked', 'Network Tab is Locked');
    });
    this.loadPage('#cluster/1/settings').waitForSelector('.settings-tab > *');
    this.then(function() {
        this.test.assertExists('input[name=tenant]:disabled', 'Settings Tab is Locked');
    });
    // TODO: add "Health Check" Tab checking - it should be Unlocked in this scenario
});

casper.loadPage('#cluster/1/dashboard').waitForSelector('.dashboard-tab > *');

casper.then(function() {
    this.test.comment('Testing Reset button');
    this.test.assertExists('.reset-environment-btn:not(:disabled)', 'Reset button exist and enabled after successful finished deployment');
    this.click('.reset-environment-btn'); // "Reset" button click
    this.test.assertSelectorAppears('.modal', 'Reset dialog opens');
    this.then(function() {
        this.click('.modal .reset-environment-btn'); // "Reset environment" button click
    });
    this.test.assertSelectorAppears('.modal .confirm-reset-form', 'Confirmation of reset action requested');
    this.then(function() {
        this.fill('.modal .confirm-reset-form', {name: 'Test Cluster'});
        this.click('.modal .reset-environment-btn:not(:disabled)');
    });
    this.test.assertSelectorDisappears('.modal', 'Reset dialog closes after clicking Reset button');
    this.test.assertSelectorDisappears('.deploy-btn', 'Deploy changes button disappears');
    this.test.assertSelectorAppears('.deploy-process .progress-bar', 'Reset progress bar appears');
    this.test.assertSelectorDisappears('.deploy-process .progress-bar', 'Reset progress bar disappears', 60000);
    this.then(function() {
        this.test.assertExists('.deploy-btn:not(:disabled)', 'Deploy changes button is enabled again');
        this.test.assertExists('.alert-success', 'Success reset message appears');
        this.test.assertEvalEquals(function() {return $('.node').length}, 1, 'Number of count nodes is correct');
        this.test.assertEvalEquals(function() {return $('.node.ready').length}, 0, 'Number of ready nodes is correct');
    });
    this.loadPage('#cluster/1/dashboard').waitForSelector('.dashboard-tab > *');
    this.then(function() {
        this.test.assertSelectorDisappears('.reset-environment-btn', 'Reset button is not shown after successful reset');
    });
});

casper.run(function() {
    this.test.done();
});
