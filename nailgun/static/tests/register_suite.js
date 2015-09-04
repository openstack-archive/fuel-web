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
    'intern!object',
    'intern/dojo/node!leadfoot/Command',
    './helpers'
], function(_, originalRegisterSuite, Command, helpers) {
    'use strict';

    function registerSuite(originalSuite) {
        _.extend(Command.prototype, helpers.leadfootHelpers);

        originalSuite = _.isFunction(originalSuite) ? originalSuite() : originalSuite;
        var suite = Object.create(originalSuite);

        suite.setup = function() {
            this.currentTestIndex = -1;
            if (originalSuite.setup) return originalSuite.setup.apply(this, arguments);
        };

        suite.beforeEach = function() {
            this.currentTestIndex++;
            if (originalSuite.beforeEach) return originalSuite.beforeEach.apply(this, arguments);
        };

        suite.afterEach = function() {
            var currentTest = this.tests[this.currentTestIndex];
            if (currentTest.error) {
                this.remote.takeScreenshotAndSave(this.name + ' - ' + currentTest.name);
            }
            if (originalSuite.afterEach) return originalSuite.afterEach.apply(this, arguments);
        };

        return originalRegisterSuite(suite);
    }

    return registerSuite;
});
