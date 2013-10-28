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
        jquery: 'js/libs/jquery-1.9.1',
        'jquery-checkbox': 'js/libs/jquery.checkbox',
        'jquery-timeout': 'js/libs/jquery.timeout',
        'jquery-ui': 'js/libs/jquery-ui-1.10.2.custom',
        'jquery-autoNumeric': 'js/libs/autoNumeric',
        utils: 'js/utils',
        underscore: 'js/libs/lodash',
        backbone: 'js/libs/backbone',
        stickit: 'js/libs/backbone.stickit',
        deepModel: 'js/libs/deep-model',
        coccyx: 'js/libs/coccyx',
        bootstrap: 'js/libs/bootstrap.min',
        text: 'js/libs/text',
        retina: 'js/libs/retina',
        app: 'js/app',
        models: 'js/models',
        collections: 'js/collections',
        views: 'js/views'
    },
    shim: {
        underscore: {
            exports: '_'
        },
        backbone: {
            deps: ['underscore', 'jquery'],
            exports: 'Backbone'
        },
        stickit: {
            deps: ['backbone']
        },
        deepModel: {
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
            deps: ['jquery', 'underscore', 'backbone', 'stickit', 'deepModel', 'coccyx', 'bootstrap', 'retina', 'jquery-checkbox', 'jquery-timeout', 'jquery-ui', 'jquery-autoNumeric']
        }
    }
});

require(['app'], function (app) {
    'use strict';
    $(document).ready(app.initialize);
});
