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
define([], function() {
    'use strict';

    return {
        coccyxExtensions: {
            rejectRegisteredDeferreds: function() {
                _(this.deferreds).each(function(deferred) {
                    deferred[_(['abort', 'clear', 'reject']).find(function(method) {return deferred[method]})]();
                });
                this.deferreds = {};
            }
        },
        coccyxViewExtensions: {
            registerDeferred: function(deferred) {
                var that = this;
                this.deferreds = this.deferreds || {};
                deferred._coccyxId = deferred._coccyxId || _.uniqueId('coccyx');
                this.deferreds[deferred._coccyxId] = deferred;
                deferred.always(function() {
                    delete that.deferreds[deferred._coccyxId];
                });
                return deferred;
            },
            unregisterDeferred: function(deferred) {
                delete this.deferreds[deferred._coccyxId];
            }
        }
    };
});
