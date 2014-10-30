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

casper.start().loadPage('#');

casper.then(function() {
    this.evaluate(function() {
        window.app.logout();
    })
});

casper.then(function() {
    var authenticated = this.evaluate(function() {
            return window.app.user.get('authenticated');
        }),
            token = this.evaluate(function() {
            return window.app.keystoneClient.token;
        });

    this.test.assertNot(authenticated, 'User is not authenticated');
    this.test.assertNot(token, 'Token is not set');
    this.test.assertUrlMatch(/#login/, 'Redirect to login page after logout');
});

casper.then(casper.authenticate).then(casper.skipWelcomeScreen).loadPage('#clusters');

casper.then(function() {
    var authenticated = this.evaluate(function() {
            return window.app.user.get('authenticated');
        }),
        token = this.evaluate(function() {
            return window.app.keystoneClient.token;
        });

    this.test.assertExists('a[href="#logout"]', 'Logout link exists');
    this.test.assert(authenticated, 'User is authenticated');
    this.test.assert(!!token, 'Token is set');
    this.test.assertSelectorAppears('span.username', 'Username span exists');
    // TODO: test for span.username content to be equal to localStorage.getItem('username')
    //       The problem for now is that CasperJS doesn't preserve localStorage for some reason
});

casper.loadPage('#logout');

casper.then(function() {
    var authenticated = this.evaluate(function() {
            return window.app.user.get('authenticated');
        }),
        token = this.evaluate(function() {
            return window.app.keystoneClient.token;
        });

    this.test.assertNot(authenticated, 'User is not authenticated');
    this.test.assertNot(token, 'Token is not set');
    this.test.assertUrlMatch(/#login/, 'Redirect to login page after logout');
});

// Test failing token DELETE response
casper.then(casper.authenticate).loadPage('#clusters');

casper.then(function() {
    if (this.loadJsFile('sinon-server')) {
        this.evaluate(function() {
            var server = sinon.fakeServer.create();
            server.autoRespond = true;
            server.respondWith('DELETE', /\/keystone\/v2\.0\/tokens\/.*/, [
                502, null, ''
            ]);
        });
    } else {
        this.test.error('Unable to load sinon');
        this.test.done();
    }
});

casper.then(function() {
    casper.loadPage('#logout');
});

casper.then(function() {
    this.test.assertUrlMatch(/#login/, 'Redirect to login page after logout with failed server request');
});

// make sure we're on #login page again, not clusters
casper.then(function() {
    casper.loadPage('#clusters');
});

casper.then(function() {
    this.test.assertUrlMatch(/#login/, 'Redirect to login page after requesting #clusters, when logged out with failed server request');
});

casper.loadPage('#clusters');

casper.then(function() {
    this.test.assertUrlMatch(/#login/, 'Redirect to login page after requesting #clusters, when logged out with failed server request');
});

casper.run(function() {
    this.test.done();
});
