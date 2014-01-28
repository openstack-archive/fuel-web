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

(function() {
    'use strict';
    var compressed = true;
//>>excludeStart("compressed", pragmas.compressed);
    compressed = false;
//>>excludeEnd("compressed");
    if (compressed) {
        // in production mode we use compressed CSS
        define(['require-css/css!/static/css/styles'], function() {
            return {};
        });
    } else {
        // in development mode we load original LESS
        // working around requirejs define counter
        var _define = define;
        _define(['less', 'jquery'], function(less, $) {
            var link = $('<link/>', {
                href: '/static/css/styles.less?_=' + (new Date()).getTime(),
                rel: 'stylesheet/less'
            });
            link.appendTo('head');
            less.sheets.push(link[0]);
            less.refresh();
        });
    }
}());
