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

//>>excludeStart("compressed", pragmas.compressed);
require(['./config'], function(config) {
    'use strict';
    requirejs.config(config);
//>>excludeEnd("compressed");
    require([
        'jquery',
        'underscore',
        'backbone',
        'stickit',
        'coccyx',
        'react',
        'react.backbone',
        'cocktail',
        'routefilter',
        'i18next',
        'bootstrap',
        'jquery-cookie',
        'jquery-checkbox',
        'jquery-timeout',
        'jquery-ui',
        'jquery-autoNumeric',
        'text',
//>>excludeStart("compressed", pragmas.compressed);
        'jsx',
//>>excludeEnd("compressed");
        'less!/static/css/styles',
        'app'
    ], function() {
        require('app').initialize();
    });
//>>excludeStart("compressed", pragmas.compressed);
});
//>>excludeEnd("compressed");
