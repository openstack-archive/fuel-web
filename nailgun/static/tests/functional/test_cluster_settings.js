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
    'tests/functional/pages/settings',
    'tests/functional/pages/modal'
], function(registerSuite, assert, Common, ClusterPage, SettingsPage, ModalWindow) {
    'use strict';

    registerSuite(function() {
        var common,
            clusterPage,
            settingsPage,
            modal,
            clusterName;

        return {
            name: 'Settings tab',
            setup: function() {
                common = new Common(this.remote);
                clusterPage = new ClusterPage(this.remote);
                settingsPage = new SettingsPage(this.remote);
                modal = new ModalWindow(this.remote);
                clusterName = common.pickRandomName('Test Cluster');

                return this.remote
                    .then(function() {
                        return common.getIn();
                    })
                    .then(function() {
                        return common.createCluster(clusterName);
                    })
                    .then(function() {
                        return clusterPage.goToTab('Settings');
                    })
                    // go to Common subtab to use checkboxes for tests
                    .findByCssSelector('a.subtab-link-common')
                        .click()
                        .end();
            },
            teardown: function() {
                return this.remote
                    // reset changes if any
                    .findByCssSelector('.btn-revert-changes')
                        .click()
                        .end()
                    .then(function() {
                        return common.removeCluster(clusterName);
                    });
            },
            'Settings tab is rendered correctly': function() {
                return this.remote
                    .setFindTimeout(5000)
                    .then(function() {
                        return common.isElementEnabled('.btn-load-defaults', 'Load defaults button is enabled');
                    })
                    .then(function() {
                        return common.isElementDisabled('.btn-revert-changes', 'Cancel Changes button is disabled');
                    })
                    .then(function() {
                        return common.isElementDisabled('.btn-apply-changes', 'Save Settings button is disabled');
                    });
            },
            'Check Save Settings button': function() {
                return this.remote
                    .setFindTimeout(5000)
                    .findByCssSelector('input[type=checkbox]')
                        // introduce change
                        .click()
                        .then(function() {
                            return common.isElementEnabled('.btn-apply-changes', 'Save Settings button is enabled');
                        })
                        // reset the change
                        .click()
                        .then(function() {
                            return common.isElementDisabled('.btn-apply-changes', 'Save Settings button is disabled');
                        })
                        .end();
            },
            'Check Cancel Changes button': function() {
                return this.remote
                    .setFindTimeout(5000)
                    // introduce change
                    .findByCssSelector('input[type=checkbox]')
                        .click()
                        .end()
                    .then(function() {
                        // try to move out of Settings tab
                        return clusterPage.goToTab('Dashboard');
                    })
                    .then(function() {
                        // check Discard Chasnges dialog appears
                        return modal.waitToOpen();
                    })
                    .then(function() {
                        return modal.close();
                    })
                    // reset changes
                    .findByCssSelector('.btn-revert-changes')
                        .click()
                        .end()
                    .then(function() {
                        return common.isElementDisabled('.btn-apply-changes', 'Save Settings button is disabled after changes were cancelled');
                    });
            },
            'Check changes saving': function() {
                return this.remote
                    .setFindTimeout(5000)
                    // introduce change
                    .findByCssSelector('input[type=checkbox]')
                        .click()
                        .end()
                    .then(function() {
                        return common.isElementEnabled('.btn-apply-changes', 'Save Settings button is enabled');
                    })
                    // save changes
                    .findByCssSelector('.btn-apply-changes')
                        .click()
                        .end()
                    .then(function() {
                        return settingsPage.waitForRequestCompleted();
                    })
                    .then(function() {
                        return common.isElementDisabled('.btn-revert-changes', 'Cancel changes button is disabled after changes were saved successfully');
                    });
            },
            'Check loading of defaults': function() {
                return this.remote
                    .setFindTimeout(5000)
                    // load defaults
                    .findByCssSelector('.btn-load-defaults')
                        .click()
                        .end()
                    .then(function() {
                        return settingsPage.waitForRequestCompleted();
                    })
                    .then(function() {
                        return common.isElementEnabled('.btn-apply-changes', 'Save Settings button is enabled after defaults were loaded');
                    })
                    .then(function() {
                        return common.isElementEnabled('.btn-revert-changes', 'Cancel changes button is enabled after defaults were loaded');
                    });
            }
        };
    });
});
