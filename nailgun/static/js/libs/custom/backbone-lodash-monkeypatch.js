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
define(['underscore', 'backbone'], function(_, Backbone) {
    // Adjust some collection functions to work properly with model.get.
    // Lodash supports some methods with predicate objects, not functions.
    // Underscore has only pure predicate functions.
    // We need to convert predicate objects to functions that use model's
    // get functionality -- otherwise model.property always returns undefined.

    var methods = ['collect', 'find', 'detect', 'filter', 'select',
        'reject', 'every', 'all', 'some', 'any',
        'max', 'min', 'first', 'head', 'take', 'initial', 'rest',
        'tail', 'drop', 'last'];

    // Mix in each Underscore method as a proxy to `Collection#models`.
    _.each(methods, function(method) {
        Backbone.Collection.prototype[method] = function() {
            var args = [].slice.call(arguments),
                predicate = args[0];

            if (_.isPlainObject(predicate)) {
                args[0] = function(model) {
                    return _.chain(predicate)
                        .pairs()
                        .every(function(pair) {
                            return _.isEqual(model.get(pair[0]), pair[1]);
                        })
                        .value();
                };
            }

            args.unshift(this.models);

            return _[method].apply(_, args);
        };
    });

    Backbone.Collection.prototype.findWhere = function(attrs) {
        var ret = this.where(attrs);
        if (ret.length > 0) {
            return ret[0];
        }
    };
});
