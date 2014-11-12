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

import ply.lex
import ply.yacc

from nailgun.errors import errors
from nailgun.expression.objects import ModelPathWrapper
from nailgun.expression.objects import ScalarWrapper
from nailgun.expression.objects import SubexpressionWrapper

tokens = (
    'NUMBER', 'STRING', 'TRUE', 'FALSE', 'NULL', 'AND', 'OR', 'NOT', 'IN',
    'EQUALS', 'NOT_EQUALS', 'LPAREN', 'RPAREN',
    'MODELPATH',
)


def t_NUMBER(t):
    r'-?\d+'
    t.value = int(t.value)
    return t


def t_STRING(t):
    r'(?P<openingquote>["\']).*?(?P=openingquote)'
    t.value = t.value[1:-1]
    return t


def t_TRUE(t):
    r'true'
    t.value = True
    return t


def t_FALSE(t):
    r'false'
    t.value = False
    return t


def t_NULL(t):
    r'null'
    t.value = None
    return t


t_AND = r'and'
t_OR = r'or'
t_NOT = r'not'
t_IN = r'in'
t_MODELPATH = r'\w*?\:[\w\.\-]+'
t_EQUALS = r'=='
t_NOT_EQUALS = r'!='
t_LPAREN = r'\('
t_RPAREN = r'\)'

t_ignore = ' \t\r\n'


def t_error(t):
    errors.LexError("Illegal character '%s'" % t.value[0])
    t.lexer.skip(1)


ply.lex.lex()

expression = None

precedence = (
    ('left', 'OR'),
    ('left', 'AND'),
    ('left', 'EQUALS', 'NOT_EQUALS'),
    ('left', 'IN', 'NOT'),
)


def p_expression_binop(p):
    """expression : expression EQUALS expression
                  | expression NOT_EQUALS expression
                  | expression OR expression
                  | expression AND expression
                  | expression IN expression
    """
    result, arg1, op, arg2 = p
    if op == '==':
        result = lambda: arg1() == arg2()
    elif op == '!=':
        result = lambda: arg1() != arg2()
    elif op == 'or':
        result = lambda: arg1() or arg2()
    elif op == 'and':
        result = lambda: arg1() and arg2()
    elif op == 'in':
        result = lambda: arg1() in arg2()
    p[0] = SubexpressionWrapper(result)


def p_not_expression(p):
    """expression : NOT expression
    """
    subexpression = p[2]
    p[0] = SubexpressionWrapper(lambda: not subexpression())


def p_expression_group(p):
    """expression : LPAREN expression RPAREN
    """
    p[0] = p[2]


def p_expression_scalar(p):
    """expression : NUMBER
                  | STRING
                  | NULL
                  | TRUE
                  | FALSE
    """
    p[0] = ScalarWrapper(p[1])


def p_expression_modelpath(p):
    """expression : MODELPATH
    """
    p[0] = ModelPathWrapper(p[1], expression)


def p_error(p):
    raise errors.ParseError("Syntax error at '%s'" % getattr(p, 'value', ''))


parser = ply.yacc.yacc(debug=False, write_tables=False)


def parse(expr):
    global expression
    expression = expr
    return parser.parse(expression.expression_text)
