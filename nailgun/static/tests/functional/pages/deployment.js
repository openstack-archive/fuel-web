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

define(['underscore',
        '../../helpers'], function(_, Helpers) {
    'use strict';
    function DeploymentPage(remote) {
        this.remote = remote;
    }

    DeploymentPage.prototype = {
        constructor: DeploymentPage,
        isDeploymentButtonVisible: function() {
            return this.remote
                .setFindTimeout(100)
                    .findByCssSelector('button.deploy-btn')
                    .then(_.constant(true), _.constant(false));
        }
    };
    return DeploymentPage;
});
