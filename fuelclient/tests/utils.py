#    Copyright 2013 Mirantis, Inc.
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

import six


def _get_elems_from_parsed_output(string_to_parse):
    parsed = []
    # get rid of row delimiters
    for line in string_to_parse.split('\n'):
        if not line or line.startswith('+'):
            continue

        elems = [elem.strip() for elem in line.split('|') if elem]
        parsed.append(elems)

    return parsed


def list_output_parser(string_to_parse):
    to_check = []
    parsed = _get_elems_from_parsed_output(string_to_parse)

    # header always will be the first element in `parsed`
    # we use header data to build make data structure suitable
    # for further analisys
    fields_names, parsed = parsed[0], parsed[1:]
    for parsed_elem in parsed:
        elem_to_check = dict(zip(fields_names, parsed_elem))
        to_check.append(elem_to_check)

    return to_check


def eval_output_to_verify(name, value):
    caster = {
        ('name', 'mode', 'status', 'net_provider'):
        lambda value: str(value),

        ('release_id',): lambda value: int(value),

        ('changes',): lambda value: eval(value)
    }
    to_return = [cast_func(value) for fields, cast_func in
                 six.iteritems(caster) if name in fields].pop()
    return to_return
