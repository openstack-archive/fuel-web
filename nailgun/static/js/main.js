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
        'jquery': 'js/lib/bower/jquery/jquery',
        'jquery-checkbox': 'js/lib/custom/jquery.checkbox',
        'jquery-timeout': 'js/lib/bower/jquery.timeout/index',
        'jquery-ui': 'js/lib/custom/jquery-ui.custom',
        'jquery-autoNumeric': 'js/lib/bower/autoNumeric/autoNumeric',
        utils: 'js/utils',
        lodash: 'js/lib/bower/lodash/lodash',
        backbone: 'js/lib/custom/backbone',
        stickit: 'js/lib/bower/backbone.stickit/index',
        coccyx: 'js/lib/custom/coccyx',
        bootstrap: 'js/lib/custom/bootstrap.custom',
        text: 'js/lib/bower/requirejs-text/text',
        retina: 'js/lib/bower/retina.js/src/retina',
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
