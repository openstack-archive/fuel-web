define([
    'underscore',
    'intern/node_modules/dojo/node!fs',
    '../../helpers',
    'tests/functional/pages/login',
    'tests/functional/pages/welcome',
    'tests/functional/pages/cluster',
    'tests/functional/pages/clusters'
],
    function(_, fs, Helpers, LoginPage, WelcomePage, ClusterPage, ClustersPage) {
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
            takeScreenshot: function(filename, error) {
                return this.remote
                    .takeScreenshot()
                    .then(function(buffer) {
                        if (!filename) {
                            filename = new Date().toTimeString();
                        }
                        fs.writeFileSync('/tmp/' + filename + '.png', buffer);
                        if (error) {
                            throw error;
                        }
                });
            },
            getOut: function() {
                var that = this;
                return this.remote
                    .then(function() {
                        return that.welcomePage.skip();
                    })
                    .then(function() {
                        return that.loginPage.logout();
                    });
            },
            getIn: function() {
                var that = this;
                return this.remote
                    .then(function() {
                        return that.loginPage.logout();
                    })
                    .then(function() {
                        return that.loginPage.login();
                    })
                    .waitForDeletedByClassName('login-btn')
                    .then(function() {
                        return that.welcomePage.skip();
                    });
            },
            clickLink: function(text) {
                return this.remote
                    .setFindTimeout(1000)
                    .findByLinkText(text)
                        .click()
                        .end();
            },
            waitForModal: function() {
                return this.remote
                    .setFindTimeout(2000)
                    .findByCssSelector('div.modal-content')
                        .end();
            },
            closeModal: function() {
                return this.remote
                    .findByCssSelector('.modal-header button.close')
                        .click()
                        .end();
            },
            waitForElementDeletion: function(cssSelector) {
                return this.remote
                    .setFindTimeout(2000)
                    .waitForDeletedByCssSelector(cssSelector)
                    .catch()   // For cases when element is destroyed already
                    .findByCssSelector(cssSelector)
                        .then(function() {
                            throw new Error('Element ' + cssSelector + ' was not destroyed');
                        }, _.constant(true));
            },
            waitForModalToClose: function() {
                return this.waitForElementDeletion('div.modal-content');
            },
            goToEnvironment: function(clusterName, tabName) {
                var that = this;
                return this.remote
                    .then(function() {
                        return that.clickLink('Environments');
                    })
                    .then(function() {
                        return that.clustersPage.goToEnvironment(clusterName);
                    })
                    .then(function() {
                        if (tabName) return that.clusterPage.goToTab(tabName);
                    });
            },
            createCluster: function(clusterName) {
                var that = this;
                return this.remote
                    .then(function() {
                        return that.clickLink('Environments');
                    })
                    .then(function() {
                        return that.clustersPage.createCluster(clusterName);
                    });
            },
            removeCluster: function(clusterName, suppressErrors) {
                var that = this;
                return this.remote
                    .then(function() {
                        return that.clickLink('Environments');
                    })
                    .then(function() {
                        return that.clustersPage.goToEnvironment(clusterName);
                    })
                    .then(function() {
                        return that.clusterPage.removeCluster();
                    })
                    .catch(function() {
                        if (!suppressErrors) throw new Error('Unable to delete cluster ' + clusterName);
                    });
            },
            doesClusterExist: function(clusterName) {
                var that = this;
                return this.remote
                    .setFindTimeout(2000)
                    .then(function() {
                        return that.clickLink('Environments');
                    })
                    .findAllByCssSelector(that.clustersPage.clusterSelector)
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
                var that = this;
                return this.remote
                    .setFindTimeout(5000)
                    .findByCssSelector('a.btn-add-nodes')
                        .click()
                        .end()
                    .findByCssSelector('div.role-panel')
                        .end()
                    .then(function() {
                        return that.clusterPage.checkNodeRoles(nodesRoles);
                    })
                    .then(function() {
                        return that.clusterPage.checkNodes(nodesAmount);
                    })
                    .findByCssSelector('button.btn-apply')
                        .click()
                        .end()
                    .setFindTimeout(2000)
                    .findByCssSelector('button.btn-add-nodes')
                        .end();
            }
        };
        return CommonMethods;
});
