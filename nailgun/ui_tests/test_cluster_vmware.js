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

casper.createVCenterCluster = function(options) {
    var self = this;
    options.release = 1; // centos
    this.then(function() {
        return this.open(baseUrl + 'api/clusters', {
            method: 'post',
            headers: addTokenHeader({'Content-Type': 'application/json'}),
            data: JSON.stringify(options)
        });
    });
    this.then(function(p1) {
        return this.open(baseUrl + 'api/clusters/1/attributes', {
            method: 'get',
            headers: addTokenHeader({'Content-Type': 'application/json'})
        });
    });
    this.then(function() {
        var attributes = this.evaluate(function(p1) {
            return JSON.parse(document.body.innerText);
        });
        attributes.editable.common.use_vcenter.value = true;
        return this.open(baseUrl + 'api/clusters/1/attributes', {
            method: 'put',
            headers: addTokenHeader({'Content-Type': 'application/json'}),
            data: JSON.stringify(attributes)
        });
    });
}

casper.start().authenticate().skipWelcomeScreen();
casper.createVCenterCluster({name: 'Test VCenter Claster', net_provider: 'nova_network'});
casper.loadPage('#cluster/1/vmware').waitForSelector('#tab-vmware > *');

casper.then(function() {
    this.test.comment('Testing VCenter: buttons have valid state');
    this.test.assertExists('.btn-load-defaults:disabled', 'Load defaults button is disabled');
    this.test.assertExists('.btn-revert-changes:disabled', 'Cancel changes button is disabled');
    this.test.assertExists('.btn-apply-changes:disabled', 'Save settings button is disabled');
});

casper.then(function() {
    this.test.comment('Testing VCenter: make changes, try exit tab, revert changes');
    this.capture('vmware2.png');
    this.click('input[type=checkbox]');
    this.wait(100);
    this.then(function() { this.click('.nav-tabs li.active + li a'); });
    this.test.assertSelectorAppears('.dismiss-settings-dialog', 'Dismiss changes dialog appears if there are changes and user is going to leave the tab');
    this.then(function() {
        this.capture('vmware4.png');
        this.click('.btn-return');
    });
    this.test.assertSelectorDisappears('.dismiss-settings-dialog', 'Dismiss changes dialog was closed');
    this.then(function() {
        this.click('.btn-revert-changes');
        this.test.assertExists('.btn-apply-changes:disabled', 'Save settings button is disabled again after changes were cancelled');
    });
});

casper.then(function() {
    this.test.comment('Testing VCenter: save changes');
    this.click('input[type=checkbox]');
    this.test.assertSelectorAppears('.btn-apply-changes:not(:disabled)', 'Save settings button is enabled');
    this.capture('vmware5.png');
    this.then(function() { this.click('.btn-apply-changes:not(:disabled)'); });
    this.test.assertSelectorDisappears('.btn-load-defaults:disabled', 'Saves settings button is disabled');
    this.then(function() {
        this.test.assertExists('.btn-revert-changes:disabled', 'Cancel changes button is disabled after changes were saved successfully');
    });
});

casper.run(function() {
    this.test.done();
});
