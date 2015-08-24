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

define(function() {
    'use strict';
    function NodeDisks(remote) {
        this.remote = remote;
    }

    NodeDisks.prototype = {
        constructor: NodeDisks,
        goToNodeDisks: function() {
            return this.remote
                .setFindTimeout(5000)
                .findAllByCssSelector('.node.pending_addition > label')
                    // Check node
                    .click()
                    .end()
                .findByCssSelector('.btn-configure-disks')
                    // Click to "Configure Disks" button
                    .click()
                    .end();
        },
        getButton: function(selector) {
            return this.remote
                .setFindTimeout(5000)
                .findByCssSelector(selector)
        }
    };
    return NodeDisks;
});
