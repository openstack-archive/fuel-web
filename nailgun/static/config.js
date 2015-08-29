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
define(function() {
    'use strict';

    return {
        baseUrl: 'static',
        waitSeconds: 60,
        paths: {
            jquery: 'vendor/npm/jquery/dist/jquery',
            'js-cookie': 'vendor/npm/js-cookie/src/js.cookie',
            lodash: 'vendor/npm/lodash/index',
            underscore: 'vendor/npm/lodash/index',
            backbone: 'vendor/npm/backbone/backbone',
            classnames: 'vendor/npm/classnames/index',
            react: 'vendor/npm/react/dist/react-with-addons',
            JSXTransformer: 'vendor/npm/react/dist/JSXTransformer',
            jsx: 'vendor/custom/jsx',
            'react.backbone': 'vendor/custom/react.backbone',
            'react-dnd': 'vendor/npm/react-dnd/dist/ReactDnD.min',
            stickit: 'vendor/npm/backbone.stickit/backbone.stickit',
            coccyx: 'vendor/custom/coccyx',
            routefilter: 'vendor/custom/backbone.routefilter',
            bootstrap: 'vendor/npm/bootstrap/dist/js/bootstrap',
            text: 'vendor/npm/requirejs-plugins/lib/text',
            json: 'vendor/npm/requirejs-plugins/src/json',
            i18next: 'vendor/npm/i18next/lib/dep/i18next-1.7.1',
            deepModel: 'vendor/custom/deep-model',
            lessLibrary: 'vendor/npm/less/dist/less',
            'require-css': 'vendor/npm/require-css'
        },
        shim: {
            'expression/parser': {
                // non-AMD module; gulp-jison supports generation of AMD
                // modules, but they have broken stacktrace
                exports: 'parser'
            },
            coccyx: {
                // non-AMD module
                deps: ['backbone', 'underscore'],
                exports: 'Coccyx'
            },
            classnames: {
                // non-AMD module
                exports: 'classNames'
            },
            bootstrap: {
                // non-AMD module, relies on global jQuery
                deps: ['jquery']
            },
            i18next: {
                // non-AMD module, relies on global jQuery; there is AMD
                // version, but we still use i18n var in lodash templates,
                // so we should use non-AMD version until we get rid of
                // Backbone.View's completely
                deps: ['jquery'],
                exports: 'i18n'
            },
            deepModel: {
                // even though deepmodel uses AMD format, it uses _.mixin
                // before define() call
                deps: ['underscore']
            }
        },
        map: {
            '*': {
                less: 'require-less'
            }
        },
        jsx: {
            fileExtension: '.jsx'
        }
    };
});
