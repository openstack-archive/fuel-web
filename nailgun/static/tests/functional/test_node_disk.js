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
    'tests/helpers',
    'tests/functional/pages/common'
], function(registerSuite, assert, helpers, Common) {
    'use strict';

    registerSuite(function() {
        var common,
            clusterName,
            initialImageSize,
            sdaDisk,
            applyButtonSelector, cancelButtonSelector, loadDefaultsButtonSelector;

        return {
            name: 'Node Disk',
            setup: function() {
                common = new Common(this.remote);
                clusterName = common.pickRandomName('Test Cluster');
                sdaDisk = '.disk-box[data-disk=sda]';
                applyButtonSelector = '.btn-apply';
                cancelButtonSelector = '.btn-revert-changes';
                loadDefaultsButtonSelector = '.btn-defaults';

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
                    // check node
                    .clickOnElement('.node.pending_addition > label')
                    // click Configure Disks button
                    .clickOnElement('.btn-configure-disks')
                    .then(function() {
                        return common.elementExists('.edit-node-disks-screen', 'Disk configuration screen opened ');
                    })
                    .findByCssSelector(sdaDisk + ' input[type=number][name=image]')
                        // get the initial size of the Image Storage volume
                        .then(function(input) {
                            return input.getAttribute('value')
                                .then(function(value) {
                                    initialImageSize = value;
                                });
                        })
                        .end();
            },
            teardown: function() {
                return this.remote
                    .then(function() {
                        return common.removeCluster(clusterName, true);
                    });
            },
            'Testing nodes disks layout': function() {
                return this.remote
                    .then(function() {
                        return common.isElementDisabled(cancelButtonSelector, 'Cancel button is disabled');
                    })
                    .then(function() {
                        return common.isElementDisabled(applyButtonSelector, 'Apply button is disabled');
                    })
                    .then(function() {
                        return common.isElementEnabled(loadDefaultsButtonSelector, 'Load Defaults button is enabled');
                    });
            },
            'Check SDA disk layout': function() {
                return this.remote
                    .clickOnElement(sdaDisk + ' .disk-visual [data-volume=os] .toggle')
                    .findByCssSelector(sdaDisk + ' .disk-utility-box [data-volume=os] input')
                        .then(function(input) {
                            return input.getAttribute('value')
                                .then(function(value) {
                                    assert.ok(value, 'Base System is allocated on SDA disk');
                                });
                        })
                        .end()
                    .findByCssSelector(sdaDisk + ' .disk-utility-box [data-volume=image] input')
                        .then(function(input) {
                            return input.getAttribute('value')
                                .then(function(value) {
                                    assert.ok(value, 'Image Storage is allocated on SDA disk');
                                });
                        })
                        .end()
                    .then(function() {
                        return common.elementExists(sdaDisk + ' .disk-visual [data-volume=image] .close-btn', 'Button Close for Image Storage volume is present');
                    })
                    .then(function() {
                        return common.elementNotExists(sdaDisk + ' .disk-visual [data-volume=os] .close-btn', 'Button Close for Base system volume is not present');
                    })
                    .then(function() {
                        return common.elementExists(sdaDisk + ' .disk-details [data-volume=os] .volume-group-notice.text-info', 'Notice about "Minimal size" is present');
                    });
            },
            'Testing Apply and Load Defaults buttons behaviour': function() {
                return this.remote
                    .then(function() {
                        return common.setInputValue(sdaDisk + ' input[type=number][name=image]', '5');
                    })
                    .then(function() {
                        return common.isElementEnabled(cancelButtonSelector, 'Cancel button is enabled');
                    })
                    .then(function() {
                        return common.isElementEnabled(applyButtonSelector, 'Apply button is enabled');
                    })
                    .then(function() {
                        return common.isElementEnabled(loadDefaultsButtonSelector, 'Load Defaults button is enabled');
                    })
                    .clickOnElement(applyButtonSelector)
                    .then(function() {
                        // wait for changes applied
                        return common.waitForElementDeletion('.btn-load-defaults:disabled');
                    })
                    .clickOnElement(loadDefaultsButtonSelector)
                    .then(function() {
                        return common.isElementValueEqualTo(sdaDisk + ' input[type=number][name=image]', initialImageSize, 'Image Storage size restored to default');
                    })
                    .then(function() {
                        return common.isElementEnabled(cancelButtonSelector, 'Cancel button is enabled');
                    })
                    .then(function() {
                        return common.isElementEnabled(applyButtonSelector, 'Apply button is enabled');
                    })
                    .clickOnElement(applyButtonSelector);
            },
            'Testing volume group deletion and Cancel button': function() {
                return this.remote
                    .findByCssSelector(sdaDisk + ' .disk-visual [data-volume=image]')
                        // check that visualisation div for Image Storage present and has positive width
                        .then(function(element) {
                            return element.getSize()
                                .then(function(sizes) {
                                    assert.isTrue(sizes.width > 0, 'Expected positive width for Image Storage visual');
                                });
                        })
                        .end()
                    .clickOnElement(sdaDisk + ' .disk-visual [data-volume=image] .close-btn')
                    .then(function() {
                        return common.isElementEnabled(applyButtonSelector, 'Apply button is enabled');
                    })
                    .findByCssSelector(sdaDisk + ' .disk-visual [data-volume=image]')
                        // check Image Storage volume deleted
                        .then(function(element) {
                            return element.getSize()
                                .then(function(sizes) {
                                    assert.equal(sizes.width, 0, 'Expected null width for Image Storage visual');
                                });
                        })
                        .end()
                    .then(function() {
                        return common.isElementValueEqualTo(sdaDisk + ' input[type=number][name=image]', 0, 'Image Storage volume was removed successfully');
                    })
                    .findByCssSelector(sdaDisk + ' .disk-visual [data-volume=unallocated]')
                        // check that there is unallocated space after Image Storage removal
                        .then(function(element) {
                            return element.getSize()
                                .then(function(sizes) {
                                    assert.isTrue(sizes.width > 0, 'There is unallocated space after Image Storage removal');
                                });
                        })
                        .end()
                    .clickOnElement(cancelButtonSelector)
                    .then(function() {
                        return common.isElementValueEqualTo(sdaDisk + ' input[type=number][name=image]', initialImageSize, 'Image Storage volume control contains correct value');
                    })
                    .then(function() {
                        return common.isElementDisabled(applyButtonSelector, 'Apply button is disabled');
                    });
            },
            'Test volume size validation': function() {
                return this.remote
                    .then(function() {
                        // reduce Image Storage volume size to free space on the disk
                        return common.setInputValue(sdaDisk + ' input[type=number][name=image]', '5');
                    })
                    .then(function() {
                        // set Base OS volume size lower than required
                        return common.setInputValue(sdaDisk + ' input[type=number][name=os]', '5');
                    })
                    .then(function() {
                        return common.elementExists(sdaDisk + ' .disk-details [data-volume=os] .volume-group-notice.text-danger', 'Validation error exists if volume size is less than required.');
                    })
                    .then(function() {
                        return common.isElementDisabled(applyButtonSelector, 'Apply button is disabled in case of validation error');
                    })
                    .clickOnElement(cancelButtonSelector);
            }
        };
    });
});
