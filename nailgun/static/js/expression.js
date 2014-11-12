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
        if (!this) return new Expression(expressionText, models, options);
        this.strict = options && !_.isUndefined(options.strict) ? options.strict : true;
        this.expressionText = expressionText;
        this.models = models || {};
        this.compiledExpression = this.getCompiledExpression();
        return this;
    }
    _.extend(Expression.prototype, {
        evaluate: function(extraModels) {
            this.modelPaths = {};
            this.knownModels = extraModels ? _.extend({}, this.models, extraModels) : this.models;
            var value = this.compiledExpression.evaluate();
            delete this.knownModels;
            return value;
        },
        getCompiledExpression: function() {
            ExpressionParser.yy.expression = this;
            var key = String(this.strict) + ' ' + this.expressionText;
            if (!this.expressionCache[key]) {
                this.expressionCache[key] = ExpressionParser.parse(this.expressionText);
            }
            return this.expressionCache[key];
        },
        expressionCache: {}
    });

    _.extend(ExpressionParser.yy, expressionObjects);

    return Expression;
});
