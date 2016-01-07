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
import _ from 'underscore';
import ExpressionParser from 'expression/parser';

    class ModelPath {
        constructor(path) {
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

        setModel(models, extraModels = {}) {
            this.model = extraModels[this.modelName] || models[this.modelName];
            if (!this.model) {
                throw new Error('No model with name "' + this.modelName + '" defined');
            }
            return this;
        }

        get(options) {
            return this.model.get(this.attribute, options);
        }

        set(value, options) {
            return this.model.set(this.attribute, value, options);
        }

        change(callback, context) {
            return this.model.on('change:' + this.attribute, callback, context);
        }
    }

    class ScalarWrapper {
        constructor(value) {
            this.value = value;
        }

        evaluate() {
            return this.value;
        }

        getValue() {
            return this.value;
        }
    }

    class SubexpressionWrapper {
        constructor(subexpression) {
            this.subexpression = subexpression;
        }

        evaluate() {
            return this.subexpression();
        }

        getValue() {
            return this.subexpression();
        }
    }

    class ModelPathWrapper {
        constructor(modelPathText) {
            this.modelPath = new ModelPath(modelPathText);
            this.modelPathText = modelPathText;
        }

        evaluate() {
            var expression = ExpressionParser.yy.expression;
            this.modelPath.setModel(expression.models, expression.extraModels);
            var result = this.modelPath.get();
            if (_.isUndefined(result)) {
                if (expression.strict) {
                    throw new TypeError('Value of ' + this.modelPathText + ' is undefined. Set options.strict to false to allow undefined values.');
                }
                result = null;
            }
            this.lastResult = result;
            expression.modelPaths[this.modelPathText] = this.modelPath;
            return this.modelPath;
        }

        getValue() {
            this.evaluate();
            return this.lastResult;
        }
    }

    export {ScalarWrapper, SubexpressionWrapper, ModelPathWrapper, ModelPath};
