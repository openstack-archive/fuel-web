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

define(['../../helpers'], function(Helpers) {
    'use strict';
    function WelcomePage(remote) {
        this.remote = remote;
    }

    WelcomePage.prototype = {
        constructor: WelcomePage,
        skip: function(strictCheck) {
            return this.remote
                .getCurrentUrl()
                .then(function(url) {
                    if (url == Helpers.serverUrl + '/#welcome') {
                        return this.parent
                            .setFindTimeout(2000)
                            .clickByCssSelector('.welcome-button-box button')
                            .waitForDeletedByCssSelector('.welcome-button-box button')
                            .then(
                                function() {return true},
                                function() {return !strictCheck}
                            );
                    } else {
                        return true;
                    }
                });
        }
    };
    return WelcomePage;
});
