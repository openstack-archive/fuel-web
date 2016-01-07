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
/*eslint object-shorthand: 0*/
define([
    'intern/dojo/node!lodash',
    'intern/chai!assert'
], function(_, assert) {
    'use strict';
    function InterfacesPage(remote) {
        this.remote = remote;
    }

    InterfacesPage.prototype = {
        constructor: InterfacesPage,
        findInterfaceElement: function(ifcName) {
            return this.remote
                .findAllByCssSelector('div.ifc-inner-container')
                    .then(function(ifcElements) {
                        return ifcElements.reduce(function(result, ifcElement) {
                            return ifcElement
                                .findByCssSelector('.ifc-name')
                                    .then(function(ifcDiv) {
                                        return ifcDiv
                                            .getVisibleText()
                                                .then(function(currentIfcName) {
                                                    return _.trim(currentIfcName) == ifcName ? ifcElement : result;
                                                });
                                    });
                        }, null);
                    });
        },
        findInterfaceElementInBond: function(ifcName) {
            return this.remote
                .findAllByCssSelector('.ifc-info-block')
                    .then(function(ifcsElements) {
                        return ifcsElements.reduce(function(result, ifcElement) {
                            return ifcElement
                                .findByCssSelector('.ifc-name')
                                    .then(function(ifcNameElement) {
                                        return ifcNameElement
                                            .getVisibleText()
                                                .then(function(foundIfcName) {
                                                    return ifcName == foundIfcName ? ifcElement : result;
                                                });
                                    });
                        }, null);
                    });
        },
        removeInterfaceFromBond: function(ifcName) {
            var self = this;
            return this.remote
                .then(function() {
                    return self.findInterfaceElementInBond(ifcName);
                })
                .then(function(ifcElement) {
                    return ifcElement
                        .findByCssSelector('.ifc-info > .btn-link')
                            .then(function(btnRemove) {
                                return btnRemove.click();
                            });
                });
        },
        assignNetworkToInterface: function(networkName, ifcName) {
            var self = this;
            return this.remote
                .findAllByCssSelector('div.network-block')
                    .then(function(networkElements) {
                        return networkElements.reduce(function(result, networkElement) {
                            return networkElement
                                .getVisibleText()
                                    .then(function(currentNetworkName) {
                                        return currentNetworkName == networkName ? networkElement : result;
                                    });
                        }, null);
                    })
                    .then(function(networkElement) {
                        return this.parent.dragFrom(networkElement);
                    })
                    .then(function() {
                        return self.findInterfaceElement(ifcName);
                    })
                    .then(function(ifcElement) {
                        return this.parent.dragTo(ifcElement);
                    });
        },
        selectInterface: function(ifcName) {
            var self = this;
            return this.remote
                .then(function() {
                    return self.findInterfaceElement(ifcName);
                })
                .then(function(ifcElement) {
                    if (!ifcElement) throw new Error('Unable to select interface ' + ifcName);
                    return ifcElement
                        .findByCssSelector('input[type=checkbox]:not(:checked)')
                            .then(function(ifcCheckbox) {
                                return ifcCheckbox.click();
                            });
                });
        },
        bondInterfaces: function(ifc1, ifc2) {
            var self = this;
            return this.remote
                .then(function() {
                    return self.selectInterface(ifc1);
                })
                .then(function() {
                    return self.selectInterface(ifc2);
                })
                .clickByCssSelector('.btn-bond');
        },
        checkBondInterfaces: function(bondName, ifcsNames) {
            var self = this;
            return this.remote
                .then(function() {
                    return self.findInterfaceElement(bondName);
                })
                .then(function(bondElement) {
                    ifcsNames.push(bondName);
                    return bondElement
                        .findAllByCssSelector('.ifc-name')
                            .then(function(ifcNamesElements) {
                                assert.equal(ifcNamesElements.length, ifcsNames.length, 'Unexpected number of interfaces in bond');

                                return ifcNamesElements.forEach(
                                    function(ifcNameElement) {
                                        return ifcNameElement
                                            .getVisibleText()
                                                .then(function(name) {
                                                    name = _.trim(name);
                                                    if (!_.contains(ifcsNames, name))
                                                        throw new Error('Unexpected name in bond: ' + name);
                                                });
                                    });
                            });
                });
        }
    };
    return InterfacesPage;
});
