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
    'tests/functional/pages/draganddrop'
], function(_, DragAndDrop) {
    'use strict';
    function InterfacesPage(remote) {
        this.remote = remote;
        this.dragAndDrop = new DragAndDrop(remote);
    }

    InterfacesPage.prototype = {
        constructor: InterfacesPage,
        findInterfaceElement: function(ifcName) {
            return this.remote
                .findAllByCssSelector('div.ifc-inner-container')
                .then(function(ifcElements) {
                    return ifcElements.reduce(function(result, ifcElement) {
                        return ifcElement
                            .findByCssSelector('div.ifc-name')
                            .then(function(ifcDiv) {
                                return ifcDiv
                                    .getVisibleText()
                                    .then(function(currentIfcName) {
                                        return currentIfcName == ifcName ? ifcElement : result;
                                    });
                            })
                    }, null);
                });
        },
        assignNetworkToInterface: function(networkName, ifcName) {
            var self = this;
            return this.dragAndDrop
                .findAllByCssSelector('div.network-block')
                .then(function(networkElements) {
                    return networkElements.reduce(function(result, networkElement) {
                        return networkElement
                            .getVisibleText()
                            .then(function(currentNetworkName) {
                                return currentNetworkName == networkName ? networkElement : result;
                            })
                    }, null);
                })
                .then(function(networkElement) {
                    return this.parent
                        .dragFrom(networkElement)
                        .end();
                })
                .then(function() {
                    return self.findInterfaceElement(ifcName);
                })
                .then(function(ifcElement) {
                    return this.parent
                        .dragTo(ifcElement)
                        .end();
                });
        }
    };
    return InterfacesPage;
});
