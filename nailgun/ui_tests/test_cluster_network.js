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
casper.createCluster({name: 'Test Cluster', net_provider: 'nova_network'});
casper.loadPage('#cluster/1/network').waitForSelector('#tab-network > *');

casper.then(function() {
    this.test.comment('Testing cluster networks: layout rendered');
    this.test.assertEvalEquals(function() {return $('.radio-group input[name=net_provider]').length}, 2, 'Network manager options are presented');
    this.test.assertExists('input[value=FlatDHCPManager]:checked', 'Flat DHCP manager is chosen');
    this.test.assertEvalEquals(function() {return $('.networks-table legend').length}, 3, 'All networks are presented');
    this.test.assertDoesntExist('.verify-networks-btn:disabled', 'Verify networks button is enabled');
    this.test.assertExists('.apply-btn:disabled', 'Save networks button is disabled');
});

casper.then(function() {
    this.test.comment('Testing cluster networks: change network manager');
    this.click('.radio-group input[name=net_provider]:not(:checked)');
    this.test.assertExists('input[name=fixed_networks_amount]', 'Amount field for a fixed network is presented in VLAN mode');
    this.test.assertExists('select[name=fixed_network_size]', 'Size field for a fixed network is presented in VLAN mode');
    this.test.assertExists('.apply-btn:not(:disabled)', 'Save networks button is enabled after manager was changed');
    this.click('input[name=net_provider]:not(:checked)');
    this.test.assertDoesntExist('input[name=fixed_networks_amount]', 'Amount field was hidden after revert to FlatDHCP');
    this.test.assertDoesntExist('select[name=fixed_network_size]', 'Size field was hidden after revert to FlatDHCP');
    this.test.assertExists('.apply-btn:disabled', 'Save networks button is disabled again after revert to FlatDHCP');
});

casper.run(function() {
    this.test.done();
});
