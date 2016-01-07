/*
 * Copyright 2015 Mirantis, Inc.
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
/*eslint object-shorthand: 0*/
define(['../../helpers'], function() {
    'use strict';
    function WelcomePage(remote) {
        this.remote = remote;
    }

    WelcomePage.prototype = {
        constructor: WelcomePage,
        skip: function(strictCheck) {
            return this.remote
                .waitForCssSelector('.welcome-page', 3000)
                .then(function() {
                    return this.parent
                        .clickByCssSelector('.welcome-button-box button')
                        .waitForDeletedByCssSelector('.welcome-button-box button', 2000)
                        .then(
                            function() {return true;},
                            function() {return !strictCheck;}
                        );
                    },
                    function() {return !strictCheck;}
                );
        }
    };
    return WelcomePage;
});
