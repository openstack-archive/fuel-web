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

import sys


def print_error(message):
    sys.stderr.write(message + "\n")
    exit(1)


def recur_get(multi_level_dict, key_chain):
    """Method accesses some field in nested dictionaries

    :returns: value for last key in key_chain in last dictionary
    """
    if not isinstance(multi_level_dict[key_chain[0]], dict):
        return multi_level_dict[key_chain[0]]
    else:
        return recur_get(multi_level_dict[key_chain[0]], key_chain[1:])


def format_table(data, acceptable_keys=None, subdict_keys=None):
    """Format list of dicts to ascii table

    :acceptable_keys list(str): list of keys for which to create table
                                also specifies their order
    :subdict_keys list(tuple(str)): list of key chains (tuples of key strings)
                                    which are applied to dictionaries
                                    to extract values
    """
    if subdict_keys:
        for key_chain in subdict_keys:
            for data_dict in data:
                data_dict[key_chain[0]] = recur_get(data_dict, key_chain)
    if acceptable_keys:
        rows = [tuple([value[key] for key in acceptable_keys])
                for value in data]
        header = tuple(acceptable_keys)
    else:
        rows = [tuple(x.values()) for x in data]
        header = tuple(data[0].keys())
    number_of_columns = len(header)
    column_widths = dict(
        zip(
            range(number_of_columns),
            (len(str(x)) for x in header)
        )
    )

    for row in rows:
        column_widths.update(
            (index, max(column_widths[index], len(str(element))))
            for index, element in enumerate(row)
        )
    row_template = ' | '.join(
        '%%-%ss' % column_widths[i] for i in range(number_of_columns)
    )

    return '\n'.join(
        (row_template % header,
         '-|-'.join(column_widths[column_index] * '-'
                    for column_index in range(number_of_columns)),
         '\n'.join(row_template % x for x in rows))
    )


def quote_and_join(words):
    words = list(words)
    if len(words) > 1:
        return '{0} and "{1}"'.format(
            ", ".join(
                map(
                    lambda x: '"{0}"'.format(x),
                    words
                )[0:-1]
            ),
            words[-1]
        )
    else:
        return '"{0}"'.format(words[0])
