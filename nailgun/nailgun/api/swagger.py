"""
Swagger mixin class.
"""

from docutils.core import publish_doctree
import re
from xml.etree import ElementTree


OPERATIONS = ['GET', 'POST', 'PUT', 'DELETE', 'HEAD']

HTTP_RE = '\* (\d+) \((.*)\)'


class Swagger(object):
    def __init__(self):
        from nailgun.api.v1 import urls
        from nailgun.api.v1.handlers import base

        self.URLS = dict(zip(urls.urls[1::2], urls.urls[::2]))

        self.handlers = base.BaseHandler.__subclasses__()

    def get_spec(self):
        return {
            'swagger': '2.0',
            'info': self.get_info_object(),
            'basePath': '/api/v1',
            'paths': self.get_paths_object(),
            'definitions': {},
            'parameters': {},
            'responses': {},
            'securityDefinitions': {},
            'security': {},
            'tags': {},
            'externalDocs': {},
        }

    def get_info_object(self):
        return {
            'title': 'Fuel Nailgun API',
            'description': 'Fuel Nailgun API',
            'version': '1.0',
        }

    def get_paths_object(self):
        ret = {}

        for handler in self.handlers:
            url = self.URLS.get(handler.__name__)
            if not url:
                continue
            url = url.rstrip('$').rstrip('?')
            ret[url] = self.get_handler_info(handler)

        return ret

    def get_handler_info(self, handler):
        ret = {}

        for operation in OPERATIONS:
            if not hasattr(handler, operation):
                continue

            ret[operation.lower()] = self.get_handler_operation_info(
                handler, operation)

        return ret

    def get_handler_operation_info(self, handler, operation):
        op = getattr(handler, operation)
        op_doc = self.get_doctree(op)
        try:
            parsed_tree = self.get_doctree_field_lists(op_doc)
        except:
            parsed_tree = None

        summary = self.get_handler_summary(handler),
        if parsed_tree is None:
            summary = '{0} [INVALID DOCSTRING]'.format(summary)
            parameters = []
            responses = []
        else:
            parameters = self.get_handler_operation_parameters(parsed_tree)
            responses = self.get_handler_operation_responses(parsed_tree)

        return {
            'summary': summary,
            'description': self.get_handler_operation_description(op_doc),
            'produces': ['application/json'],
            'parameters': parameters,
            'responses': responses,
            #'responses': {
            #    '200': {
            #        'description': 'response',
            #    }
            #}
        }

    def get_doctree(self, operation):
        doc = operation.__doc__ or ''

        xmlstr = publish_doctree(doc).asdom().toxml()

        # hack for <emphasis>xxx</emphasis> inside the paragraphs
        xmlstr = xmlstr.replace('<emphasis>', '').replace('</emphasis>', '')

        return ElementTree.fromstring(xmlstr)

    def get_doctree_field_lists(self, doctree):
        ret = []

        block_quote = doctree.find('block_quote')

        if block_quote is not None:
            for field_list in block_quote.findall('field_list'):
                for field in field_list.findall('field'):
                    s = field.find('field_name').text.split(' ', 1)
                    if len(s) == 1:
                        type_ = s
                        name = ''
                    else:
                        type_, name = s

                    field_body = field.find('field_body')
                    paragraph = field_body.find('paragraph')
                    description = paragraph.text if paragraph is not None \
                        else 'NO DOC'

                    ret.append((type_, name, description))

        return ret

    def get_handler_summary(self, handler):
        if handler.__doc__:
            return handler.__doc__.strip()

        return '[NO DOC] {}'.format(handler.__name__)

    def get_handler_operation_parameters(self, parsed_doctree):
        ret = []

        for type_, name, description in parsed_doctree:
            if type_ == 'query':
                ret.append({
                    'name': name,
                    'in': 'query',
                    'description': description,
                    # TODO: parameter type
                })

        return ret

    def get_handler_operation_responses(self, parsed_doctree):
        ret = {}

        for type_, code, description in parsed_doctree:
            if type_ == 'statuscode':
                ret.setdefault(code, [])
                ret[code].append(description)

        return dict([
            (k, {'description': ' OR '.join(v)}) for k, v in ret.items()
        ])

    def get_handler_operation_description(self, doctree):
        ret = []

        el = doctree.find('paragraph')
        if el is not None:
            ret.append(' '.join(el.itertext()))

        el = doctree.find('block_quote')
        if el is not None:
            for p in el.findall('paragraph'):
                ret.append(' '.join(p.itertext()))

        if ret:
            return '\n\n'.join(ret)

        return '[NO DOC]'

    def get_handler_operation_description_old(self, handler, operation):
        handler_doc = '{}.{}'.format(handler.__name__, operation.__name__)

        if operation.__doc__:
            op_doc = unicode(operation.__doc__).strip()

            # strip out parameters -- they will be added to 'responses' value
            tmp = []
            for line in op_doc.split('\n'):
                if not (re.search(HTTP_RE, line) or
                        ':http:' in line or
                        ':returns:' in line):
                    tmp.append(line)
            op_doc = '\n'.join(tmp)

            op_doc = '{}\n{}'.format(handler_doc, op_doc)
        else:
            op_doc = '[NO DOC] {}'.format(handler_doc)

        # replace -- swagger UI renders only \n\n, with \n it just joins
        #  strings in one line
        return op_doc.replace('\n', '\n\n')

    def get_handler_operation_responses_old(self, handler, operation):
        responses = {}

        if not operation.__doc__:
            return {}

        op_doc = unicode(operation.__doc__).strip()

        for line in op_doc.split('\n'):
            s = re.search(HTTP_RE, line)
            if s:
                code, description = s.groups()
                responses[code] = {
                    'description': description,
                }

        return responses

