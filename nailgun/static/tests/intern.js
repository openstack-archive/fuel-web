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

define(['config'], function(config) {
    'use strict';

    config.baseUrl = '';
    config.waitSeconds = 7;

    config.paths.sinon = 'tests/bower/sinon/lib/sinon';

    // FIXME(vkramskikh): workaround for https://github.com/theintern/intern/issues/348
    delete config.map['*'];

    return {
        proxyPort: 9057,
        proxyUrl: 'http://localhost:9057/',
        capabilities: {
            'selenium-version': '2.45.0'
        },
        maxConcurrency: 1,
        useLoader: {
            'host-node': 'requirejs',
            'host-browser': '/vendor/bower/requirejs/require.js'
        },
        grep: /^/,
        excludeInstrumentation: /^/,
        loader: config,
        reporters: ['console', 'tests/screenshot_on_fail']
    };
});
