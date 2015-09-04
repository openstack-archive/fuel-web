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
    'intern/chai!assert',
    '../../helpers',
    'tests/functional/pages/login',
    'tests/functional/pages/welcome',
    'tests/functional/pages/cluster',
    'tests/functional/pages/clusters'
],
    function(_, assert, Helpers, LoginPage, WelcomePage, ClusterPage, ClustersPage) {
    'use strict';
        function CommonMethods(remote) {
            this.remote = remote;
            this.loginPage = new LoginPage(remote);
            this.welcomePage = new WelcomePage(remote);
            this.clusterPage = new ClusterPage(remote);
            this.clustersPage = new ClustersPage(remote);
        }

        CommonMethods.prototype = {
            constructor: CommonMethods,
            pickRandomName: function(prefix) {
                return (prefix || 'Item') + ' #' + _.random(1000, 9999);
            },
            getOut: function() {
                var self = this;
                return this.remote
                    .then(function() {
                        return self.welcomePage.skip();
                    })
                    .then(function() {
                        return self.loginPage.logout();
                    });
            },
            getIn: function() {
                var self = this;
                return this.remote
                    .then(function() {
                        return self.loginPage.logout();
                    })
                    .then(function() {
                        return self.loginPage.login();
                    })
                    .waitForDeletedByClassName('login-btn')
                    .then(function() {
                        return self.welcomePage.skip();
                    });
            },
            clickLink: function(text) {
                return this.remote
                    .setFindTimeout(1000)
                    .findByLinkText(text)
                        .click()
                        .end();
            },
            waitForElementDeletion: function(cssSelector) {
                return this.remote
                    .setFindTimeout(5000)
                    .waitForDeletedByCssSelector(cssSelector)
                    .catch(function(error) {
                        if (error.name != 'Timeout')
                            throw error;
                    })   // For cases when element is destroyed already
                    .findAllByCssSelector(cssSelector)
                        .then(function(elements) {
                            if (elements.length)
                                throw new Error('Element ' + cssSelector + ' was not destroyed');
                        });
            },
            goToEnvironment: function(clusterName, tabName) {
                var self = this;
                return this.remote
                    .then(function() {
                        return self.clickLink('Environments');
                    })
                    .then(function() {
                        return self.clustersPage.goToEnvironment(clusterName);
                    })
                    .then(function() {
                        if (tabName) return self.clusterPage.goToTab(tabName);
                    });
            },
            createCluster: function(clusterName, stepsMethods) {
                var self = this;
                return this.remote
                    .then(function() {
                        return self.clickLink('Environments');
                    })
                    .then(function() {
                        return self.clustersPage.createCluster(clusterName, stepsMethods);
                    });
            },
            removeCluster: function(clusterName, suppressErrors) {
                var self = this;
                return this.remote
                    .then(function() {
                        return self.clickLink('Environments');
                    })
                    .then(function() {
                        return self.clustersPage.goToEnvironment(clusterName);
                    })
                    .then(function() {
                        return self.clusterPage.removeCluster(clusterName);
                    })
                    .catch(function() {
                        if (!suppressErrors) throw new Error('Unable to delete cluster ' + clusterName);
                    });
            },
            doesClusterExist: function(clusterName) {
                var self = this;
                return this.remote
                    .setFindTimeout(2000)
                    .then(function() {
                        return self.clickLink('Environments');
                    })
                    .findAllByCssSelector(self.clustersPage.clusterSelector)
                    .then(function(divs) {
                        return divs.reduce(function(matchFound, element) {
                            return element.getVisibleText().then(
                                function(name) {
                                    return (name === clusterName) || matchFound;
                                }
                            )}, false);
                    });
            },
            addNodesToCluster: function(nodesAmount, nodesRoles) {
                var self = this;
                return this.remote
                    .then(function() {
                        return self.clusterPage.goToTab('Nodes');
                    })
                    .findByCssSelector('button.btn-add-nodes')
                        .click()
                        .end()
                    .findByCssSelector('div.role-panel')
                        .end()
                    .then(function() {
                        return self.clusterPage.checkNodeRoles(nodesRoles);
                    })
                    .then(function() {
                        return self.clusterPage.checkNodes(nodesAmount);
                    })
                    .findByCssSelector('button.btn-apply')
                        .click()
                        .end()
                    .setFindTimeout(2000)
                    .findByCssSelector('button.btn-add-nodes')
                        .end();
            },
            doesCssSelectorContainText: function(cssSelector, searchedText) {
                return this.remote
                    .findAllByCssSelector(cssSelector)
                    .then(function(messages) {
                        return messages.reduce(function(result, message) {
                            return message.getVisibleText().then(function(visibleText) {
                                return visibleText == searchedText || result;
                            });
                        }, false)
                    });
            },
            setInputValue: function(cssSelector, value) {
                return this.remote
                    .findByCssSelector(cssSelector)
                        .clearValue()
                        .type(value)
                        .end();
            },
            isElementEnabled: function(cssSelector, message) {
                return this.remote
                    .findByCssSelector(cssSelector)
                        .isEnabled()
                        .then(function(isEnabled) {
                            return assert.isTrue(isEnabled, message);
                        })
                        .end();
            },
            isElementDisabled: function(cssSelector, message) {
                return this.remote
                    .findByCssSelector(cssSelector)
                        .isEnabled()
                        .then(function(isEnabled) {
                            return assert.isFalse(isEnabled, message);
                        })
                        .end();
            },
            elementExists: function(cssSelector, message) {
                return this.remote
                    .findAllByCssSelector(cssSelector)
                        .then(function(elements) {
                            return assert.equal(elements.length, 1, message);
                        })
                        .end();
            },
            elementNotExists: function(cssSelector, message) {
                return this.remote
                    .findAllByCssSelector(cssSelector)
                        .then(function(elements) {
                            return assert.equal(elements.length, 0, message);
                        })
                        .end();
            }
        };
        return CommonMethods;
});
