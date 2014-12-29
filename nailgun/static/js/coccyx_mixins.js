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
define(['underscore'], function(_) {
    'use strict';

    return {
        rejectRegisteredDeferreds: function() {
            _(this.deferreds).each(function(deferred) {
                var rejectMethod = deferred[_(['abort', 'clear', 'reject']).find(function(method) {return deferred[method];})];
                if (rejectMethod) {
                    rejectMethod();
                }
            });
            this.deferreds = {};
        },
        registerDeferred: function(deferred) {
            this.deferreds = this.deferreds || {};
            deferred._coccyxId = deferred._coccyxId || _.uniqueId('coccyx');
            this.deferreds[deferred._coccyxId] = deferred;
            deferred.always(_.bind(function() {
                delete this.deferreds[deferred._coccyxId];
            }, this));
            return deferred;
        },
        unregisterDeferred: function(deferred) {
            this.deferreds = this.deferreds || {};
            delete this.deferreds[deferred._coccyxId];
        }
    };
});
