#    Copyright 2016 Mirantis, Inc.
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
import traceback

import six

# Size of the new level text indent when rendering report
REPORT_INDENT_SIZE = 4

# Symbol to mark error nodes when rendering report
REPORT_FAILURE_POINTER = '> '


class ReportNode(object):
    """Basic unit of Reports tree.

    Any ReportNode could be rendered as report with all children tree.
    """

    text = None
    children = None
    _failed = False

    def __init__(self, text=None, children=None, failed=False):
        """Basic unit of report tree.

        :param text: node text
        :type text: basestring
        :param children: list of child ReportNodes
        :type children: list[ReportNode]
        :param failed: failure flag that affects rendering
        :type failed: boolean
        """
        self.text = text
        self.children = children if children is not None else []
        self._failed = failed

    def _render(self, level=0):
        """Render report tree to the validation result and messages list.

        :param level: indent level
        :type level: int
        :return: failed flag and list of message lines
        :rtype: (list[str], bool)
        """
        indent_size = REPORT_INDENT_SIZE * level
        error_indent_size = \
            max(indent_size - len(REPORT_FAILURE_POINTER), 0)
        indent = indent_size * ' '
        error_indent = error_indent_size * ' '

        lines = []
        failed = self._failed
        # no indent is required if we have no output on this level
        next_level = level + (1 if self.text else 0)
        for child in self.children:
            child_strings, child_failed = child._render(next_level)
            failed = child_failed or failed
            lines.extend(child_strings)

        if self.text:
            output = ''.join([
                error_indent if failed else indent,
                REPORT_FAILURE_POINTER if failed else '',
                u"{}".format(self.text)
            ])
            lines.insert(0, output)

        return lines, failed

    def add_nodes(self, *nodes):
        """Add single node or several nodes.

        :param nodes: one or several report nodes
        :type nodes: list[ReportNode]
        :raises: InspectionConfigurationError
        """
        for node in nodes:
            if not isinstance(node, ReportNode):
                raise TypeError(
                    u"This value is not ReportNode {0}".format(node))
            self.children.append(node)
        return self

    def _process_message_or_exception(
            self, prefix, msg_or_exc, *args, **kwargs):
        if isinstance(msg_or_exc, six.string_types):
            self.add_nodes(
                ReportNode(prefix + u'{}'.format(msg_or_exc))
            )

        elif isinstance(msg_or_exc, Exception):
            self.add_nodes(
                ReportNode(prefix + (msg_or_exc.message or repr(msg_or_exc)))
            )
            tb = traceback.print_exc(msg_or_exc)
            if tb:
                self.error(tb)

        self.add_nodes(
            *(
                ReportNode(prefix + u'{}'.format(arg))
                for arg in args
            )
        )
        self.add_nodes(
            *(
                ReportNode(prefix + u'{}: {}'.format(key, kwargs[key]))
                for key in kwargs
            )
        )
        return

    def error(self, msg_or_exc, *args, **kwargs):
        """Add child ReportNode with error message.

        :param msg_or_exc: message or exception
        :type msg_or_exc: str|basestring|Exception

        :return: self
        :rtype: ReportNode
        """
        self._failed = True
        self._process_message_or_exception(
            u"ERROR: ", msg_or_exc, *args, **kwargs)
        return self

    def warning(self, msg_or_exc, *args, **kwargs):
        """Add child ReportNode with warning message.

        :param msg_or_exc: message or exception
        :type msg_or_exc: str|basestring|Exception

        :return: self
        :rtype: ReportNode
        """
        self._process_message_or_exception(
            u"WARNING: ", msg_or_exc, *args, **kwargs)
        return self

    def info(self, msg_or_exc, *args, **kwargs):
        """Add child ReportNode with info message.

        :param msg: text
        :type msg: str|basestring

        :return: self
        :rtype: ReportNode
        """
        self._process_message_or_exception(
            u"INFO: ", msg_or_exc, *args, **kwargs)
        return self

    def render(self, add_summary=True):
        """Render report tree to the text.

        :param add_summary: include statistics and result
        :type add_summary: bool

        :return: report strings
        :rtype: str|basestring
        """
        strings, _ = self._render()

        if add_summary:
            strings.append('')
            fail_count = self.count_failures()
            if fail_count:
                strings += [
                    u'Failure!',
                    u'Please fix {} errors listed above.'.format(fail_count)
                ]
            else:
                strings += [
                    u'Success!'
                ]

        return "\n".join(strings)

    def count_failures(self, start_from=0):
        """Count failure messages inside report.

        :param start_from: start count from
        :type start_from: int
        :return: errors count
        :rtype: int
        """
        count = start_from
        if self._failed:
            count += 1
        for child in self.children:
            count = child.count_failures(count)
        return count

    def is_failed(self):
        """Is this report about failure.

        :return: is failed
        :rtype: boolean
        """
        return bool(self.count_failures())
