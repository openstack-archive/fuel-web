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
    'tests/functional/pages/common',
    'tests/functional/pages/modal'
], function(registerSuite, assert, helpers, Common, Modal) {
    'use strict';

    registerSuite(function() {
        var common,
            modal;

        return {
            name: 'Wizard Page',
            setup: function() {
                common = new Common(this.remote);
                modal = new Modal(this.remote);
                return this.remote
                    .then(function() {
                        return common.getIn();
                    });
            },
            'Test descriptions are present': function() {
                var clusterName = common.pickRandomName('Temp');
                return this.remote
                    .clickOnElement('.create-cluster')
                    .then(function() {
                        return modal.waitToOpen();
                    })
                    // Name and release
                    .findByName('name')
                        .clearValue()
                        .type(clusterName)
                        .end()
                    .then(function() {
                        return common.elementExists('.release-description', 'Release description element exists');
                    })
                    .findByCssSelector('.release-description')
                        .getVisibleText()
                        .then(function(text) {
                            return assert.isTrue(_.contains(text, 'This option will install'), 'Release description has proper text');
                        })
                        .end();
            }
        };
    });
});
