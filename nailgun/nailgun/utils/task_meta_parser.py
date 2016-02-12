import yaql
import six
import re
import abc
from nailgun.expression import Expression

#Code taken from bareon

class BaseParser(object):

    @abc.abstractmethod
    def __init__(self, expression, data={}, context={}):
        self.data = data
        self.context = context
        self.expression = expression

class YAQLParser(BaseParser):

    yaql_engine_options = {
        'yaql.limitIterators': 100,
        'yaql.treatSetsAsLists': True,
        'yaql.memoryQuota': 10000
    }

    def __init__(self, expression, data={}, *args, **kwargs):
        super(YAQLParser, self).__init__(expression, data)
        self.factory = yaql.YaqlFactory()
        self.parser = self.factory.create(options=self.yaql_engine_options)

    def evaluate(self):
        result = self.parser(self.expression).evaluate(data=self.data,context=self.context.create_child_context())
        return result

class LegacyParser(BaseParser):

    def evaluate(self):
        return Expression(
            self.expression, self.data).evaluate()

class Parser(object):

    yaql_re = re.compile(r'^\s*[\'\"]?yaql\s*=\s*[\'\"]?')

    def __init__(self, expression):
        self.expression = expression
        assert isinstance(self.expression, six.string_types)

    def evaluate(self):
        return self.get_parser().evaluate()

    def get_parser(self):
        if self.yaql_re.match(self.expression):
            wo_prefix = self.yaql_re.sub('', self.expression)
            return YAQLParser(wo_prefix)

        return LegacyParser(self.expression)