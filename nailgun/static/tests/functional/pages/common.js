define([
    'intern/node_modules/dojo/node!fs',
    '../../helpers',
    'tests/functional/pages/login',
    'tests/functional/pages/welcome',
    'tests/functional/pages/clusters'
],
    function(fs, Helpers, LoginPage, WelcomePage, ClustersPage) {

    'use strict';
        function CommonMethods(remote) {
            this.remote = remote;
            this.loginPage = new LoginPage(remote);
            this.welcomePage = new WelcomePage(remote);
            this.clustersPage = new ClustersPage(remote);
        }

        CommonMethods.prototype = {
            constructor: CommonMethods,
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
            goToEnvironment: function(clusterName) {
                var that = this;
                return this.remote
                    .then(function() {
                        return that.clickLink('Environments');
                    })
                    .then(function() {
                        return that.clustersPage.goToEnvironment(clusterName);
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
                        return that.clustersPage.removeCluster(clusterName, suppressErrors);
                    });
            },
            doesClusterExist: function(clusterName) {
                var that = this;
                return this.remote
                    .setFindTimeout(2000)
                    .then(function() {
                        return that.clickLink('Environments');
                    })
                    .findAllByCssSelector('div.cluster-name')
                    .then(function(divs) {
                        return divs.reduce(function(matchFound, element) {
                            return element.getVisibleText().then(
                                function(name) {
                                    return (name === clusterName) || matchFound;
                                }
                            )}, false);
                    });
            }
        };
        return CommonMethods;
});
