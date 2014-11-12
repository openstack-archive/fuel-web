/*
 * Copyright 2013 Mirantis, Inc.
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
var system = require('system');
var port = system.env.SERVER_PORT || 5544;

var baseUrl = 'http://127.0.0.1:' + port + '/';

var authToken;

var addTokenHeader = function(headers) {
    var ret = {},
        property;

    headers = headers || {};

    if (authToken) {
        ret['X-Auth-Token'] = authToken;
    }

    for (property in headers) {
        if (headers.hasOwnProperty(property)) {
            ret[property] = headers[property];
        }
    }

    return ret;
};

casper.on('page.error', function(msg) {
    casper.echo(msg, 'ERROR');
});

casper.on('page.initialized', function(msg) {
    this.loadJsFile('bind-polyfill');
});

casper.loadPage = function(page) {
    //FIXME: hack to prevent ajax requests interruption (phantomjs issue)
    this.wait(1000);
    return this.thenOpen(baseUrl + page).waitWhileSelector('#content > .loading');
}

casper.loadJsFile = function(file) {
    return this.page.injectJs('ui_tests/' + file + '.js');
}

casper.test.assertSelectorAppears = function(selector, message, timeout) {
    return this.casper.waitForSelector(selector, function () {
        this.test.pass(message);
    }, function() {
        this.test.fail(message);
    }, timeout);
}

casper.test.assertSelectorDisappears = function(selector, message, timeout) {
    return this.casper.waitWhileSelector(selector, function () {
        this.test.pass(message);
    }, function() {
        this.test.fail(message);
    }, timeout);
}

casper.authenticate = function(options) {
    options = options || {};
    var username = options.username || 'admin',
        password = options.password || 'admin';

    this.thenOpen(baseUrl + 'keystone/v2.0/tokens', {
        method: 'post',
        headers: addTokenHeader({'Content-Type': 'application/json'}),
        data: JSON.stringify({
            auth: {
                passwordCredentials: {
                    username: username,
                    password: password
                }
            }
        })
    });
    this.then(function() {
        authToken = this.evaluate(function() {
            var data,
                authToken = '',
                username;
            try {
                data = JSON.parse(document.body.innerText);
                authToken = data.access.token.id;
                username = data.access.user.username;
            } catch (ignore) {}

            localStorage.setItem('token', authToken);
            localStorage.setItem('username', username);

            return authToken;
        });
    });

    return this;
}

casper.skipWelcomeScreen = function() {
    return this.then(function() {
        this.thenOpen(baseUrl + 'api/settings', {
            method: 'get',
            headers: addTokenHeader({'Content-Type': 'application/json'})
        });
        this.then(function() {
            var fuelSettings = this.evaluate(function() {
                return JSON.parse(document.body.innerText);
            });
            fuelSettings.settings.statistics.user_choice_saved.value = true;
            this.thenOpen(baseUrl + 'api/settings', {
                method: 'put',
                headers: addTokenHeader({'Content-Type': 'application/json'}),
                data: JSON.stringify(fuelSettings)
            });
        });
    });
}

casper.createCluster = function(options) {
    options.release = 1; // centos
    this.then(function() {
        return this.open(baseUrl + 'api/clusters', {
            method: 'post',
            headers: addTokenHeader({'Content-Type': 'application/json'}),
            data: JSON.stringify(options)
        });
    });
}

casper.createNode = function(options) {
    var mac = '52:54:00:96:81:6E';
    if('mac' in options) {
        mac = options['mac'];
    }

    options.meta = {
        "disks": [
            {
                "model": "TOSHIBA MK3259GS",
                "disk": "sda",
                "name": "sda",
                "size": 100010485760
            },
            {
                "model": "TOSHIBA",
                "disk": "vda",
                "name": "vda",
                "size": 80010485760
            }
        ],
        "interfaces": [
            {
              "mac": mac,
              "name": "eth0",
              "max_speed": 1000,
              "current_speed": 100
            },
            {
              "ip": "10.20.0.3",
              "mac": "C8:0A:A9:A6:FF:28",
              "name": "eth1",
              "max_speed": 1000,
              "current_speed": 1000
            },
            {
              "mac": "D4:56:C3:88:99:DF",
              "name": "eth0:1",
              "max_speed": 2000,
              "current_speed": null
            }
        ],
        "cpu": {
            "real": 0,
            "0": {
                "family": "6",
                "vendor_id": "GenuineIntel",
                "mhz": "3192.766",
                "stepping": "3",
                "cache_size": "4096 KB",
                "flags": [
                    "fpu",
                    "lahf_lm"
                ],
                "model": "2",
                "model_name": "QEMU Virtual CPU version 0.14.1"
            },
            "total": 1
        },
        "memory": {
            "slots": 6,
            "total": 4294967296,
            "maximum_capacity": 8589934592,
            "devices": [
                {
                    "size": 1073741824
                },
                {
                    "size": 1073741824
                },
                {
                    "size": 1073741824
                },
                {
                    "size": 1073741824
                }
            ]
        }
    };
    return this.thenOpen(baseUrl + 'api/nodes', {
        method: 'post',
        headers: addTokenHeader({'Content-Type': 'application/json'}),
        data: JSON.stringify(options)
    });
}
