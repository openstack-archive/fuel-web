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
        'jquery': 'js/libs/bower/jquery/js/jquery',
        'jquery-checkbox': 'js/libs/custom/jquery.checkbox',
        'jquery-timeout': 'js/libs/custom/jquery.timeout',
        'jquery-ui': 'js/libs/custom/jquery-ui-1.10.2.custom',
        'jquery-autoNumeric': 'js/libs/bower/autoNumeric/js/autoNumeric',
        utils: 'js/utils',
        lodash: 'js/libs/bower/lodash/js/lodash',
        backbone: 'js/libs/custom/backbone',
        stickit: 'js/libs/bower/backbone.stickit/js/backbone.stickit',
        coccyx: 'js/libs/custom/coccyx',
        bootstrap: 'js/libs/custom/bootstrap.min',
        text: 'js/libs/bower/requirejs-text/js/text',
        i18next: 'js/libs/bower/i18next/js/i18next-1.7.1',
        underscore: 'js/libs/bower/lodash/js/lodash',
        deepModel: 'js/libs/bower/backbone-deep-model/js/deep-model',
        less: 'js/libs/bower/less/js/less-1.5.1',
        'require-css': 'js/libs/bower/require-css',
        app: 'js/app',
        styles: 'js/styles',
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
            deps: ['backbone'],
            exports: 'Coccyx'
        },
        bootstrap: {
            deps: ['jquery']
        },
        i18next: {
            deps: ['text!i18n/translation.json', 'jquery'],
            init: function(translation, $) {
                'use strict';
                $.i18n.init({resStore: JSON.parse(translation), fallbackLng: 'en-US'});
            }
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
        }
    }
});

require([
    'jquery',
    'underscore',
    'backbone',
    'stickit',
    'deepModel',
    'coccyx',
    'i18next',
    'bootstrap',
    'jquery-checkbox',
    'jquery-timeout',
    'jquery-ui',
    'jquery-autoNumeric',
    'styles',
    'app'
], function() {
    'use strict';
    require('app').initialize();
});
