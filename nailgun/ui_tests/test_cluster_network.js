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
casper.loadPage('#cluster/1/network').waitForSelector('#tab-network > *');

casper.then(function() {
    this.test.comment('Testing cluster networks: layout rendered');
    this.test.assertEvalEquals(function() {return $('input[name=net-manager]').length}, 2, 'Network manager options are presented');
    this.test.assertExists('input[value=FlatDHCPManager]:checked', 'Flat DHCP manager is chosen');
    this.test.assertEvalEquals(function() {return $('.networks-table legend').length}, 3, 'All networks are presented');
    this.test.assertDoesntExist('.verify-networks-btn:disabled', 'Verify networks button is enabled');
    this.test.assertExists('.apply-btn:disabled', 'Save networks button is disabled');
});

casper.then(function() {
    this.test.comment('Testing cluster networks: Save button interractions');
    var initialValue = this.evaluate(function() {
        return $('.management input[name=cidr]').val();
    });
    this.fill('.management', {'cidr': '240.0.1.0/25'});
    this.evaluate(function() {
        $('.management input[name=cidr]').keyup();
    });
    this.test.assertExist('.apply-btn:not(:disabled)', 'Save networks button is enabled if there are changes');
    this.fill('.management', {'cidr': initialValue});
    this.evaluate(function() {
        $('.management input[name=cidr]').keyup();
    });
    this.test.assertExists('.apply-btn:disabled', 'Save networks button is disabled again if there are no changes');
});

casper.then(function() {
    this.test.comment('Testing cluster networks: change network manager');
    this.click('input[name=net-manager]:not(:checked)');
    this.test.assertExists('input[name=fixed_networks_amount]', 'Amount field for a fixed network is presented in VLAN mode');
    this.test.assertExists('select[name=fixed_network_size]', 'Size field for a fixed network is presented in VLAN mode');
    this.test.assertExists('.apply-btn:not(:disabled)', 'Save networks button is enabled after manager was changed');
    this.click('input[name=net-manager]:not(:checked)');
    this.test.assertDoesntExist('input[name=fixed_networks_amount]', 'Amount field was hidden after revert to FlatDHCP');
    this.test.assertDoesntExist('select[name=fixed_network_size]', 'Size field was hidden after revert to FlatDHCP');
    this.test.assertExists('.apply-btn:disabled', 'Save networks button is disabled again after revert to FlatDHCP');
});

casper.then(function() {
    this.test.comment('Testing cluster networks: data validation');
    var initialValue = this.evaluate(function() {
        return $('.management input[name=cidr]').val();
    });
    this.fill('.management', {'cidr': '240.0.1.0/245'});
    this.evaluate(function() {
        $('.management input[name=cidr]').keyup();
    });
    this.test.assertExists('.management input[name=cidr].error', 'Field validation has worked');
    this.test.assertExists('.apply-btn:disabled', 'Save networks button is disabled if there is validation error');
    this.fill('.management', {'cidr': initialValue});
    this.evaluate(function() {
        $('.management input[name=cidr]').keyup();
    });
    this.test.assertDoesntExist('.management input[name=cidr].error', 'Field validation works properly');
});

casper.then(function() {
    this.test.comment('Check Amount field validation');
    this.click('input[name=net-manager]:not(:checked)');
    this.test.assertExists('input[value=VlanManager]:checked', 'VLAN manager is chosen');
    var initialAmountValue = this.evaluate(function() {
        return $('input[name=fixed_networks_amount]').val();
    });
    var initialVlanIDValue = this.evaluate(function() {
        return $('input[name=fixed_networks_vlan_start]').val();
    });

    var fixtures = [
        {
            'amount': ' ',
            'vlanStart': '',
            'vlanEnd':'',
            'validationMessage': 'with empty field'
        },
        {
            'amount': '-10',
            'vlanStart': '',
            'vlanEnd':'',
            'validationMessage': 'when use negative number'
        },
        {
            'amount': '0',
            'vlanStart': '',
            'vlanEnd':'',
            'validationMessage': 'when use 0'
        },
        {
            'amount': '2',
            'vlanStart': '4094',
            'vlanEnd':'',
            'validationMessage': 'if amount more than 4095 - VLAN ID'
        },
        {
            'amount': '2',
            'vlanStart': '4093',
            'vlanEnd':'4094',
            'validationMessage': ''
        },
        {
            'amount': '10',
            'vlanStart': '250',
            'vlanEnd':'259',
            'validationMessage': ''
        }

    ];

    this.each(fixtures, function(self, fixture) {
        self.then(function() {
            this.fill('.networking-parameters', {'fixed_networks_amount': fixture.amount});
            if (fixture.vlanStart != '') {
                this.fill('.networking-parameters', {'fixed_networks_vlan_start': fixture.vlanStart});
            }
            this.evaluate(function() {
                $('input[name=fixed_networks_amount]').keyup();
            });
            if (fixture.vlanEnd == '') {
                this.test.assertExists('input[name=fixed_networks_amount].error', 'Field validation has worked ' + fixture.validationMessage);
                this.test.assertExists('.apply-btn:disabled', 'Apply button is disabled if there is validation error');
            } else {
                this.test.assertEvalEquals(function() {return $('input[name=vlan_end]').val()}, fixture.vlanEnd, 'End value is correct');
                this.test.assertDoesntExist('input[name=fixed_networks_amount].error', 'Field validation works properly with correct value');}
        });
    });

    casper.then(function() {
	this.fill('.networking-parameters', {
            'fixed_networks_amount': '1',
            'fixed_networks_vlan_start': '4094'
        });
        this.evaluate(function() {
            $('input[name=fixed_networks_amount]').keyup();
        });
        this.test.assertDoesntExist('input[name=fixed_networks_amount].error', 'Field validation works properly');
    });

    casper.then(function() {
        this.fill('.networking-parameters', {
            'fixed_networks_amount': initialAmountValue,
            'fixed_networks_vlan_start': initialVlanIDValue
        });
	this.evaluate(function() {
            $('input[name=fixed_networks_amount]').keyup();
        });
        this.click('input[name=net-manager]:not(:checked)');
    });

});

casper.then(function() {
    this.test.comment('Check CIDR field validation');
    var initialCIDRValue = this.evaluate(function() {
        return $('.management input[name=cidr]').val();
    });

    var fixtures = [
        {
            'cidr': ' ',
            'validationMessage': 'empty field'
        },
        {
            'cidr': '0.10.-1.255/15',
            'validationMessage': 'negative number -1'
        },
        {
            'cidr': '0.-100.240.255/15',
            'validationMessage': 'negative number -100'
        },
        {
            'cidr': '0.256.240.255/15',
            'validationMessage': 'number out of area 255'
        },

        {
            'cidr': '0.750.240.255/15',
            'validationMessage': 'number 750'
        },
        {
            'cidr': '0.01.240.255/15',
            'validationMessage': 'number starts with 0'
        },
        {
            'cidr': '0.000.240.255/15',
            'validationMessage': 'number 000'
        },
        {
            'cidr': '0.50.240.255.45/15',
            'validationMessage': 'big amount of decimals groups'
        },
        {
            'cidr': '0.240.255/15',
            'validationMessage': 'little amount of decimals groups'
        },
        {
            'cidr': '0.1000.240.255/15',
            'validationMessage': 'bigger number of symbols in group'
        },
        {
            'cidr': '0..240.255/15',
            'validationMessage': 'any empty group'
        }

    ];

    this.each(fixtures, function(self, fixture) {
        self.then(function() {
            this.fill('.management', {'cidr': fixture.cidr});
            this.evaluate(function() {
                $('.management input[name=cidr]').keyup();
            });
            this.test.assertExists('.management input[name=cidr].error', 'Field validation has worked properly in case of ' + fixture.validationMessage);
        });
    });


    casper.then(function() {
	this.fill('.management', {'cidr': '0.10.100.255/15'});
        this.evaluate(function() {
            $('.management input[name=cidr]').keyup();
        });
        this.test.assertDoesntExist('.management input[name=cidr].error', 'Validation error description disappears if there are no errors');
    });

    casper.then(function() {
	this.fill('.management', {'cidr': initialCIDRValue});
        this.evaluate(function() {
            $('.management input[name=cidr]').keyup();
        });
    });

});

casper.then(function() {
    this.test.comment('Check CIDR prefix');
    var initialCIDRValue = this.evaluate(function() {
        return $('.management input[name=cidr]').val();
    });

    function testCIDRprefix (fixtures, negativeTests) {
        casper.each(fixtures, function(self, fixture) {
            self.then(function() {
                this.fill('.management', {'cidr': '240.0.1.0/' + fixture});
                this.evaluate(function() {
                    $('.managementinput[name=cidr]').keyup();
                });
                if (negativeTests) {
                    this.test.assertExists('.management input[name=cidr].error', 'Field validation has worked properly in case of prefix ' + fixture);
                } else {
                    this.test.assertDoesntExist('.management input[name=cidr].error', 'Field validation works properly in case of no errors (prefix ' + fixture +')');
                }
            });
        });
    }
    testCIDRprefix (['1', '-10', '0', '31', '75', 'test'], true);
    testCIDRprefix (['2', '30', '15'], false);

    casper.then(function() {
	this.fill('.management', {'cidr': initialCIDRValue});
        this.evaluate(function() {
            $('.management input[name=cidr]').keyup();
        });
    });
});

casper.then(function() {
    this.test.comment('Check VlanID field validation');
    var initialVlanIDValue = this.evaluate(function() {
        return $('.management input[name=vlan_start]').val();
    });

    function testVlanID (fixtures, negativeTests) {
        casper.each(fixtures, function(self, fixture) {
            self.then(function() {
                this.fill('.management', {'vlan_start': fixture});
                this.evaluate(function() {
                    $('.management input[name=vlan_start]').keyup();
                });
                if (negativeTests) {
                    this.test.assertExists('.management input[name=vlan_start].error', 'Field validation has worked properly in case of ' + fixture + ' value');
                } else {
                    this.test.assertDoesntExist('.management input[name=vlan_start].error', 'No validation errors in case of ' + fixture + ' value');
                }
            });
        });
    }
    testVlanID (['0', '4095', '-100', '5000'], true);
    testVlanID (['1', '4094', '2000'], false);

    casper.then(function() {
        this.fill('.management', {'vlan_start': initialVlanIDValue});
        this.evaluate(function() {
            $('.management input[name=vlan_start]').keyup();
        });
    });
});

casper.then(function() {
    this.test.comment('Testing cluster networks: save changes');
    this.fill('.management', {'cidr': '220.0.1.0/23'});
    this.evaluate(function() {
        $('.management input[name=cidr]').keyup();
    });
    this.click('.apply-btn:not(:disabled)');
    this.test.assertSelectorAppears('input:not(:disabled)', 'Input is not disabled');
    this.then(function() {
        this.test.assertDoesntExist('.alert-error', 'Correct settings were saved successfully');
    });
});

casper.then(function() {
    this.test.comment('Testing cluster networks: verification');
    this.click('.verify-networks-btn:not(:disabled)');
	// FIXME: disabling this assert due to bug/1297232
    //this.test.assertSelectorAppears('.connect-3-error',
    //    'There should be atleast 1 node for dhcp check. And 2 nodes for connectivity check', 10000);

});

casper.then(function() {
    this.test.comment('Testing cluster networks: verification task deletion');
    this.fill('.management', {'cidr': '240.0.1.0/22'});
    this.evaluate(function() {
        $('.management input[name=cidr]').keyup();
    });
    this.test.assertDoesntExist('.page-control-error-placeholder', 'Verification task was removed after settings has been changed');
});

casper.then(function() {
    this.test.comment('Testing cluster networks: VLAN range fields');
    this.click('input[name=net-manager]:not(:checked)');
    this.fill('.networking-parameters', {'fixed_networks_amount': '10'});
    this.evaluate(function() {
        $('input[name=fixed_networks_amount]').keyup();
    });
    this.then(function() {
        this.test.assertExists('input[name=vlan_end]', 'VLAN range is displayed');
    });
});

casper.run(function() {
    this.test.done();
});
