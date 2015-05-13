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

    var serverHost = '127.0.0.1',
        serverPort = process.env.SERVER_PORT || 5544,
        serverUrl = 'http://' + serverHost + ':' + serverPort,
        username = 'admin',
        password = 'admin';

    return {
        username: username,
        password: password,
        serverUrl: serverUrl,
        clickLinkByText: function(remote, cssSelector, linkText) {
            return remote
                .setFindTimeout(1000)
                .findAllByCssSelector(cssSelector)
                .then(function(links) {
                    return links.reduce(function(matchFound, link) {
                        return link.getVisibleText().then(function(text) {
                            if (text == linkText) {
                                link.click();
                                return true;
                            }
                            return matchFound;
                        });
                    }, false);
                });
        }
    };
});
