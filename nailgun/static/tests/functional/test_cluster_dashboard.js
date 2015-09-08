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
    'underscore',
    'intern!object',
    'intern/chai!assert',
    'tests/functional/pages/common',
    'tests/functional/pages/cluster',
    'tests/functional/pages/dashboard'
], function(_, registerSuite, assert, Common, ClusterPage, DashboardPage) {
    'use strict';

    registerSuite(function() {
        var common,
            clusterPage,
            dashboardPage,
            clusterName;

        return {
            name: 'Dashboard tab',
            setup: function() {
                common = new Common(this.remote);
                clusterPage = new ClusterPage(this.remote);
                dashboardPage = new DashboardPage(this.remote);
                clusterName = common.pickRandomName('Test Cluster');

                return this.remote
                    .then(function() {
                        return common.getIn();
                    })
                    .then(function() {
                        return common.createCluster(clusterName);
                    });
            },
            beforeEach: function() {
                return this.remote
                    .then(function() {
                        return clusterPage.goToTab('Dashboard');
                    });
            },
            teardown: function() {
                return this.remote
                    .then(function() {
                        return common.removeCluster(clusterName);
                    });
            },
            'Renaming cluster works': function() {
                var initialName = clusterName,
                    newName = clusterName + '!!!';
                return this.remote
                    .then(function() {
                        return dashboardPage.startClusterRenaming();
                    })
                    .findByCssSelector(dashboardPage.renameInputSelector)
                        // Escape
                        .type('\uE00C')
                        .end()
                    .then(function() {
                        return common.assertElementNotExists(dashboardPage.renameInputSelector, 'Rename control disappears');
                    })
                    .then(function() {
                        return common.isElementTextEqualTo(dashboardPage.nameSelector, initialName,
                            'Switching rename control does not change cluster name');
                    })
                    .then(function() {
                        return dashboardPage.setClusterName(newName);
                    })
                    .then(function() {
                        return common.isElementTextEqualTo(dashboardPage.nameSelector, newName, 'New name is applied');
                    })
                    .then(function() {
                        return dashboardPage.setClusterName(initialName);
                    });
            },
            'Provision button availability': function() {
                return this.remote
                    .then(function() {
                        return common.addNodesToCluster(1, ['Virtual']);
                    })
                    .then(function() {
                        return clusterPage.goToTab('Dashboard');
                    })
                    .then(function() {
                        return common.isElementTextEqualTo(dashboardPage.deployButtonSelector, 'Provision VMs',
                            'Text is changed for Virtual nodes');
                    })
                    .then(function() {
                        return dashboardPage.discardChanges();
                    });
            },
            'Network validation error warning': function() {
                return this.remote
                    .then(function() {
                        return common.addNodesToCluster(1, ['Controller']);
                    })
                    .then(function() {
                        return clusterPage.goToTab('Networks');
                    })
                    .clickByCssSelector('.verify-networks-btn')
                    .then(function() {
                        return common.assertElementExists('.verification-box .alert-danger', 'No nodes added - so verification fails');
                    })
                    .then(function() {
                        return clusterPage.goToTab('Dashboard');
                    })
                    .then(function() {
                        return common.assertElementContainsText('.warnings-block',
                            'Networks verification', 'Network verification warning is shown');
                    })
                    .then(function() {
                        return dashboardPage.discardChanges();
                    });
            },
            'Capacity table tests': function() {
                return this.remote
                    .then(function() {
                        return common.addNodesToCluster(1, ['Controller', 'Storage - Cinder']);
                    })
                    .then(function() {
                        return common.addNodesToCluster(2, ['Compute']);
                    })
                    .then(function() {
                        return clusterPage.goToTab('Dashboard');
                    })
                    .then(function() {
                        return common.isIntegerContentPositive('.capacity-items .cpu .capacity-value', 'CPU');
                    })
                    .then(function() {
                        return common.isIntegerContentPositive('.capacity-items .hdd .capacity-value', 'HDD');
                    })
                    .then(function() {
                        return common.isIntegerContentPositive('.capacity-items .ram .capacity-value', 'RAM');
                    })
                    .then(function() {
                        return dashboardPage.discardChanges();
                    });
            },
            'Test statistics update': function() {
                this.timeout = 90000;
                var controllerNodes = 3,
                    storageCinderNodes = 1,
                    computeNodes = 2,
                    operatingSystemNodes = 1,
                    virtualNodes = 1,
                    valueSelector = '.statistics-block .cluster-info-value',
                    total = controllerNodes + storageCinderNodes + computeNodes + operatingSystemNodes + virtualNodes;
                return this.remote
                    .then(function() {
                        return common.addNodesToCluster(controllerNodes, ['Controller']);
                    })
                    .then(function() {
                        return common.addNodesToCluster(storageCinderNodes, ['Storage - Cinder']);
                    })
                    .then(function() {
                        return common.addNodesToCluster(computeNodes, ['Compute']);
                    })
                    .then(function() {
                        return common.addNodesToCluster(operatingSystemNodes, ['Operating System'], {error: true});
                    })
                    .then(function() {
                        return common.addNodesToCluster(virtualNodes, ['Virtual'], {offline: true});
                    })
                    .then(function() {
                        return clusterPage.goToTab('Dashboard');
                    })
                    .then(function() {
                        return common.isElementTextEqualTo(valueSelector + '.total',
                            total,
                            'The number of Total nodes in statistics is updated according to added nodes');
                    })
                    .then(function() {
                        return common.isElementTextEqualTo(valueSelector + '.controller',
                            controllerNodes,
                            'The number of controllerNodes nodes in statistics is updated according to added nodes');
                    })
                    .then(function() {
                        return common.isElementTextEqualTo(valueSelector + '.compute',
                            computeNodes,
                            'The number of Compute nodes in statistics is updated according to added nodes');
                    })
                    .then(function() {
                        return common.isElementTextEqualTo(valueSelector + '.base-os',
                            operatingSystemNodes,
                            'The number of Operating Systems nodes in statistics is updated according to added nodes');
                    })
                    .then(function() {
                        return common.isElementTextEqualTo(valueSelector + '.virt',
                            virtualNodes,
                            'The number of Virtual nodes in statistics is updated according to added nodes');
                    })
                    .then(function() {
                        return common.isElementTextEqualTo(valueSelector + '.offline',
                            1,
                            'The number of Offline nodes in statistics is updated according to added nodes');
                    })
                    .then(function() {
                        return common.isElementTextEqualTo(valueSelector + '.error',
                            1,
                            'The number of Error nodes in statistics is updated according to added nodes');
                    })
                    .then(function() {
                        return common.isElementTextEqualTo(valueSelector + '.pending_addition',
                            total,
                            'The number of Pending Addition nodes in statistics is updated according to added nodes');
                    })
                    .then(function() {
                        return dashboardPage.discardChanges();
                    });
            },
            'Testing error nodes in cluster deploy': function() {
                return this.remote
                    .clickByCssSelector('.btn-add-nodes')
                    .then(function() {
                        return clusterPage.checkNodeRoles('Controller');
                    })
                    .then(function() {
                        return clusterPage.checkErrorNode();
                    })
                    .clickByCssSelector('button.btn-apply')
                    .waitForElementDeletion('button.btn-apply', 1000)
                    .then(function() {
                        return clusterPage.goToTab('Dashboard');
                    })
                    .then(function() {
                        return common.isElementTextEqualTo('.statistics-block .cluster-info-value.error',
                            1, 'Error node is reflected in Statistics block');
                    })
                    .then(function() {
                        return dashboardPage.startDeployment();
                    })
                    .waitForElementDeletion('.deploy-block .progress', 10000)
                    .waitForCssSelector('.dashboard-tab .alert strong', 1000)
                    .then(function() {
                        return common.isElementTextEqualTo('.dashboard-tab .alert strong', 'Error',
                            'Deployment failed in case of adding offline nodes');
                    });
            },
            'VCenter warning appears': function() {
                var vCenterClusterName = clusterName + 'VCenter test';
                return this.remote
                    .clickLinkByText('Environments')
                    // needed here to wait for transition
                    .waitForCssSelector('a.clusterbox', 2000)
                    .then(function() {
                        return common.createCluster(
                            vCenterClusterName,
                            {
                                Compute: function() {
                                    // Selecting VCenter
                                    return this.remote
                                        .clickByCssSelector('.custom-tumbler input[name=vcenter]');
                                }
                            }
                        );
                    })
                    .then(function() {
                        return common.addNodesToCluster(1, ['Controller']);
                    })
                    .then(function() {
                        return clusterPage.goToTab('Dashboard');
                    })
                    .then(function() {
                        return common.assertElementContainsText('.warnings-block',
                            'VMware settings are invalid', 'VMware warning is shown');
                    })
                    .then(function() {
                        return dashboardPage.discardChanges();
                    });
            }
        };
    });
});
