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
            jquery: 'js/libs/bower/jquery/jquery',
            'jquery-cookie': 'js/libs/bower/jquery-cookie/jquery.cookie',
            'jquery-ui': 'js/libs/bower/jquery-ui/ui',
            'jquery-autoNumeric': 'js/libs/bower/autoNumeric/autoNumeric',
            utils: 'js/utils',
            expression: 'js/expression',
            keystone_client: 'js/keystone_client',
            lodash: 'js/libs/bower/lodash/dist/lodash.compat',
            underscore: 'js/libs/bower/lodash/dist/lodash.compat',
            backbone: 'js/libs/bower/backbone/backbone',
            'backbone-lodash-monkeypatch': 'js/libs/custom/backbone-lodash-monkeypatch',
            classnames: 'js/libs/bower/classnames/index',
            react: 'js/libs/bower/react/react-with-addons',
            JSXTransformer: 'js/libs/bower/react/JSXTransformer',
            jsx: 'js/libs/bower/jsx-requirejs-plugin/js/jsx',
            'react.backbone': 'js/libs/custom/react.backbone',
            stickit: 'js/libs/bower/backbone.stickit/backbone.stickit',
            coccyx: 'js/libs/custom/coccyx',
            cocktail: 'js/libs/bower/cocktail/Cocktail',
            routefilter: 'js/libs/bower/routefilter/dist/backbone.routefilter.min',
            bootstrap: 'js/libs/custom/bootstrap.min',
            text: 'js/libs/bower/requirejs-text/text',
            json: 'js/libs/bower/requirejs-plugins/src/json',
            i18next: 'js/libs/bower/i18next/release/i18next-1.7.1',
            deepModel: 'js/libs/bower/backbone-deep-model/distribution/deep-model',
            lessLibrary: 'js/libs/bower/less/dist/less',
            'require-css': 'js/libs/bower/require-css',
            'require-less': 'js/require-less',
            i18n: 'js/i18n',
            dispatcher: 'js/dispatcher',
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
            coccyx: {
                deps: ['backbone', 'underscore'],
                exports: 'Coccyx'
            },
            classnames: {
                exports: 'classNames'
            },
            bootstrap: {
                deps: ['jquery']
            },
            i18next: {
                deps: ['jquery'],
                exports: 'i18n'
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
