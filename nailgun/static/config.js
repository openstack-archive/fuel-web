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
            jquery: 'libs/bower/jquery/jquery',
            'jquery-cookie': 'libs/bower/jquery-cookie/jquery.cookie',
            'jquery-ui': 'libs/bower/jquery-ui/ui',
            'jquery-autoNumeric': 'libs/bower/autoNumeric/autoNumeric',
            lodash: 'libs/bower/lodash/dist/lodash.compat',
            underscore: 'libs/bower/lodash/dist/lodash.compat',
            backbone: 'libs/bower/backbone/backbone',
            classnames: 'libs/bower/classnames/index',
            react: 'libs/bower/react/react-with-addons',
            JSXTransformer: 'libs/bower/react/JSXTransformer',
            jsx: 'libs/bower/jsx-requirejs-plugin/js/jsx',
            'react.backbone': 'libs/custom/react.backbone',
            stickit: 'libs/bower/backbone.stickit/backbone.stickit',
            coccyx: 'libs/custom/coccyx',
            cocktail: 'libs/bower/cocktail/Cocktail',
            routefilter: 'libs/bower/routefilter/dist/backbone.routefilter.min',
            bootstrap: 'libs/bower/bootstrap/dist/js/bootstrap',
            text: 'libs/bower/requirejs-text/text',
            json: 'libs/bower/requirejs-plugins/src/json',
            i18next: 'libs/bower/i18next/release/i18next-1.7.1',
            deepModel: 'libs/bower/backbone-deep-model/distribution/deep-model',
            lessLibrary: 'libs/bower/less/dist/less',
            'require-css': 'libs/bower/require-css'
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
            },
            'jquery-autoNumeric': {
                // non-AMD module, relies on global jQuery
                deps: ['jquery']
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
