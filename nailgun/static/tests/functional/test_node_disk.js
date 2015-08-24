/*
 * Copyright 2014 Mirantis, Inc.
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
            clusterName;
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
                    });
            },
            beforeEach: function() {
                return this.remote
                    .then(function() {
                        return disks.goToNodeDisks();
                    });
            },
            afterEach: function() {
            },
            teardown: function() {
                return this.remote
                    .then(function() {
                        return common.removeCluster(clusterName, true);
                    });
            },
            'Testing nodes disks layout': function() {
                var cancelButton, applyButton, loadDefaultsButton,
                    osSDA, imageSDA,
                    sdaDisk = '.disk-box[data-disk=sda]',
                    sdaDiskOS = sdaDisk + ' .disk-utility-box [data-volume=os]',
                    sdaDiskImage = sdaDisk + ' .disk-utility-box [data-volume=image]';
                return this.remote
                    .setFindTimeout(5000)
                    .findByCssSelector('.edit-node-disks-screen')
                        // Check if "Edit Node Disks page" opens
                        .end()
                    .findAllByCssSelector('.node-disks > .disk-box')
                        // Find all disks fo this Node
                        .then(function(elements) {
                            return assert.ok(elements.length, 6, 'Number of disks is incorrect');
                        })
                        .end()
                    .findByCssSelector('.btn-revert-changes')
                        // Checking "Cancel" button is disabled
                        .then(function(button) {
                            cancelButton = button;
                            return cancelButton.isEnabled().then(function(isEnabled) {
                                return assert.isFalse(isEnabled, 'Cancel button should be disabled');
                            });
                        })
                        .end()
                    .findByCssSelector('.btn-apply')
                        // Checking "Apply" button is disabled
                        .then(function(button) {
                            applyButton = button;
                            return applyButton.isEnabled().then(function(isEnabled) {
                                return assert.isFalse(isEnabled, 'Apply button should be disabled');
                            });
                        })
                        .end()
                    .findByCssSelector('.btn-defaults')
                        // Checking "Load Defaults" button is enabled
                        .then(function(button) {
                            loadDefaultsButton = button;
                            return loadDefaultsButton.isEnabled().then(function(isEnabled) {
                                return assert.ok(isEnabled, 'Load Defaults button should be enabled');
                            });
                        })
                        .end()
                    .findByCssSelector(sdaDisk + ' .disk-visual [data-volume=os] .toggle')
                        // View SDA disk
                        .click()
                        .end()
                    .findByCssSelector(sdaDiskOS + ' input')
                        .then(function(input) {
                            return input.getAttribute('value')
                               .then(function(value){
                                    console.log('osSDA value =', value);
                                    osSDA = value;
                                    return assert.ok(value == 55296, 'tralala');
                                })
                        })
                        .end()
                    .findByCssSelector(sdaDiskImage + ' input')
                        .then(function(input) {
                            return input.getAttribute('value')
                               .then(function(value){
                                    console.log('imageSDA value =', value);
                                    imageSDA = value;
                                    return assert.ok(value == 877337, 'tralala2');
                                })
                        })
                        .end()
            }
        };
    });
});
