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

define([
  'intern!object',
  'tests/functional/helpers',
  'intern/dojo/node!leadfoot/helpers/pollUntil',
  'tests/functional/pages/interfaces',
  'tests/functional/pages/common'
], function(registerSuite, helpers, pollUntil, InterfacesPage, Common) {
  'use strict';

  registerSuite(function() {
    var common,
      interfacesPage,
      clusterName;

    return {
      name: 'Node Interfaces',
      setup: function() {
        common = new Common(this.remote);
        interfacesPage = new InterfacesPage(this.remote);
        clusterName = common.pickRandomName('Test Cluster');

        return this.remote
          .then(function() {
            return common.getIn();
          })
          .then(function() {
            return common.createCluster(clusterName);
          })
          .then(function() {
            return common.addNodesToCluster(1, 'Controller', null, 'Supermicro X9SCD');
          })
          .clickByCssSelector('.node.pending_addition input[type=checkbox]:not(:checked)')
          .clickByCssSelector('button.btn-configure-interfaces')
          .assertElementAppears('div.ifc-list', 2000, 'Node interfaces loaded')
          .then(pollUntil(function() {
            return window.$('div.ifc-list').is(':visible') || null;
          }, 1000));
      },
      afterEach: function() {
        return this.remote
          .clickByCssSelector('.btn-defaults')
          .waitForCssSelector('.btn-defaults:enabled', 2000);
      },
      teardown: function() {
        return this.remote
          .then(function() {
            return common.removeCluster(clusterName, true);
          });
      },
      'Untagged networks error': function() {
        return this.remote
          .then(function() {
            return interfacesPage.assignNetworkToInterface('Public', 'eth0');
          })
          .assertElementExists('div.ifc-error',
            'Untagged networks can not be assigned to the same interface message should appear');
      },
      'Bond interfaces with different speeds': function() {
        return this.remote
          .then(function() {
            return interfacesPage.selectInterface('eth2');
          })
          .then(function() {
            return interfacesPage.selectInterface('eth3');
          })
          .assertElementExists('div.alert.alert-warning',
            'Interfaces with different speeds bonding not recommended message should appear')
          .assertElementEnabled('.btn-bond', 'Bonding button should still be enabled');
      },
      'Interfaces bonding': function() {
        return this.remote
          .then(function() {
            return interfacesPage.bondInterfaces('eth1', 'eth2');
          })
          .then(function() {
            // Two interfaces bonding
            return interfacesPage.checkBondInterfaces('bond0', ['eth1', 'eth2']);
          })
          .then(function() {
            return interfacesPage.bondInterfaces('bond0', 'eth5');
          })
          .then(function() {
            // Adding interface to existing bond
            return interfacesPage.checkBondInterfaces('bond0', ['eth1', 'eth2', 'eth5']);
          })
          .then(function() {
            return interfacesPage.removeInterfaceFromBond('eth2');
          })
          .then(function() {
            // Removing interface from the bond
            return interfacesPage.checkBondInterfaces('bond0', ['eth1', 'eth5']);
          });
      },
      'Interfaces unbonding': function() {
        return this.remote
          .then(function() {
            return interfacesPage.bondInterfaces('eth1', 'eth2');
          })
          .then(function() {
            // Two interfaces bonding
            return interfacesPage.selectInterface('bond0');
          })
          .clickByCssSelector('.btn-unbond')
          .then(function() {
            return interfacesPage.selectInterface('eth1');
          })
          .then(function() {
            return interfacesPage.selectInterface('eth2');
          });
      },
      'Check that two bonds cannot be bonded': function() {
        return this.remote
          .then(function() {
            return interfacesPage.bondInterfaces('eth0', 'eth2');
          })
          .then(function() {
            return interfacesPage.bondInterfaces('eth1', 'eth5');
          })
          .then(function() {
            return interfacesPage.selectInterface('bond0');
          })
          .then(function() {
            return interfacesPage.selectInterface('bond1');
          })
          .assertElementDisabled('.btn-bond', 'Making sure bond button is disabled')
          .assertElementContainsText('.alert.alert-warning',
            ' network interface is already bonded with other network interfaces.',
            'Warning message should appear when intended to bond bonds');
      }
    };
  });
});
