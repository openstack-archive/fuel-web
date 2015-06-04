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
    {status: 'discover', manufacturer: 'Dell', mac: 'C0:8D:DF:52:76:F1', cluster_id: 1, roles: ['compute'], pending_addition: true}
];
nodes.forEach(function(node) {
    casper.createNode(node);
});
var vmSDA;
var osSDA;

casper.loadPage('#cluster/1/nodes').waitForSelector('.nodes-tab > *');

casper.then(function() {
    this.test.comment('Testing nodes disks');

    var sdaDisk = '.disk-box[data-disk=sda]';
    var sdaDiskVM = sdaDisk + ' .disk-utility-box [data-volume=vm]';
    var sdaDiskOS = sdaDisk + ' .disk-utility-box [data-volume=os]';
    var vdaDisk = '.disk-box[data-disk=vda]';
    var vdaDiskVM = vdaDisk + ' .disk-utility-box [data-volume=vm]';
    var vdaDiskOS = vdaDisk + ' .disk-utility-box [data-volume=os]';

    this.then(function() {
        this.then(function() {
            this.click('.node-settings');
        });
        this.test.assertSelectorAppears('.modal', 'Node details popup was opened');
        this.then(function() {
            this.click('.btn-edit-disks');
        });
        this.test.assertSelectorAppears('.disk-box', 'Node disks configuration screen appears');
    });

    this.then(function() {
        this.test.comment('Testing nodes disks layout');
        this.test.assertEvalEquals(function() {return $('.disk-box').length}, 2, 'Number of disks is correct');
        this.test.assertExists('.btn-defaults:not(:disabled)', 'Load Defaults button is enabled');
        this.test.assertExists('.btn-revert-changes:disabled', 'Cancel button is disabled');
        this.test.assertExists('.btn-apply:disabled', 'Apply button is disabled');
    });

    this.then(function() {
        this.test.comment('Testing nodes disk block');
        this.click(sdaDisk + ' .disk-visual [data-volume=os] .toggle');
        vmSDA = this.getElementAttribute(sdaDiskVM + ' input', 'value');
        osSDA = this.getElementAttribute(sdaDiskOS + ' input', 'value');
        this.test.assertExists(sdaDiskOS, 'Base system group form is presented');
        this.test.assertExists(sdaDiskVM, 'Virtual Storage group form is presented');
        this.test.assertDoesntExist(sdaDisk + ' .disk-visual [data-volume=os] .close-btn', 'Button Close for Base system group is not presented');
        this.test.assertExists(sdaDisk + ' .disk-visual [data-volume=vm] .close-btn', 'Button Close for Virtual Storage group is presented');
    });

    this.then(function() {
        this.test.comment('Testing button Apply: interractions');
        this.fill(sdaDiskVM, {'vm': '80'});
        this.evaluate(function(sdaDiskVM) {$(sdaDiskVM + ' input').keyup();}, {sdaDiskVM: sdaDiskVM});
        this.test.assertExists('.btn-defaults:not(:disabled)', 'Load Defaults button is enabled');
        this.test.assertExists('.btn-revert-changes:not(:disabled)', 'Cancel button is enabled');
        this.test.assertExists('.btn-apply:not(:disabled)', 'Apply button is enabled');
    });

    this.then(function() {
        this.test.comment('Testing button Load Defaults');
        this.test.assertExists('.btn-defaults:not(:disabled)', 'Load Defaults button is enabled');
        this.click('.btn-defaults');
        this.test.assertSelectorAppears('.btn-defaults:not(:disabled)', 'Defaults were loaded');
        this.then(function() {
            this.test.assertEvalEquals(function(sdaDiskVM) {return $(sdaDiskVM + ' input[type=number]').attr('value')}, vmSDA, 'Volume group input control VM contains default value', {sdaDiskVM:sdaDiskVM});
            this.test.assertEvalEquals(function(sdaDiskOS) {return $(sdaDiskOS + ' input[type=number]').attr('value')}, osSDA, 'Volume group input control OS contains default value', {sdaDiskOS:sdaDiskOS});
        });
    });

    this.then(function() {
        this.test.comment('Testing volume group deletion and Cancel button');
        this.click(sdaDisk + ' .disk-visual [data-volume=vm] .close-btn');
        this.test.assertEquals(this.getElementBounds(sdaDisk + ' .disk-visual [data-volume=vm]').width, 0, 'VM group was removed successfully');
        this.click('.btn-revert-changes');
        this.test.assertEvalEquals(function(sdaDiskVM) {return $(sdaDiskVM + ' input[type=number]').attr('value')}, vmSDA, 'Volume group input control VM contains default value', {sdaDiskVM:sdaDiskVM});
        this.click(sdaDisk + ' .disk-visual [data-volume=vm] .close-btn');
        this.test.assertEval(function(sdaDisk) {return $(sdaDisk + ' .disk-visual [data-volume=unallocated]').width() > 0}, 'There is unallocated space after Virtual Storage VG removal',{sdaDisk:sdaDisk});
        this.test.assertEvalEquals(function(sdaDiskVM) {return $(sdaDiskVM + ' input[type=number]').val()}, '0', 'Volume group input control contains correct value',{sdaDiskVM:sdaDiskVM});
    });

});


casper.run(function() {
    this.test.done();
});
