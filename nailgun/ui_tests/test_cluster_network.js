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
casper.createCluster({name: 'Test Cluster', net_provider: 'nova_network'});
casper.loadPage('#cluster/1/network').waitForSelector('.network-tab > *');

casper.then(function() {
    this.test.comment('Testing cluster networks: layout rendered');
    this.test.assertEvalEquals(function() {return $('.checkbox-group input[name=net_provider]').length}, 2, 'Network manager options are presented');
    this.test.assertExists('input[value=FlatDHCPManager]:checked', 'Flat DHCP manager is chosen');
    this.test.assertEvalEquals(function() {return $('.networks-table h3').length}, 3, 'All networks are presented');
    this.test.assertDoesntExist('.verify-networks-btn:disabled', 'Verify networks button is enabled');
    this.test.assertExists('.apply-btn:disabled', 'Save networks button is disabled');
});

casper.then(function() {
    this.test.comment('Testing cluster networks: Save button interactions');
    this.click('input[name=net_provider]:not(:checked)');
    this.test.assertDoesntExist('.apply-btn:disabled', 'Save networks button is enabled if there are changes');
    this.click('input[name=net_provider]:not(:checked)');
    this.test.assertExists('.apply-btn:disabled', 'Save networks button is disabled again if there are no changes');
});

casper.then(function() {
    this.test.comment('Testing cluster networks: change network manager');
    this.click('input[name=net_provider]:not(:checked)');
    this.test.assertExists('input[name=fixed_networks_amount]', 'Amount field for a fixed network is presented in VLAN mode');
    this.test.assertExists('select[name=fixed_network_size]', 'Size field for a fixed network is presented in VLAN mode');
    this.test.assertExists('.apply-btn:not(:disabled)', 'Save networks button is enabled after manager was changed');
    this.click('input[name=net_provider]:not(:checked)');
    this.test.assertDoesntExist('input[name=fixed_networks_amount]', 'Amount field was hidden after revert to FlatDHCP');
    this.test.assertDoesntExist('select[name=fixed_network_size]', 'Size field was hidden after revert to FlatDHCP');
    this.test.assertExists('.apply-btn:disabled', 'Save networks button is disabled again after revert to FlatDHCP');
});

casper.then(function() {
    this.test.comment('Testing cluster networks: VLAN range fields');
    this.click('input[name=net_provider]:not(:checked)');
    this.test.assertExists('.networking-parameters input[name=range-end_fixed_networks_vlan_start]', 'VLAN range is displayed');
    this.click('input[name=net_provider]:not(:checked)');
});

casper.then(function() {
    this.test.comment('Testing cluster networks: save changes');
    this.click('input[name=net_provider]:not(:checked)');
    this.click('.apply-btn:not(:disabled)');
    this.test.assertSelectorAppears('input:not(:disabled)', 'Input is not disabled');
    this.then(function() {
        this.test.assertDoesntExist('.alert-error', 'Correct settings were saved successfully');
    });
    this.click('input[name=net_provider]:not(:checked)');
});

casper.then(function() {
    this.test.comment('Testing cluster networks: verification');
    this.click('.verify-networks-btn:not(:disabled)');
    this.test.assertSelectorAppears('.connect-3.error',
        ' At least two nodes are required to be in the environment for network verification.', 10000);
});

casper.then(function() {
    this.test.comment('Testing cluster networks: verification task deletion');
    this.click('input[name=net_provider]:not(:checked)');
    this.test.assertDoesntExist('.page-control-error-placeholder', 'Verification task was removed after settings has been changed');
    this.click('input[name=net_provider]:not(:checked)');
});

casper.then(function() {
    this.test.comment('Check VlanID field validation');
    this.click('.management input[type=checkbox]');
    this.then(function() {
        this.click('.management input[type=checkbox]');
    });
    this.then(function() {
        this.test.assertExists('.management .has-error input[name=vlan_start]', 'Field validation has worked properly in case of empty value');
    });

});

casper.then(function() {
    this.test.comment('Testing cluster networks: data validation');
    this.click('.networking-parameters input[name=fixed_networks_vlan_start]');
    this.click('input[name=net_provider]:not(:checked)');
    this.test.assertExists('.networking-parameters .has-error input[name=range-start_fixed_networks_vlan_start]', 'Field validation has worked');
    this.test.assertExists('.apply-btn:disabled', 'Save networks button is disabled if there is validation error');
    this.click('input[name=net_provider]:not(:checked)');
    this.click('.networking-parameters input[name=fixed_networks_vlan_start]');
    this.test.assertDoesntExist('.networking-parameters .has-error input[name=range-start_fixed_networks_vlan_start]', 'Field validation works properly');
});

/*
* casper tests with text input fields validation do not work
* because the version of casper we use cannot send native
* keyboard events to the text inputs
* (morale)
* @TODO: port these tests
*/

casper.run(function() {
    this.test.done();
});
