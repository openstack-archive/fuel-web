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

casper.start().loadPage('#logout');

casper.then(function() {
    var authenticated = this.evaluate(function() {
            return window.app.user.get('authenticated');
        }),
            token = this.evaluate(function() {
            return window.app.keystoneClient.token;
        });

    this.test.assertNot(authenticated, 'User is not authenticated');
    this.test.assertNot(token, 'User is token is not set');
    this.test.assertUrlMatch(/#login/, 'Redirect to login page after logout');
});

casper.then(casper.authenticate).loadPage('#clusters');

casper.then(function() {
    var authenticated = this.evaluate(function() {
            return window.app.user.get('authenticated');
        }),
        token = this.evaluate(function() {
            return window.app.keystoneClient.token;
        });

    this.test.assertExists('a[href="#logout"]', 'Logout link exists');
    this.test.assert(authenticated, 'User is authenticated');
    this.test.assert(!!token, 'User is token is set');
    this.click('a[href="#logout"]');
});

casper.then(function() {
    var authenticated = this.evaluate(function() {
            return window.app.user.get('authenticated');
        }),
        token = this.evaluate(function() {
            return window.app.keystoneClient.token;
        });

    this.test.assertNot(authenticated, 'User is not authenticated');
    this.test.assertNot(token, 'User is token is not set');
    this.test.assertUrlMatch(/#login/, 'Redirect to login page after logout');
});

casper.run(function() {
    this.test.done();
});
