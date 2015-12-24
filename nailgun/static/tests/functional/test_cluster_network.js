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
  'intern/dojo/node!lodash',
  'intern!object',
  'intern/chai!assert',
  'tests/functional/pages/common',
  'tests/functional/pages/networks',
  'tests/functional/pages/cluster',
  'tests/functional/pages/modal',
  'tests/functional/pages/dashboard'
], function(_, registerSuite, assert, Common, NetworksPage, ClusterPage, ModalWindow, DashboardPage) {
  'use strict';

  registerSuite(function() {
    var common,
      networksPage,
      clusterPage,
      clusterName;

    return {
      name: 'Networks page Neutron tests',
      setup: function() {
        common = new Common(this.remote);
        networksPage = new NetworksPage(this.remote);
        clusterPage = new ClusterPage(this.remote);
        clusterName = common.pickRandomName('Test Cluster');

        return this.remote
          .then(function() {
            return common.getIn();
          })
          .then(function() {
            return common.createCluster(
              clusterName,
              {
                'Networking Setup': function() {
                  return this.remote
                    .clickByCssSelector('input[value=network\\:neutron\\:ml2\\:vlan]')
                    .clickByCssSelector('input[value=network\\:neutron\\:ml2\\:tun]');
                }
              }
            );
          })
          .then(function() {
            return clusterPage.goToTab('Networks');
          });
      },
      afterEach: function() {
        return this.remote
          .clickByCssSelector('.btn-revert-changes');
      },
      'Add ranges manipulations': function() {
        var rangeSelector = '.public .ip_ranges ';
        return this.remote
          .clickByCssSelector(rangeSelector + '.ip-ranges-add')
          .assertElementsExist(rangeSelector + '.ip-ranges-delete', 2, 'Remove ranges controls appear')
          .clickByCssSelector(networksPage.applyButtonSelector)
          .assertElementsExist(rangeSelector + '.range-row',
              'Empty range row is removed after saving changes')
          .assertElementNotExists(rangeSelector + '.ip-ranges-delete',
              'Remove button is absent for only one range');
      },
      'DNS nameservers manipulations': function() {
        var dnsNameserversSelector = '.dns_nameservers ';
        return this.remote
          .clickByCssSelector('.subtab-link-neutron_l3')
          .clickByCssSelector(dnsNameserversSelector + '.ip-ranges-add')
          .assertElementExists(dnsNameserversSelector + '.range-row .has-error',
              'New nameserver is added and contains validation error');
      },
      'Segmentation types differences': function() {
        return this.remote
          .clickByCssSelector('.subtab-link-default')
          // Tunneling segmentation tests
          .assertElementExists('.private',
              'Private Network is visible for tunneling segmentation type')
          .assertElementTextEquals('.segmentation-type', '(Neutron with tunneling segmentation)',
              'Segmentation type is correct for tunneling segmentation')
          // Vlan segmentation tests
          .clickLinkByText('Environments')
          .then(function() {
            return common.createCluster('Test vlan segmentation');
          })
          .then(function() {
            return clusterPage.goToTab('Networks');
          })
          .assertElementNotExists('.private', 'Private Network is not visible for vlan segmentation type')
          .assertElementTextEquals('.segmentation-type', '(Neutron with VLAN segmentation)',
              'Segmentation type is correct for VLAN segmentation');
      },
      'Junk input in ip fields': function() {
        return this.remote
          .clickByCssSelector('.subtab-link-default')
          .setInputValue('.public input[name=cidr]', 'blablabla')
          .assertElementAppears('.public .has-error input[name=cidr]', 1000,
            'Error class is applied for invalid cidr')
          .assertElementAppears('.subtab-link-default .subtab-icon.glyphicon-danger-sign', 1000,
            'Warning icon for node network group appears')
          .assertElementAppears('.add-nodegroup-btn .glyphicon-danger-sign', 1000,
            'Warning icon for add node network group appears')
          .setInputValue('.public input[name=range-start_ip_ranges]', 'blablabla')
          .assertElementAppears('.public .has-error input[name=range-start_ip_ranges]', 1000,
            'Error class is applied for invalid range start');
      },
      'Other settings validation error': function() {
        return this.remote
          .clickByCssSelector('.subtab-link-network_settings')
          .setInputValue('input[name=dns_list]', 'blablabla')
          .assertElementAppears('.subtab-link-network_settings .glyphicon-danger-sign', 1000,
            'Warning icon for "Other" section appears');
      }
    };
  });

  registerSuite(function() {
    var common,
      clusterPage,
      dashboardPage,
      clusterName,
      modal;

    return {
      name: 'Node network group tests',
      setup: function() {
        common = new Common(this.remote);
        clusterPage = new ClusterPage(this.remote);
        dashboardPage = new DashboardPage(this.remote);
        clusterName = common.pickRandomName('Test Cluster');
        modal = new ModalWindow(this.remote);

        return this.remote
          .then(function() {
            return common.getIn();
          })
          .then(function() {
            return common.createCluster(clusterName);
          })
          .then(function() {
            return clusterPage.goToTab('Networks');
          });
      },
      'Node network group creation': function() {
        return this.remote
          .clickByCssSelector('.add-nodegroup-btn')
          .then(function() {
            return modal.waitToOpen();
          })
          .assertElementContainsText('h4.modal-title', 'Add New Node Network Group', 'Add New Node Network Group modal expected')
          .setInputValue('[name=node-network-group-name]', 'Node_Network_Group_1')
          .then(function() {
            return modal.clickFooterButton('Add Group');
          })
          .then(function() {
            return modal.waitToClose();
          })
          .assertElementAppears('.node-network-groups-list', 2000, 'Node network groups title appears')
          .assertElementDisplayed('.subtab-link-Node_Network_Group_1', 'New subtab is shown')
          .assertElementTextEquals('.network-group-name .btn-link', 'Node_Network_Group_1', 'New Node Network group title is shown');
      },
      'Verification is disabled for multirack': function() {
        return this.remote
          .clickByCssSelector('.subtab-link-network_verification')
          .assertElementExists('.alert-warning', 'Warning is shown')
          .assertElementDisabled('.verify-networks-btn', 'Verify networks button is disabled');
      },
      'Node network group renaming': function() {
        return this.remote
          .clickByCssSelector('.subtab-link-Node_Network_Group_1')
          .clickByCssSelector('.glyphicon-pencil')
          .waitForCssSelector('.network-group-name input[type=text]', 2000)
          .findByCssSelector('.node-group-renaming input[type=text]')
            .type('Node_Network_Group_2')
            // Enter
            .type('\uE007')
            .end()
          .assertElementDisplayed('.subtab-link-Node_Network_Group_2', 'Node network group was successfully renamed');
      },
      'Node network group deletion': function() {
        return this.remote
          .clickByCssSelector('.subtab-link-default')
          .assertElementNotExists('.glyphicon-remove', 'It is not possible to delete default node network group')
          .clickByCssSelector('.subtab-link-Node_Network_Group_2')
          .assertElementAppears('.glyphicon-remove', 1000, 'Remove icon is shown')
          .clickByCssSelector('.glyphicon-remove')
          .then(function() {
            return modal.waitToOpen();
          })
          .assertElementContainsText('h4.modal-title', 'Remove Node Network Group', 'Remove Node Network Group modal expected')
          .then(function() {
            return modal.clickFooterButton('Delete');
          })
          .then(function() {
            return modal.waitToClose();
          })
          .assertElementDisappears('.subtab-link-Node_Network_Group_2', 2000, 'Node network groups title disappears');
      },
      'Node network group renaming in deployed environment': function() {
        this.timeout = 100000;
        return this.remote
          .then(function() {
            return common.addNodesToCluster(1, ['Controller']);
          })
          .then(function() {
            return clusterPage.goToTab('Dashboard');
          })
          .then(function() {
            return dashboardPage.startDeployment();
          })
          .waitForElementDeletion('.dashboard-block .progress', 60000)
          .then(function() {
            return clusterPage.goToTab('Networks');
          })
          .clickByCssSelector('.subtab-link-default')
          .assertElementNotExists('.glyphicon-pencil', 'Renaming of a node network group is fobidden in deployed environment')
          .clickByCssSelector('.network-group-name .name')
          .assertElementNotExists('.network-group-name input[type=text]', 'Renaming is not started on a node network group name click')
          .then(function() {
            return clusterPage.goToTab('Dashboard');
          })
          .then(function() {
            return clusterPage.resetEnvironment(clusterName);
          })
          .then(function() {
            return dashboardPage.discardChanges();
          });
      }
    };
  });
});
