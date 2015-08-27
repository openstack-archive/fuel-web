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

define(['underscore', 'tests/functional/pages/modal'], function(_, ModalWindow) {
    'use strict';
    function ClustersPage(remote) {
        this.remote = remote;
        this.modal = new ModalWindow(remote);
    }

    ClustersPage.prototype = {
        constructor: ClustersPage,
        createCluster: function(clusterName, stepsMethods) {
            var self = this,
                stepMethod = function(stepName) {
                    return _.bind(_.get(stepsMethods, stepName, _.noop), self);
                };
            return this.remote
                .setFindTimeout(1000)
                .findByClassName('create-cluster')
                    .click()
                    .end()
                .then(function() {
                    return self.modal.waitToOpen();
                })
                // Name and release
                .findByName('name')
                    .clearValue()
                    .type(clusterName)
                    .end()
                .then(stepMethod('Name and Release'))
                .pressKeys('\uE007')
                // Compute
                .then(stepMethod('Compute'))
                .pressKeys('\uE007')
                // Networking Setup
                .then(stepMethod('Networking Setup'))
                .pressKeys('\uE007')
                //Storage Backends
                .then(stepMethod('Storage Backends'))
                .pressKeys('\uE007')
                // Additional Services
                .then(stepMethod('Additional Services'))
                .pressKeys('\uE007')
                // Finish
                .pressKeys('\uE007')
                .then(function() {
                    return self.modal.waitToClose();
                });
        },
        clusterSelector: '.clusterbox div.name',
        goToEnvironment: function(clusterName) {
            var self = this;
            return this.remote
                .setFindTimeout(5000)
                .findAllByCssSelector(self.clusterSelector)
                .then(function(divs) {
                    return divs.reduce(
                        function(matchFound, element) {
                            return element.getVisibleText().then(
                                function(name) {
                                    if (name === clusterName) {
                                        element.click();
                                        return true;
                                    }
                                    return matchFound;
                                }
                            )},
                            false
                        );
                })
                .then(function(result) {
                    if (!result) {
                        throw new Error('Cluster ' + clusterName + ' not found');
                    }
                    return true;
                });
        }
    };
    return ClustersPage;
});
