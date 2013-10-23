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
requirejs.config({
    baseUrl: 'static',
    urlArgs: '_=' +  (new Date()).getTime(),
    waitSeconds: 60,
    paths: {
        'jquery': 'js/libs/jquery/jquery.min',
        'jquery-checkbox': 'js/libs/jquery.checkbox/index',
        'jquery-timeout': 'js/libs/jquery.timeout-1.1.0.js/index',
        'jquery-ui': 'js/libs/jquery-ui-custom/index',
        'jquery-autoNumeric': 'js/libs/autoNumeric/autoNumeric',
        utils: 'js/utils',
        lodash: 'js/libs/lodash/dist/lodash.min',
        backbone: 'js/libs/backbone.js/index',
        stickit: 'js/libs/backbone.stickit/index',
        coccyx: 'js/libs/Coccyx.js/index',
        bootstrap: 'js/libs/bootstrap-custom/index',
        text: 'js/libs/requirejs-text/text',
        retina: 'js/libs/retina.js/src/retina',
        app: 'js/app',
        models: 'js/models',
        collections: 'js/collections',
        views: 'js/views'
    },
    shim: {
        lodash: {
            exports: '_'
        },
        backbone: {
            deps: ['lodash', 'jquery'],
            exports: 'Backbone'
        },
        stickit: {
            deps: ['backbone']
        },
        coccyx: {
            deps: ['backbone']
        },
        bootstrap: {
            deps: ['jquery']
        },
        'jquery-checkbox': {
            deps: ['jquery']
        },
        'jquery-timeout': {
            deps: ['jquery']
        },
        'jquery-ui': {
            deps: ['jquery']
        },
        'jquery-autoNumeric': {
            deps: ['jquery']
        },
        app: {
            deps: ['jquery', 'lodash', 'backbone', 'stickit', 'coccyx', 'bootstrap', 'retina', 'jquery-checkbox', 'jquery-timeout', 'jquery-ui', 'jquery-autoNumeric']
        }
    }
});

require(['app'], function (app) {
    'use strict';
    $(document).ready(app.initialize);
});
