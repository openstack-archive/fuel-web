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

    var objects = {};

    objects.ScalarWrapper = function(value) {
        this.value = value;
    }
    objects.ScalarWrapper.prototype.evaluate = objects.ScalarWrapper.prototype.getValue = function() {
        return this.value;
    };

    objects.SubexpressionWrapper = function(subexpression) {
        this.subexpression = subexpression;
    }
    objects.SubexpressionWrapper.prototype.evaluate = objects.SubexpressionWrapper.prototype.getValue = function() {
        return this.subexpression();
    };

    objects.ModelPathWrapper = function(yytext, expression, strict) {
        this.yytext = yytext;
        this.expression = expression;
        this.modelPath = require('utils').parseModelPath(yytext, expression.models);
        this.strict = strict;
    }
    objects.ModelPathWrapper.prototype.evaluate = function() {
        var result = this.modelPath.get();
        if (_.isUndefined(result)) {
            if (this.strict) {
                throw new TypeError('Value of ' + this.yytext + ' is undefined. Set options.strict to false to allow undefined values.');
            }
            result = null;
        }
        this.expression.modelPaths[this.yytext] = this.modelPath;
        return this.modelPath;
    };
    objects.ModelPathWrapper.prototype.getValue = function() {
        return this.evaluate().get();
    };

    return objects;
});
