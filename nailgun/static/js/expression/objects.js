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
define(['underscore'], function(_) {
    'use strict';

    function ModelPath(path) {
        var pathParts = path.split(':');
        if (_.isUndefined(pathParts[1])) {
            this.modelName = 'default';
            this.attribute = pathParts[0];
        } else {
            this.modelName = pathParts[0];
            this.attribute = pathParts[1];
        }
        return this;
    }
    _.extend(ModelPath.prototype, {
        setModel: function(models) {
            this.model = models[this.modelName];
            if (!this.model) {
                throw new Error('No model with name "' + this.modelName + '" defined');
            }
            return this;
        },
        get: function(options) {
            return this.model.get(this.attribute, options);
        },
        set: function(value, options) {
            return this.model.set(this.attribute, value, options);
        },
        change: function(callback, context) {
            return this.model.on('change:' + this.attribute, callback, context);
        }
    });

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
        this.modelPath = new ModelPath(yytext);
        this.strict = strict;
    }
    ModelPathWrapper.prototype.evaluate = function() {
        this.modelPath.setModel(this.expression.knownModels);
        var result = this.modelPath.get();
        if (_.isUndefined(result)) {
            if (this.strict) {
                throw new TypeError('Value of ' + this.yytext + ' is undefined. Set options.strict to false to allow undefined values.');
            }
            result = null;
        }
        this.lastResult = result;
        this.expression.modelPaths[this.yytext] = this.modelPath;
        return this.modelPath;
    };
    ModelPathWrapper.prototype.getValue = function() {
        this.evaluate();
        return this.lastResult;
    };

    return {
        ScalarWrapper: ScalarWrapper,
        SubexpressionWrapper: SubexpressionWrapper,
        ModelPathWrapper: ModelPathWrapper,
        ModelPath: ModelPath
    };
});
