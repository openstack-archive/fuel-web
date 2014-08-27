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
define(['expression_parser'], function(ExpressionParser) {
    'use strict';

    function ScalarWrapper(value) {
        this.value = value;
    }
    ScalarWrapper.prototype.evaluate = ScalarWrapper.prototype.getValue = function() {
        return this.value;
    };

    function SubexpressionWrapper(subexpression) {
        this.subexpression = subexpression;
    }
    SubexpressionWrapper.prototype.evaluate = SubexpressionWrapper.prototype.getValue = function() {
        return this.subexpression();
    };

    function ModelPathWrapper(yytext, expression, strict) {
        this.yytext = yytext;
        this.expression = expression;
        this.modelPath = require('utils').parseModelPath(yytext, expression.models);
        this.strict = strict;
    }
    ModelPathWrapper.prototype.evaluate = function() {
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
    ModelPathWrapper.prototype.getValue = function() {
        return this.evaluate().get();
    };

    function Expression(expressionText, models, options) {
        if (!(this instanceof Expression)) {
            return new Expression(expressionText, models, options);
        }
        options = _.extend({strict: true}, options);
        _.extend(this, {
            expressionText: expressionText,
            models: models || {},
            options: options,
            modelPaths: {}
        });
        ExpressionParser.yy = {
            _: _,
            ScalarWrapper: ScalarWrapper,
            SubexpressionWrapper: SubexpressionWrapper,
            ModelPathWrapper: ModelPathWrapper,
            expression: this
        };
        this.compiledExpression = ExpressionParser.parse(expressionText);
        return this;
    }
    Expression.prototype.evaluate = function() {
        return this.compiledExpression.evaluate();
    }

    return Expression;
});
