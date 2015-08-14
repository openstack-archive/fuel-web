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

    var ScreenshotOnFailReporter = function(options) {
        this.console = options.console;
        this.remotes = {};
    }

    ScreenshotOnFailReporter.prototype = {
        saveScreenshot: function(testOrSuite) {
            var remote = this.remotes[testOrSuite.sessionId];
            if (remote && remote.takeScreenshotAndSave) remote.takeScreenshotAndSave(testOrSuite.id);
        },
        sessionStart: function(remote) {
            var sessionId = remote._session._sessionId;
            this.remotes[sessionId] = remote;
        },
        suiteError: function(suite) {
            this.saveScreenshot(suite);
        },
        testFail: function(test) {
            this.saveScreenshot(test);
        }
    };

    return ScreenshotOnFailReporter;
});
