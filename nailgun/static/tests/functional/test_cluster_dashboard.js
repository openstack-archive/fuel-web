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
            'Add nodes button is present and works on freshly created cluster': function() {
                return this.remote
                    .then(function() {
                        return common.elementExists(dashboardPage.addNodesButtonSelector, 'Add nodes button is visible on new cluster');
                    })
                    .findByCssSelector(dashboardPage.addNodesButtonSelector)
                        .click()
                        .end()
                    .getCurrentUrl()
                        .then(function(url) {
                            assert.isTrue(_.contains(url, 'nodes/add'), 'Add nodes button navigates from Dashboard to Add nodes screen');
                        })
            },
            'Renaming cluster works': function() {
                var initialName = clusterName,
                    newName = clusterName + '!!!';
                return this.remote
                    .then(function() {
                        return dashboardPage.startClusterRenaming();
                    })
                    .then(function() {
                        return common.elementExists(dashboardPage.renameInputSelector, 'Rename control appears');
                    })
                    .findByCssSelector(dashboardPage.renameInputSelector)
                        // Escape
                        .type('')
                        .end()
                    .then(function() {
                        return common.elementNotExists(dashboardPage.renameInputSelector, 'Rename control disappears');
                    })
                    .then(function() {
                        return dashboardPage.getClusterName()
                            .then(function(text) {
                                assert.isTrue(text == initialName, 'Switching rename control does not change cluster name');
                            })
                            .end()
                    })
                    .then(function() {
                        return dashboardPage.setClusterName(newName)
                            .end()
                    })
                    .then(function() {
                        return dashboardPage.getClusterName()
                            .then(function(text) {
                                assert.isFalse(text == initialName, 'New cluster name is not equal to the initial');
                                assert.isTrue(text == newName, 'New name is applied');
                            })
                    })
                    .then(function() {
                        return dashboardPage.setClusterName(initialName);
                    });
            },
            'Adding node manipulations': function() {
                return this.remote
                    .then(function() {
                        return common.addNodesToCluster(1, ['Controller']);
                    })
                    .then(function() {
                        return clusterPage.goToTab('Dashboard');
                    })
                    .then(function() {
                        return common.elementExists(dashboardPage.deployButtonSelector, 'Deploy button is visible after adding Controller node');
                    })
                    .then(function() {
                        return dashboardPage.discardChanges();
                    })
                    .then(function() {
                        return common.elementNotExists(dashboardPage.deployButtonSelector, 'Deploy button is not visible after adding Controller node');
                    })
            },
            'Provision button availability': function() {
                return this.remote
                    .then(function() {
                        return common.addNodesToCluster(1, ['Virtual']);
                    })
                    .then(function() {
                        return clusterPage.goToTab('Dashboard');
                    })
                    .findByCssSelector(dashboardPage.deployButtonSelector)
                        .getVisibleText()
                            .then(function(text) {
                                assert.isTrue(text == 'Provision VMs', 'Text is changed');
                            })
                        .getAttribute('class')
                            .then(function(classNames) {
                                assert.isTrue(_.contains(classNames, 'provision-vms'), 'Class name is correct');
                            })
                        .end()
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
                    // No nodes added - so verification should fail
                    .findByCssSelector('.verify-networks-btn')
                        .click()
                        .end()
                    .then(function() {
                        return common.elementExists('.verification-box .alert-danger', 'Verification error appears');
                    })
                    .then(function() {
                        return clusterPage.goToTab('Dashboard');
                    })
                    .findByCssSelector('.warnings-block')
                        .getVisibleText()
                            .then(function(text) {
                                assert.isTrue(_.contains(text, 'Networks verification'), 'Network verification warning is shown');
                            })
                        .end()
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
                        return common.textIsGreaterThanZero('.capacity-items .cpu .capacity-value', 'CPU');
                    })
                    .then(function() {
                        return common.textIsGreaterThanZero('.capacity-items .hdd .capacity-value', 'HDD');
                    })
                    .then(function() {
                        return common.textIsGreaterThanZero('.capacity-items .ram .capacity-value', 'RAM');
                    })
                    .then(function() {
                        return dashboardPage.discardChanges();
                    });
            },
            'Test statistics update': function() {
                this.timeout = 90000;
                var controllers = 2,
                    storageCinders = 1,
                    computes = 1,
                    operatingSystems = 2,
                    virtuals = 2,
                    valueSelector = '.statistics-block .cluster-info-value',
                    total = controllers + storageCinders + computes + operatingSystems + virtuals;
                return this.remote
                    .then(function() {
                        return common.addNodesToCluster(controllers, ['Controller']);
                    })
                    .then(function() {
                        return common.addNodesToCluster(storageCinders, ['Storage - Cinder']);
                    })
                    .then(function() {
                        return common.addNodesToCluster(computes, ['Compute']);
                    })
                    .then(function() {
                        return common.addNodesToCluster(operatingSystems, ['Operating System']);
                    })
                    .then(function() {
                        return common.addNodesToCluster(virtuals, ['Virtual'], true);
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
                            controllers,
                            'The number of Controllers nodes in statistics is updated according to added nodes');
                    })
                    .then(function() {
                        return common.isElementTextEqualTo(valueSelector + '.compute',
                            computes,
                            'The number of Compute nodes in statistics is updated according to added nodes');
                    })
                    .then(function() {
                        return common.isElementTextEqualTo(valueSelector + '.base-os',
                            operatingSystems,
                            'The number of Operating Systems nodes in statistics is updated according to added nodes');
                    })
                    .then(function() {
                        return common.isElementTextEqualTo(valueSelector + '.virt',
                            virtuals,
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
                    .findByCssSelector('.btn-add-nodes')
                        .click()
                        .end()
                    .then(function() {
                        return clusterPage.checkNodeRoles('Controller');
                    })
                    .then(function() {
                        return clusterPage.checkErrorNode();
                    })
                    .findByCssSelector('button.btn-apply')
                        .click()
                        .end()
                    .then(function() {
                        return clusterPage.goToTab('Dashboard');
                    })
                    .then(function() {
                        return common.isElementTextEqualTo('.statistics-block .cluster-info-value.error',
                            1,
                            'Error node is reflected in Statistics block');
                    })
                    .then(function() {
                        return dashboardPage.startDeployment();
                    })
                    .findByCssSelector('.dashboard-tab .alert strong')
                        .getVisibleText()
                            .then(function(alertTitle) {
                                assert.equal(alertTitle, 'Error', 'Deployment failed in case of adding offline nodes');
                            })
                        .end();
            },
            'VCenter warning appears': function() {
                var tempName = clusterName + 'VCenter test';
                return this.remote
                    .then(function() {
                        return common.clickLink('Environments')
                    })
                    // needed here to wait for transition
                    .setFindTimeout(2000)
                    .then(function() {
                        return common.createCluster(
                            tempName,
                            {
                                Compute: function() {
                                    // Selecting VCenter
                                    return this.remote
                                        .findByCssSelector('.custom-tumbler input[name=vcenter]')
                                        .click()
                                        .end();
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
                    .findByCssSelector('.warnings-block')
                        .getVisibleText()
                        .then(function(text) {
                            return assert.isTrue(_.contains(text, 'VMware settings are invalid'), 'VMware warning is shown');
                        })
                        .end()
                    .then(function() {
                        return dashboardPage.discardChanges();
                    });
            }
        };
    });
});
