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
            sdaDisk;

        return {
            name: 'Node Disk',
            setup: function() {
                common = new Common(this.remote);
                clusterName = common.pickRandomName('Test Cluster');
                sdaDisk = '.disk-box[data-disk=sda]';

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
                        // Check node
                        return common.clickElement('.node.pending_addition > label');
                    })
                    .then(function() {
                        // Click Configure Disks button
                        return common.clickElement('.btn-configure-disks');
                    })
                    .then(function() {
                        return common.elementExists('.edit-node-disks-screen', 'Disk configuration screen opened ');
                    })
                    .findByCssSelector(sdaDisk + ' input[type=number][name=image]')
                        // Get the initial size of the Image Storage volume
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
                    .findAllByCssSelector('.node-disks > .disk-box')
                        // Check disk number
                        .then(function(elements) {
                            assert.ok(elements.length, 'Disks are presented');
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
            'Check SDA disk layout': function() {
                return this.remote
                    .then(function() {
                        // Expand SDA disk
                        return common.clickElement(sdaDisk + ' .disk-visual [data-volume=os] .toggle');
                    })
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
            'Testing Apply and Load Defaults buttons: interaction': function() {
                return this.remote
                    .then(function() {
                        return common.setInputValue(sdaDisk + ' input[type=number][name=image]', '5');
                    })
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
                        return common.clickElement('.btn-apply');
                    })
                    .then(function() {
                        // Wait for changes applied
                        return common.waitForElementDeletion('.btn-load-defaults:disabled');
                    })
                    .then(function() {
                        return common.clickElement('.btn-defaults');
                    })
                    .then(function() {
                        return common.isElementValueEqualTo(sdaDisk + ' input[type=number][name=image]', initialImageSize, 'Image Storage size restored to default');
                    })
                    .then(function() {
                        return common.isElementEnabled('.btn-revert-changes', 'Cancel button is enabled');
                    })
                    .then(function() {
                        return common.isElementEnabled('.btn-apply', 'Apply button is enabled');
                    })
                    .then(function() {
                        return common.clickElement('.btn-apply');
                    });
            },
            'Testing volume group deletion and Cancel button': function() {
                return this.remote
                    .findByCssSelector(sdaDisk + ' .disk-visual [data-volume=image]')
                        // Check that visualisation div for Image Storage present and has positive width
                        .then(function(element) {
                            return element.getSize()
                                .then(function(sizes) {
                                    assert.isTrue(sizes.width > 0, 'Expected positive width for Image Storage visual');
                                });
                        })
                        .end()
                    .then(function() {
                        // Delete Image Storage volume
                        return common.clickElement(sdaDisk + ' .disk-visual [data-volume=image] .close-btn');
                    })
                    .then(function() {
                        return common.isElementEnabled('.btn-apply', 'Apply button is enabled');
                    })
                    .findByCssSelector(sdaDisk + ' .disk-visual [data-volume=image]')
                        // Check Image Storage volume deleted
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
                        // Check that there is unallocated space after Image Storage removal
                        .then(function(element) {
                            return element.getSize()
                                .then(function(sizes) {
                                    assert.isTrue(sizes.width > 0, 'There is unallocated space after Image Storage removal');
                                });
                        })
                        .end()
                    .then(function() {
                        // Revert Changes button click
                        return common.clickElement('.btn-revert-changes');
                    })
                    .then(function() {
                        return common.isElementValueEqualTo(sdaDisk + ' input[type=number][name=image]', initialImageSize, 'Image Storage volume control contains correct value');
                    })
                    .then(function() {
                        return common.isElementDisabled('.btn-apply', 'Apply button is disabled');
                    });
            },
            'Testing wrong value': function() {
                return this.remote
                    .then(function() {
                        return common.setInputValue(sdaDisk + ' input[type=number][name=image]', '5');
                    })
                    .then(function() {
                        // Aplly button is active in case of correct value
                        return common.isElementEnabled('.btn-apply', 'Apply button is enabled');
                    })
                    .then(function() {
                        return common.setInputValue(sdaDisk + ' input[type=number][name=os]', '5');
                    })
                    .then(function() {
                        return common.elementExists(sdaDisk + ' .disk-details [data-volume=os] .volume-group-notice.text-danger', 'Error about low value is present');
                    })
                    .then(function() {
                        // Aplly button is disabled in case of incorrect value
                        return common.isElementDisabled('.btn-apply', 'Apply button is disabled');
                    })
                    .then(function() {
                        return common.clickElement('.btn-revert-changes');
                    });
            }
        };
    });
});
