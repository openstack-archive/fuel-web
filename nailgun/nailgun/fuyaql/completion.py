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


class FuCompleter(object):
    def __init__(self, words):
        self.words = words
        self.prefix = None
        self.matches = None

    def complete(self, text, index):
        """Check for matches words and return them

        :param text: text to match
        :type text: str
        :param index: index to calculate completion results
        :type index: int
        :return: matched words if any, None if fails
        """
        if text != self.prefix:
            self.matches = [m for m in self.words if m.startswith(text)]
            self.prefix = text
        try:
            return self.matches[index]
        except IndexError:
            return None
