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
                    .clickByCssSelector('.node.pending_addition > label')
                    // click Configure Disks button
                    .clickByCssSelector('.btn-configure-disks')
                    .waitForCssSelector('.edit-node-disks-screen', 2000)
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
            'Testing nodes disks layout': function() {
                return this.remote
                    .then(function() {
                        return common.assertElementDisabled(cancelButtonSelector, 'Cancel button is disabled');
                    })
                    .then(function() {
                        return common.assertElementDisabled(applyButtonSelector, 'Apply button is disabled');
                    })
                    .then(function() {
                        return common.assertElementEnabled(loadDefaultsButtonSelector, 'Load Defaults button is enabled');
                    });
            },
            'Check SDA disk layout': function() {
                return this.remote
                    .clickByCssSelector(sdaDisk + ' .disk-visual [data-volume=os] .toggle')
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
                        return common.assertElementExists(sdaDisk + ' .disk-visual [data-volume=image] .close-btn', 'Button Close for Image Storage volume is present');
                    })
                    .then(function() {
                        return common.assertElementNotExists(sdaDisk + ' .disk-visual [data-volume=os] .close-btn', 'Button Close for Base system volume is not present');
                    })
                    .then(function() {
                        return common.assertElementExists(sdaDisk + ' .disk-details [data-volume=os] .volume-group-notice.text-info', 'Notice about "Minimal size" is present');
                    });
            },
            'Testing Apply and Load Defaults buttons behaviour': function() {
                return this.remote
                    .setInputValue(sdaDisk + ' input[type=number][name=image]', '5')
                    .then(function() {
                        return common.assertElementEnabled(cancelButtonSelector, 'Cancel button is enabled');
                    })
                    .then(function() {
                        return common.assertElementEnabled(applyButtonSelector, 'Apply button is enabled');
                    })
                    .clickByCssSelector(applyButtonSelector)
                    // wait for changes applied
                    .waitForElementDeletion('.btn-load-defaults:disabled', 2000)
                    .clickByCssSelector(loadDefaultsButtonSelector)
                    .then(function() {
                        return common.assertElementValueEqualTo(sdaDisk + ' input[type=number][name=image]', initialImageSize, 'Image Storage size restored to default');
                    })
                    .then(function() {
                        return common.assertElementEnabled(cancelButtonSelector, 'Cancel button is enabled');
                    })
                    .then(function() {
                        return common.assertElementEnabled(applyButtonSelector, 'Apply button is enabled');
                    })
                    .clickByCssSelector(applyButtonSelector);
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
                    .clickByCssSelector(sdaDisk + ' .disk-visual [data-volume=image] .close-btn')
                    .then(function() {
                        return common.assertElementEnabled(applyButtonSelector, 'Apply button is enabled');
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
                        return common.assertElementValueEqualTo(sdaDisk + ' input[type=number][name=image]', 0, 'Image Storage volume was removed successfully');
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
                    .clickByCssSelector(cancelButtonSelector)
                    .then(function() {
                        return common.assertElementValueEqualTo(sdaDisk + ' input[type=number][name=image]', initialImageSize, 'Image Storage volume control contains correct value');
                    })
                    .then(function() {
                        return common.assertElementDisabled(applyButtonSelector, 'Apply button is disabled');
                    });
            },
            'Test volume size validation': function() {
                return this.remote
                    // reduce Image Storage volume size to free space on the disk
                    .setInputValue(sdaDisk + ' input[type=number][name=image]', '5')
                    // set Base OS volume size lower than required
                    .setInputValue(sdaDisk + ' input[type=number][name=os]', '5')
                    .then(function() {
                        return common.assertElementExists(sdaDisk + ' .disk-details [data-volume=os] .volume-group-notice.text-danger', 'Validation error exists if volume size is less than required.');
                    })
                    .then(function() {
                        return common.assertElementDisabled(applyButtonSelector, 'Apply button is disabled in case of validation error');
                    })
                    .clickByCssSelector(cancelButtonSelector);
            }
        };
    });
});
