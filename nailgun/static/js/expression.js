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
define(['expression/parser', 'expression/objects'], function(ExpressionParser, expressionObjects) {
    'use strict';

    function Expression(expressionText, models, options) {
        if (!(this instanceof Expression)) {
            return new Expression(expressionText, models, options);
        }
        options = _.extend({strict: true}, options);
        _.extend(this, {
            expressionText: expressionText,
            models: models || {},
            options: options
        });
        _.extend(ExpressionParser.yy, expressionObjects, {expression: this});
        this.compiledExpression = ExpressionParser.parse(expressionText);
        return this;
    }
    Expression.prototype.evaluate = function(extraModels) {
        this.modelPaths = {};
        this.knownModels = extraModels ? _.extend({}, this.models, extraModels) : this.models;
        var value = this.compiledExpression.evaluate();
        delete this.knownModels;
        return value;
    };

    return Expression;
});
