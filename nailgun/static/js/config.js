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
            jquery: 'js/libs/bower/jquery/js/jquery',
            'jquery-cookie': 'js/libs/bower/jquery-cookie/jquery.cookie',
            'jquery-timeout': 'js/libs/custom/jquery.timeout',
            'jquery-ui': 'js/libs/custom/jquery-ui-1.10.2.custom',
            'jquery-autoNumeric': 'js/libs/bower/autoNumeric/js/autoNumeric',
            utils: 'js/utils',
            expression: 'js/expression',
            keystone_client: 'js/keystone_client',
            lodash: 'js/libs/bower/lodash/js/lodash.compat',
            underscore: 'js/libs/bower/lodash/js/lodash.compat',
            backbone: 'js/libs/bower/backbone/backbone',
            'backbone-lodash-monkeypatch': 'js/libs/custom/backbone-lodash-monkeypatch',
            react: 'js/libs/bower/react/js/react-with-addons',
            JSXTransformer: 'js/libs/bower/react/js/JSXTransformer',
            jsx: 'js/libs/bower/jsx-requirejs-plugin/jsx',
            'react.backbone': 'js/libs/custom/react.backbone',
            stickit: 'js/libs/bower/backbone.stickit/js/backbone.stickit',
            coccyx: 'js/libs/custom/coccyx',
            cocktail: 'js/libs/bower/cocktail/Cocktail',
            routefilter: 'js/libs/bower/routefilter/backbone.routefilter.min',
            bootstrap: 'js/libs/custom/bootstrap.min',
            text: 'js/libs/bower/requirejs-text/js/text',
            json: 'js/libs/bower/requirejs-plugins/json',
            i18next: 'js/libs/bower/i18next/js/i18next-1.7.1',
            deepModel: 'js/libs/bower/backbone-deep-model/js/deep-model',
            lessLibrary: 'js/libs/bower/less/js/less-1.5.1',
            'require-css': 'js/libs/bower/require-css',
            'require-less': 'js/require-less',
            i18n: 'js/i18n',
            app: 'js/app',
            models: 'js/models',
            backbone_view_wrapper: 'js/backbone_view_wrapper',
            views: 'js/views',
            view_mixins: 'js/view_mixins',
            component_mixins: 'js/component_mixins',
            controls: 'js/views/controls'
        },
        shim: {
            'expression/parser': {
                exports: 'parser'
            },
            stickit: {
                deps: ['backbone']
            },
            deepModel: {
                deps: ['backbone']
            },
            coccyx: {
                deps: ['backbone', 'underscore'],
                exports: 'Coccyx'
            },
            bootstrap: {
                deps: ['jquery']
            },
            i18next: {
                deps: ['jquery'],
                exports: 'i18n'
            },
            'jquery-cookie': {
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
