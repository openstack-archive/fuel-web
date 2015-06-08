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
define(['underscore', 'expression/parser', 'expression/objects'], function(_, ExpressionParser, expressionObjects) {
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
            // FIXME(vkramskikh): currently Jison supports sharing state
            // only via ExpressionParser.yy. It is unsafe and could lead to
            // issues in case we start to use webworkers
            ExpressionParser.yy.expression = this;
            this.modelPaths = {};
            this.extraModels = extraModels;
            var value = this.compiledExpression.evaluate();
            delete this.extraModels;
            return value;
        },
        getCompiledExpression: function() {
            var cacheEntry = this.expressionCache[this.expressionText];
            if (!cacheEntry) {
                cacheEntry = this.expressionCache[this.expressionText] = ExpressionParser.parse(this.expressionText);
            }
            return cacheEntry;
        },
        expressionCache: {}
    });

    _.extend(ExpressionParser.yy, expressionObjects);

    return Expression;
});
