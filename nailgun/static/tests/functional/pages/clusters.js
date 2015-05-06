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

define([], function() {
    'use strict';
    function ClustersPage(remote) {
        this.remote = remote;
    }

    ClustersPage.prototype = {
        constructor: ClustersPage,
        createCluster: function(clusterName) {
            return this.remote
                .setFindTimeout(1000)
                .findByClassName('create-cluster')
                    .click()
                    .end()
                .setFindTimeout(2000)
                .findByCssSelector('div.modal-content')
                .findByName('name')
                    .clearValue()
                    .type(clusterName)
                    .pressKeys('\uE007')
                    .pressKeys('\uE007')
                    .pressKeys('\uE007')
                    .pressKeys('\uE007')
                    .pressKeys('\uE007')
                    .pressKeys('\uE007')
                    .pressKeys('\uE007')
                    .end()
                .setFindTimeout(4000)
                .waitForDeletedByCssSelector('div.modal-content')
                    .end();
        },
        clusterSelector: '.clusterbox div.name',
        goToEnvironment: function(clusterName) {
            var that = this;
            return this.remote
                .setFindTimeout(5000)
                .findAllByCssSelector(that.clusterSelector)
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
