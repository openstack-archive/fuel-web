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
define(['jquery', 'underscore', 'react', 'react.backbone'], function($, _, React) {
    'use strict';

    return {
        backboneMixin: React.BackboneMixin,
        pollingMixin: function(updateInterval) {
            updateInterval = updateInterval * 1000;
            return {
                scheduleDataFetch: function() {
                    var shouldDataBeFetched = !_.isFunction(this.shouldDataBeFetched) || this.shouldDataBeFetched();
                    if (this.isMounted() && !this.activeTimeout && shouldDataBeFetched) {
                        this.activeTimeout = $.timeout(updateInterval).done(_.bind(this.startPolling, this));
                    }
                },
                startPolling: function(force) {
                    var shouldDataBeFetched = force || !_.isFunction(this.shouldDataBeFetched) || this.shouldDataBeFetched();
                    if (shouldDataBeFetched) {
                        this.stopPolling();
                        this.fetchData().always(_.bind(this.scheduleDataFetch, this));
                    }
                },
                stopPolling: function() {
                    if (this.activeTimeout) {
                        this.activeTimeout.clear();
                    }
                    delete this.activeTimeout;
                },
                componentDidMount: function() {
                    this.startPolling();
                }
            };
        }
    };
});
