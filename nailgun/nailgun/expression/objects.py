#    Copyright 2014 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


class ScalarWrapper(object):
    def __init__(self, value):
        self.value = value

    def evaluate(self):
        return self.value

    def __call__(self):
        return self.value


class SubexpressionWrapper(object):
    def __init__(self, subexpression):
        self.subexpression = subexpression

    def evaluate(self):
        self.value = self.subexpression()
        return self.value

    def __call__(self):
        self.evaluate()
        return self.value


class ModelPath(object):
    def __init__(self, path):
        path_parts = path.split(':')
        if len(path_parts) == 1:
            self.model_name = 'default'
            self.attribute = path_parts[0]
        else:
            self.model_name = path_parts[0]
            self.attribute = path_parts[1]

    def set_model(self, models):
        if self.model_name not in models:
            raise KeyError('No model with name "{0}" defined'.format(
                self.model_name))
        self.model = models[self.model_name]

    def get_value(self):
        def get_attribute_value(model, path):
            value = model[path.pop(0)]
            return get_attribute_value(value, path) if len(path) else value
        return get_attribute_value(self.model, self.attribute.split('.'))


class ModelPathWrapper(object):
    def __init__(self, path, expression):
        self.path = path
        self.model_path = ModelPath(path)
        self.expression = expression

    def evaluate(self):
        self.model_path.set_model(self.expression.models)
        result = None
        try:
            result = self.model_path.get_value()
        except (KeyError, AttributeError):
            if self.expression.strict:
                raise TypeError(
                    'Value of {0} is undefined. Set options.strict'
                    ' to false to allow undefined values.'.format(self.path))
        self.value = result
        return self.model_path

    def __call__(self):
        self.evaluate()
        return self.value
