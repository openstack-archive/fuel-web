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
    'tests/functional/pages/disks'
], function(registerSuite, assert, Common, NodeDisks) {
    'use strict';

    registerSuite(function() {
        var common,
            disks,
            clusterName,
            cancelButton, applyButton, loadDefaultsButton,
            initialImageSize, expectedDisksNumber;

        return {
            name: 'Node Disk',
            setup: function() {
                common = new Common(this.remote);
                disks = new NodeDisks(this.remote);
                clusterName = common.pickRandomName('Test Cluster');
                expectedDisksNumber = 6;

                return this.remote
                    .then(function() {
                        return common.getIn();
                    })
                    .then(function() {
                        return common.createCluster(clusterName);
                    })
                    .then(function() {
                        return common.addNodesToCluster(1, ['Controller']);
                    })
                    .then(function() {
                        return disks.goToNodeDisks();
                    })
                    .findByCssSelector(disks.sdaDisk + ' input[type=number][name=image]')
                        // Get the Initial size of the Image Storage
                        .then(function(input) {
                            return input.getAttribute('value')
                                .then(function(value) {
                                    initialImageSize = value;
                                });
                        })
                        .end()
                    .then(function() {
                        cancelButton = disks.getButton('.btn-revert-changes');
                        applyButton = disks.getButton('.btn-apply');
                        loadDefaultsButton = disks.getButton('.btn-defaults');
                    });
            },
            teardown: function() {
                return this.remote
                    .then(function() {
                        return common.removeCluster(clusterName, true);
                    });
            },
            'Testing nodes disks layout': function() {
                return this.remote
                    .setFindTimeout(5000)
                    .findAllByCssSelector('.node-disks > .disk-box')
                        // Find all disks fo this Node
                        .then(function(elements) {
                            assert.isTrue(elements.length == expectedDisksNumber, 'Number of disks correct');
                        })
                        .end()
                    .then(function() {
                        return common.isElementDisabled('.btn-revert-changes', 'Cancel button is disabled');
                    })
                    .then(function() {
                        return common.isElementDisabled('.btn-apply', 'Apply button is disabled');
                    })
                    .then(function() {
                        return common.isElementEnabled('.btn-defaults', 'Load Defaults button is enabled');
                    });
            },
            'Testing nodes disk block layout': function() {
                return this.remote
                    .setFindTimeout(5000)
                    .findByCssSelector(disks.sdaDisk + ' .disk-visual [data-volume=os] .toggle')
                        // View SDA disk
                        .click()
                        .end()
                    .findByCssSelector(disks.sdaDiskOS + ' input')
                        .then(function(input) {
                            return input.getAttribute('value')
                                .then(function(value) {
                                    assert.ok(value, 'Base System is allocated on SDA disk');
                                });
                        })
                        .end()
                    .findByCssSelector(disks.sdaDiskImage + ' input')
                        .then(function(input) {
                            return input.getAttribute('value')
                                .then(function(value) {
                                    assert.ok(value, 'Image Storage is allocated on SDA disk');
                                });
                        })
                        .end()
                    .findAllByCssSelector(disks.sdaDisk + ' .disk-visual [data-volume=image] .close-btn')
                        .then(function(elements) {
                            assert.ok(elements.length, 'Button Close for Image Storage volume is present');
                        })
                        .end()
                    .findAllByCssSelector(disks.sdaDisk + ' .disk-visual [data-volume=os] .close-btn')
                        .then(function(elements) {
                            assert.notOk(elements.length, 'Button Close for Base system volume is not present');
                        })
                        .end();
            },
            'Testing Apply and Load Default buttons: interractions': function() {
                return this.remote
                    .setFindTimeout(5000)
                    .findByCssSelector(disks.sdaDisk + ' input[type=number][name=image]')
                        // Change the value of the Image Storage
                        .clearValue()
                        .type('80')
                        .end()
                    .then(function() {
                        return common.isElementEnabled('.btn-revert-changes', 'Cancel button is enabled');
                    })
                    .then(function() {
                        return common.isElementEnabled('.btn-apply', 'Apply button is enabled');
                    })
                    .then(function() {
                        return common.isElementEnabled('.btn-defaults', 'Load Defaults button is enabled');
                    })
                    .then(function() {
                        return applyButton.click();
                    })
                    .then(function() {
                        return common.waitForElementDeletion('.btn-load-defaults:disabled');
                    })
                    .then(function() {
                        return loadDefaultsButton.click();
                    })
                    .findByCssSelector(disks.sdaDisk + ' input[type=number][name=image]')
                        // Get Image Storage size after load default
                        .then(function(input) {
                            return input.getAttribute('value')
                                .then(function(value) {
                                    assert.isTrue(value == initialImageSize, 'Image Storage size restored to default');
                                });
                        })
                    .then(function() {
                        return common.isElementEnabled('.btn-revert-changes', 'Cancel button is enabled');
                    })
                    .then(function() {
                        return common.isElementEnabled('.btn-apply', 'Apply button is enabled');
                    })
                    .then(function() {
                        return applyButton.click();
                    });
            },
            'Testing volume group deletion and Cancel button': function() {
                return this.remote
                    .setFindTimeout(5000)
                    .findByCssSelector(disks.sdaDisk + ' .disk-visual [data-volume=image]')
                        // Check that visualisation div for Image Storage present and has positive width
                        .then(function(element) {
                            return element.getSize()
                                .then(function(size) {
                                    assert.isTrue(size.width > 0, 'Expected positive width for Image Storage visual');
                                });
                        })
                        .end()
                    .findByCssSelector(disks.sdaDisk + ' .disk-visual [data-volume=image] .close-btn')
                        // Delete Image Storage volume
                        .click()
                        .end()
                    .then(function() {
                        return common.isElementEnabled('.btn-apply', 'Apply button is enabled');
                    })
                    .findByCssSelector(disks.sdaDisk + ' .disk-visual [data-volume=image]')
                        // Check that visualisation div for Image Storage present and has width = 0
                        .then(function(element) {
                            return element.getSize()
                                .then(function(size) {
                                    assert.isTrue(size.width == 0, 'Expected null width for Image Storage visual');
                                });
                        })
                        .end()
                    .findByCssSelector(disks.sdaDisk + ' .disk-visual [data-volume=unallocated]')
                        // Check that there is unallocated space after Image Storage removal
                        .then(function(element) {
                            return element.getSize()
                                .then(function(size) {
                                    assert.isTrue(size.width > 0, 'There is unallocated space after Image Storage removal');
                                });
                        })
                        .end()
                    .findByCssSelector(disks.sdaDisk + ' input[type=number][name=image]')
                        // Get Image Storage size after deletion, check that this value = 0
                        .then(function(input) {
                            return input.getAttribute('value')
                                .then(function(value) {
                                    assert.isTrue(value == 0, 'Image Storage volume was removed successfully');
                                });
                        })
                        .end()
                    .then(function() {
                        return cancelButton.click();
                    })
                    .findByCssSelector(disks.sdaDisk + ' input[type=number][name=image]')
                        // Get Image Storage size after load default
                        .then(function(input) {
                            return input.getAttribute('value')
                                .then(function(value) {
                                    assert.isTrue(value == initialImageSize, 'Image Storage volume control contains correct value');
                                });
                        })
                        .end()
                    .then(function() {
                        return common.isElementDisabled('.btn-apply', 'Apply button is disabled');
                    });
            }
        };
    });
});
