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
  'intern/chai!assert',
  'tests/functional/pages/common',
  'tests/functional/pages/cluster',
  'tests/functional/pages/clusters',
  'tests/functional/pages/modal',
  'tests/functional/pages/dashboard',
  'tests/functional/pages/network'
], function(registerSuite, assert, Common, ClusterPage,
    ClustersPage, ModalWindow, DashboardPage, NetworkPage) {
  'use strict';

  registerSuite(function() {
    var common,
      clusterPage,
      clusterName,
      dashboardPage;
    var applyButtonSelector = '.apply-btn';

    return {
      name: 'Networks page Neutron tests',
      setup: function() {
        common = new Common(this.remote);
        clusterPage = new ClusterPage(this.remote);
        clusterName = common.pickRandomName('Test Cluster');
        dashboardPage = new DashboardPage(this.remote);

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
          .findByCssSelector('.btn-revert-changes')
            .then(function(element) {
              return element.isEnabled()
                .then(function(isEnabled) {
                  if (isEnabled) return element.click();
                });
            })
            .end();
      },
      'Network Tab is rendered correctly': function() {
        return this.remote
          .assertElementsExist('.network-tab h3', 4, 'All networks are present');
      },
      'Testing cluster networks: Save button interactions': function() {
        var self = this;
        var cidrInitialValue;
        var cidrElementSelector = '.storage input[name=cidr]';
        return this.remote
          .findByCssSelector(cidrElementSelector)
          .then(function(element) {
            return element.getAttribute('value')
              .then(function(value) {
                cidrInitialValue = value;
              });
          })
          .end()
          .setInputValue(cidrElementSelector, '240.0.1.0/25')
          .assertElementAppears(applyButtonSelector + ':not(:disabled)', 200,
            'Save changes button is enabled if there are changes')
          .then(function() {
            return self.remote.setInputValue(cidrElementSelector, cidrInitialValue);
          })
          .assertElementAppears(applyButtonSelector + ':disabled', 200,
            'Save changes button is disabled again if there are no changes');
      },
      'Testing cluster networks: network notation change': function() {
        return this.remote
          .clickByCssSelector('.subtab-link-default')
          .assertElementAppears('.storage', 2000, 'Storage network is shown')
          .assertElementSelected('.storage .cidr input[type=checkbox]',
            'Storage network has "cidr" notation by default')
          .assertElementNotExists('.storage .ip_ranges input[type=text]:not(:disabled)',
            'It is impossible to configure IP ranges for network with "cidr" notation')
          .clickByCssSelector('.storage .cidr input[type=checkbox]')
          .assertElementNotExists('.storage .ip_ranges input[type=text]:disabled',
            'Network notation was changed to "ip_ranges"');
      },
      'Testing cluster networks: save network changes': function() {
        var cidrElementSelector = '.storage .cidr input[type=text]';
        return this.remote
          .setInputValue(cidrElementSelector, '192.168.1.0/26')
          .clickByCssSelector(applyButtonSelector)
          .assertElementsAppear('input:not(:disabled)', 2000, 'Inputs are not disabled')
          .assertElementNotExists('.alert-error', 'Correct settings were saved successfully')
          .assertElementDisabled(applyButtonSelector,
            'Save changes button is disabled again after successful settings saving');
      },
      'Testing cluster networks: verification': function() {
        return this.remote
          .clickByCssSelector('.subtab-link-network_verification')
          .assertElementDisabled('.verify-networks-btn',
            'Verification button is disabled in case of no nodes')
          .assertElementTextEquals('.alert-warning',
            'At least two online nodes are required to verify environment network configuration',
            'Not enough nodes warning is shown')
          .clickByCssSelector('.subtab-link-default')
          .then(function() {
            // Adding 2 controllers
            return common.addNodesToCluster(2, ['Controller']);
          })
          .then(function() {
            return clusterPage.goToTab('Networks');
          })
          .setInputValue('.public input[name=gateway]', '172.16.0.2')
          .clickByCssSelector('.subtab-link-network_verification')
          .clickByCssSelector('.verify-networks-btn')
          .assertElementAppears('.alert-danger.network-alert', 4000, 'Verification error is shown')
          .assertElementAppears('.alert-danger.network-alert', 'Address intersection',
            'Verification result is shown in case of address intersection')
          // Testing cluster networks: verification task deletion
          .clickByCssSelector('.subtab-link-default')
          .setInputValue('.public input[name=gateway]', '172.16.0.5')
          .clickByCssSelector('.subtab-link-network_verification')
          .assertElementNotExists('.page-control-box .alert',
            'Verification task was removed after settings has been changed')
          .clickByCssSelector('.btn-revert-changes')
          .clickByCssSelector('.verify-networks-btn')
          .waitForElementDeletion('.animation-box .success.connect-1', 6000)
          .assertElementAppears('.alert-success', 6000, 'Success verification message appears')
          .assertElementContainsText('.alert-success', 'Verification succeeded',
            'Success verification message appears with proper text')
          .clickByCssSelector('.btn-revert-changes')
          .then(function() {
            return clusterPage.goToTab('Dashboard');
          })
          .then(function() {
            return dashboardPage.discardChanges();
          }) .then(function() {
            return clusterPage.goToTab('Networks');
          });
      },
      'Check VlanID field validation': function() {
        return this.remote
          .clickByCssSelector('.subtab-link-default')
          .assertElementAppears('.management', 2000, 'Management network appears')
          .clickByCssSelector('.management .vlan-tagging input[type=checkbox]')
          .clickByCssSelector('.management .vlan-tagging input[type=checkbox]')
          .assertElementExists('.management .has-error input[name=vlan_start]',
            'Field validation has worked properly in case of empty value');
      },
      'Testing cluster networks: data validation on invalid settings': function() {
        return this.remote
          .clickByCssSelector('.subtab-link-default')
          .setInputValue('input[name=range-end_ip_ranges]', '172.16.0.2')
          .clickByCssSelector(applyButtonSelector)
          .assertElementAppears('.alert-danger.network-alert', 2000, 'Validation error appears')
          .setInputValue('.public input[name=cidr]', 'blablabla')
          .assertElementAppears('.public .has-error input[name=cidr]', 1000,
            'Error class style is applied to invalid input field')
          .assertElementExists('.subtab-link-default i.glyphicon-danger-sign',
            'Warning tab icon appears')
          .clickByCssSelector('.btn-revert-changes')
          .waitForElementDeletion('.alert-danger.network-alert', 1000)
          .assertElementNotExists('.subtab-link-default i.glyphicon-danger-sign',
            'Warning tab icon disappears')
          .assertElementNotExists('.public .has-error input[name=cidr]', 1000,
            'Error class style is removed after reverting changes');
      },
      'Add ranges manipulations': function() {
        var rangeSelector = '.public .ip_ranges ';
        return this.remote
          .clickByCssSelector(rangeSelector + '.ip-ranges-add')
          .assertElementsExist(rangeSelector + '.ip-ranges-delete', 2,
            'Remove ranges controls appear')
          .clickByCssSelector(applyButtonSelector)
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
          .assertElementNotExists('.private',
            'Private Network is not visible for vlan segmentation type')
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
      modal,
      networkPage,
      clustersPage;

    return {
      name: 'Node network group tests',
      setup: function() {
        common = new Common(this.remote);
        clusterPage = new ClusterPage(this.remote);
        dashboardPage = new DashboardPage(this.remote);
        clusterName = common.pickRandomName('Test Cluster');
        modal = new ModalWindow(this.remote);
        networkPage = new NetworkPage(this.remote);
        clustersPage = new ClustersPage(this.remote);

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
          .assertElementContainsText('h4.modal-title', 'Add New Node Network Group',
            'Add New Node Network Group modal expected')
          .setInputValue('[name=node-network-group-name]', 'Node_Network_Group_1')
          .then(function() {
            return modal.clickFooterButton('Add Group');
          })
          .then(function() {
            return modal.waitToClose();
          })
          .assertElementAppears('.node-network-groups-list', 2000,
            'Node network groups title appears')
          .assertElementDisplayed('.subtab-link-Node_Network_Group_1', 'New subtab is shown')
          .assertElementTextEquals('.network-group-name .btn-link', 'Node_Network_Group_1',
            'New Node Network group title is shown');
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
          .then(function() {
            return networkPage.renameNodeNetworkGroup('Node_Network_Group_2');
          })
          .assertElementDisplayed('.subtab-link-Node_Network_Group_2',
            'Node network group was successfully renamed')
          .then(function() {
            return common.createCluster(clusterName + '2');
          })
          .then(function() {
            return clusterPage.goToTab('Networks');
          })
          .then(function() {
            return networkPage.addNodeNetworkGroup('1');
          })
          .then(function() {
            return common.createCluster(clusterName + '3');
          })
          .then(function() {
            return clusterPage.goToTab('Networks');
          })
          .then(function() {
            return networkPage.addNodeNetworkGroup('1');
          })
          .clickByCssSelector('.subtab-link-default')
          .then(function() {
            return networkPage.renameNodeNetworkGroup('new');
          })
          .then(function() {
            return networkPage.renameNodeNetworkGroup('default');
          })
          .assertElementContainsText('.network-group-name .btn-link', 'default',
            'Node network group was successfully renamed to "default"')
          .clickLinkByText('Environments')
          .then(function() {
            return clustersPage.goToEnvironment(clusterName);
          })
          .then(function() {
            return clusterPage.goToTab('Networks');
          });
      },
      'Node network group deletion': function() {
        return this.remote
          .clickByCssSelector('.subtab-link-default')
          .assertElementNotExists('.glyphicon-remove',
            'It is not possible to delete default node network group')
          .clickByCssSelector('.subtab-link-Node_Network_Group_2')
          .assertElementAppears('.glyphicon-remove', 1000, 'Remove icon is shown')
          .clickByCssSelector('.glyphicon-remove')
          .then(function() {
            return modal.waitToOpen();
          })
          .assertElementContainsText('h4.modal-title', 'Remove Node Network Group',
            'Remove Node Network Group modal expected')
          .then(function() {
            return modal.clickFooterButton('Delete');
          })
          .then(function() {
            return modal.waitToClose();
          })
          .assertElementDisappears('.subtab-link-Node_Network_Group_2', 2000,
            'Node network groups title disappears');
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
          .assertElementNotExists('.glyphicon-pencil',
            'Renaming of a node network group is fobidden in deployed environment')
          .clickByCssSelector('.network-group-name .name')
          .assertElementNotExists('.network-group-name input[type=text]',
            'Renaming is not started on a node network group name click');
      }
    };
  });
});
