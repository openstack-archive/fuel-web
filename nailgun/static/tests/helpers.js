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

define(['underscore', 'intern/dojo/node!fs', 'intern/dojo/node!leadfoot/Command'], function(_, fs, Command) {
    'use strict';

    _.defaults(Command.prototype, {
        clickLinkByText: function(text) {
            return new this.constructor(this, function() {
                return this.parent
                    .findByLinkText(text)
                        .click()
                        .end();
            });
        },
        clickByCssSelector: function(cssSelector) {
            return new this.constructor(this, function() {
                return this.parent
                    .findByCssSelector(cssSelector)
                        .click()
                        .end();
            });
        },
        takeScreenshotAndSave: function(filename) {
            return new this.constructor(this, function() {
                return this.parent
                    .takeScreenshot()
                    .then(function(buffer) {
                        var targetDir = process.env.ARTIFACTS || process.cwd();
                        if (!filename) filename = new Date().toTimeString();
                        filename = filename.replace(/[\s\*\?\\\/]/g, '_');
                        filename = targetDir + '/' + filename + '.png';
                        console.log('Saving screenshot to', filename); // eslint-disable-line no-console
                        fs.writeFileSync(filename, buffer);
                });
            });
        },
        waitForCssSelector: function(cssSelector, timeout) {
            return new this.constructor(this, function() {
                var self = this, currentTimeout;
                return this.parent
                    .getFindTimeout()
                    .then(function(value) {
                        currentTimeout = value;
                    })
                    .setFindTimeout(timeout)
                    .findByCssSelector(cssSelector)
                        .catch(function(error) {
                            self.parent.setFindTimeout(currentTimeout);
                            throw error;
                        })
                        .end()
                    .then(function() {
                        self.parent.setFindTimeout(currentTimeout);
                    })
            });
        },
        waitForElementDeletion: function(cssSelector, timeout) {
            return new this.constructor(this, function() {
                var self = this, currentTimeout;
                return this.parent
                    .getFindTimeout()
                    .then(function(value) {
                        currentTimeout = value;
                    })
                    .setFindTimeout(timeout)
                    .waitForDeletedByCssSelector(cssSelector)
                    .catch(function(error) {
                        self.parent.setFindTimeout(currentTimeout);
                        if (error.name != 'Timeout') throw error;
                    })
                    .then(function() {
                        self.parent.setFindTimeout(currentTimeout);
                    })
            });
        },
        setInputValue: function(cssSelector, value) {
            return new this.constructor(this, function() {
                return this.parent
                    .findByCssSelector(cssSelector)
                        .clearValue()
                        .type(value)
                        .end();
            });
        }
    });

    var serverHost = '127.0.0.1',
        serverPort = process.env.SERVER_PORT || 5544,
        serverUrl = 'http://' + serverHost + ':' + serverPort,
        username = 'admin',
        password = 'admin';

    return {
        username: username,
        password: password,
        serverUrl: serverUrl
    };
});
