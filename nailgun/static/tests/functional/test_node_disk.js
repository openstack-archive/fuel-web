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
            cancelButton, applyButton, loadDefaultsButton;

        return {
            name: 'Node Disk',
            setup: function() {
                common = new Common(this.remote);
                disks = new NodeDisks(this.remote);
                clusterName = 'Test Cluster #' + Math.round(99999 * Math.random());

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
                    });
            },
            beforeEach: function() {
                cancelButton = common.getElement('.btn-revert-changes');
                applyButton = common.getElement('.btn-apply');
                loadDefaultsButton = common.getElement('.btn-defaults');
            },
            teardown: function() {
                return this.remote
                    .then(function() {
                        return common.removeCluster(clusterName, true);
                    });
            },
            'Testing nodes disks layout': function() {
                var expectedDisksNumber = 6;

                return this.remote
                    .setFindTimeout(5000)
                    .findByCssSelector('.edit-node-disks-screen')
                        // Check if "Edit Node Disks page" opens
                        .end()
                    .findAllByCssSelector('.node-disks > .disk-box')
                        // Find all disks fo this Node
                        .then(function(elements) {
                            assert.isTrue(elements.length == expectedDisksNumber, 'Number of disks correct');
                        })
                        .end()
                    .then(function() {
                        // Checking "Cancel" button is disabled
                        return cancelButton
                            .isEnabled()
                            .then(function(isEnabled) {
                                assert.isFalse(isEnabled, 'Cancel button is disabled');
                            });
                    })
                    .then(function() {
                        // Checking "Apply" button is disabled
                        return applyButton
                            .isEnabled()
                            .then(function(isEnabled) {
                                assert.isFalse(isEnabled, 'Apply button is disabled');
                            });
                    })
                    .then(function() {
                        // Checking "Load Defaults" button is enabled
                        return loadDefaultsButton
                            .isEnabled()
                            .then(function(isEnabled) {
                                assert.isTrue(isEnabled, 'Load Defaults button is enabled');
                            });
                    });
            },
            'Testing nodes disk block layout': function() {
                var sdaDisk = '.disk-box[data-disk=sda]',
                    sdaDiskOS = sdaDisk + ' .disk-utility-box [data-volume=os]',
                    sdaDiskImage = sdaDisk + ' .disk-utility-box [data-volume=image]';

                return this.remote
                    .setFindTimeout(5000)
                    .findByCssSelector(sdaDisk + ' .disk-visual [data-volume=os] .toggle')
                        // View SDA disk
                        .click()
                        .end()
                    .findByCssSelector(sdaDiskOS + ' input')
                        // Check if osSDA volume has positive size value
                        .then(function(input) {
                            return input.getAttribute('value')
                                .then(function(value) {
                                    assert.ok(value, 'Expected positive size value for osSDA');
                                })
                        })
                        .end()
                    .findByCssSelector(sdaDiskImage + ' input')
                        // Check if imageSDA volume has positive size value
                        .then(function(input) {
                            return input.getAttribute('value')
                                .then(function(value) {
                                    assert.ok(value, 'Expected positive size value for imageSDA');
                                })
                        })
                        .end()
                    .findByCssSelector(sdaDiskOS)
                        .end()
                    .findByCssSelector(sdaDiskImage)
                        .end()
                    .findAllByCssSelector(sdaDisk + ' .disk-visual [data-volume=image] .close-btn')
                        .then(function(elements) {
                            assert.ok(elements.length, 'Button Close for Image Storage volume is present');
                        })
                        .end()
                    .findAllByCssSelector(sdaDisk + ' .disk-visual [data-volume=os] .close-btn')
                        .then(function(elements) {
                            assert.notOk(elements.length, 'Button Close for Base system volume is not present');
                        })
                        .end();
            },
            'Testing Apply and Load Default buttons: interractions': function() {
                var sdaDisk = '.disk-box[data-disk=sda]',
                    initialImageSize;

                return this.remote
                    .setFindTimeout(5000)
                    .findByCssSelector(sdaDisk + ' input[type=number][name=image]')
                        // Get the initial size of the Image Storage
                        .then(function(input) {
                            return input.getAttribute('value')
                                .then(function(value) {
                                    initialImageSize = value;
                                    assert.ok(value, 'Expected positive size value for imageSDA');
                                })
                        })
                        // Change the value of the Image Storage
                        .clearValue()
                        .type('80')
                        .end()
                    .then(function() {
                        // Checking "Cancel" button is enabled now
                        return cancelButton
                            .isEnabled()
                            .then(function(isEnabled) {
                                assert.isTrue(isEnabled, 'Cancel button is enabled');
                            });
                    })
                    .then(function() {
                        // Checking "Apply" button is enabled now
                        return applyButton
                            .isEnabled()
                            .then(function(isEnabled) {
                                assert.isTrue(isEnabled, 'Apply button is enabled');
                            });
                    })
                    .then(function() {
                        // Checking "Load Defaults" button is enabled
                        return loadDefaultsButton
                            .isEnabled()
                            .then(function(isEnabled) {
                                assert.isTrue(isEnabled, 'Load Defaults button is enabled');
                            });
                    })
                    .then(function() {
                        // Click Load Defaults Button
                        return loadDefaultsButton.click();
                    })
                    .findByCssSelector(sdaDisk + ' input[type=number][name=image]')
                        // Get Image Storage size after load default
                        .then(function(input) {
                            return input.getAttribute('value')
                                .then(function(value) {
                                    assert.isTrue(value == initialImageSize, 'Image Storage size restored to default');
                                })
                        })
                    .then(function() {
                        // Checking "Cancel" button is disabled again
                        return cancelButton
                            .isEnabled()
                            .then(function(isEnabled) {
                                assert.isFalse(isEnabled, 'Cancel button is disabled');
                            });
                    })
                    .then(function() {
                        // Checking "Apply" button is disabled again
                        return applyButton
                            .isEnabled()
                            .then(function(isEnabled) {
                                assert.isFalse(isEnabled, 'Apply button is disabled');
                            });
                    });
            },
            'Testing volume group deletion and Cancel button': function() {
                var sdaDisk = '.disk-box[data-disk=sda]',
                    initialImageSize;

                return this.remote
                    .setFindTimeout(5000)
                    .findByCssSelector(sdaDisk + ' input[type=number][name=image]')
                        // Get the initial size of the Image Storage
                        .then(function(input) {
                            return input.getAttribute('value')
                                .then(function(value) {
                                    initialImageSize = value;
                                    assert.ok(value, 'Expected positive size value for imageSDA');
                                });
                        })
                        .end()
                    .findByCssSelector(sdaDisk + ' .disk-visual [data-volume=image]')
                        // Check that visualisation div for Image Storage present and has positive width
                        .then(function(element) {
                            return element.getAttribute('style')
                                .then(function(style) {
                                    var width = style.split(';')[0].split(' ')[1];
                                    assert.isTrue(parseInt(width.substring(0, width.length - 1)) > 0, 'Expected positive width for Image Storage visual');
                                });
                        })
                        .end()
                    .findByCssSelector(sdaDisk + ' .disk-visual [data-volume=image] .close-btn')
                        // Delete Image Storage volume
                        .click()
                        .end()
                    .then(function() {
                        // Checking "Apply" button is enabled now
                        return applyButton
                            .isEnabled()
                            .then(function(isEnabled) {
                                assert.isTrue(isEnabled, 'Apply button is enabled');
                            });
                    })
                    .findByCssSelector(sdaDisk + ' .disk-visual [data-volume=image]')
                        // Check that visualisation div for Image Storage present and has width = 0
                        .then(function(element) {
                            return element.getAttribute('style')
                                .then(function(style) {
                                    var width = style.split(';')[0].split(' ')[1];
                                    assert.isTrue(parseInt(width.substring(0, width.length - 1)) == 0, 'Expected null width for Image Storage visual');
                                });
                        })
                        .end()
                    .findByCssSelector(sdaDisk + ' .disk-visual [data-volume=unallocated]')
                        // Check that there is unallocated space after Image Storage removal
                        .then(function(element) {
                            return element.getAttribute('style')
                                .then(function(style) {
                                    var width = style.split(';')[0].split(' ')[1];
                                    assert.isTrue(parseInt(width.substring(0, width.length - 1)) > 0, 'There is unallocated space after Image Storage removal');
                                });
                        })
                        .end()
                    .findByCssSelector(sdaDisk + ' input[type=number][name=image]')
                        // Get Image Storage size after deletion, check that this value = 0
                        .then(function(input) {
                            return input.getAttribute('value')
                                .then(function(value) {
                                    assert.isTrue(value == 0, 'Image Storage volume was removed successfully');
                                })
                        })
                        .end()
                    .then(function() {
                        // Click Revert Changes Button
                        return cancelButton.click();
                    })
                    .findByCssSelector(sdaDisk + ' input[type=number][name=image]')
                        // Get Image Storage size after load default
                        .then(function(input) {
                            return input.getAttribute('value')
                                .then(function(value) {
                                    assert.isTrue(value == initialImageSize, 'Image Storage volume control contains correct value');
                                })
                        })
                        .end()
                    .then(function() {
                        // Checking "Apply" button is disabled again
                        return applyButton
                            .isEnabled()
                            .then(function(isEnabled) {
                                assert.isFalse(isEnabled, 'Apply button is disabled');
                            });
                    });
            }
        };
    });
});
