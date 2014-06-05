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

import curses
from functools import partial
from itertools import chain
import math
from operator import itemgetter
import os
import sys
from time import sleep
import urllib2

from fuelclient.cli.error import DeployProgressError
from fuelclient.cli.error import exit_with_error


def format_table(data, acceptable_keys=None, column_to_join=None):
    """Format list of dicts to table in a string form

    :acceptable_keys list(str): list of keys for which to create table
                                also specifies their order
    """
    if column_to_join is not None:
        for data_dict in data:
            for column_name in column_to_join:
                data_dict[column_name] = u", ".join(
                    sorted(data_dict[column_name])
                )
    if acceptable_keys is not None:
        rows = [tuple(value[key] for key in acceptable_keys)
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
            (index, max(column_widths[index], len(unicode(element))))
            for index, element in enumerate(row)
        )
    row_template = u' | '.join(
        u"{{{0}:{1}}}".format(idx, width)
        for idx, width in column_widths.iteritems()
    )

    return u'\n'.join(
        (row_template.format(*header),
         u'-|-'.join(column_widths[column_index] * u'-'
                     for column_index in range(number_of_columns)),
         u'\n'.join(row_template.format(*map(unicode, x))
                    for x in rows))
    )


def quote_and_join(words):
    """quote_and_join - performs listing of objects and returns string.
    """
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


def get_bar_for_progress(full_width, progress):
    """get_bar_for_progress - returns string with a width of 'full_width'
    which illustrates specific progress value.
    """
    number_of_equal_signs = int(
        math.ceil(progress * float(full_width - 2) / 100)
    )
    return "[{0}{1}{2}]".format(
        "=" * number_of_equal_signs,
        ">" if number_of_equal_signs < full_width - 2 else "",
        " " * (full_width - 3 - number_of_equal_signs)
    )


def download_snapshot_with_progress_bar(url, directory=os.path.curdir):
    """downloads file from specific 'url' with progress bar and save it
    to some 'directory'.
    """
    if not os.path.exists(directory):
        exit_with_error("Folder {0} doesn't exist.".format(directory))
    file_name = os.path.join(
        os.path.abspath(directory),
        url.split('/')[-1]
    )
    download_handle = urllib2.urlopen(url)
    with open(file_name, 'wb') as file_handle:
        meta = download_handle.info()
        file_size = int(meta.getheaders("Content-Length")[0])
        print("Downloading: {0} Bytes: {1}".format(url, file_size))
        file_size_dl = 0
        block_size = 8192
        bar = partial(get_bar_for_progress, 80)
        while True:
            data_buffer = download_handle.read(block_size)
            if not data_buffer:
                break
            file_size_dl += len(data_buffer)
            file_handle.write(data_buffer)
            progress = int(100 * float(file_size_dl) / file_size)
            sys.stdout.write("\r{0}".format(
                bar(progress)
            ))
            sys.stdout.flush()
            sleep(1 / 10)
        print()


def print_deploy_progress(deploy_task):
    """Receives 'deploy_task' and depending on terminal availability
    starts progress printing routines with or without curses.
    """
    try:
        terminal_screen = curses.initscr()
        print_deploy_progress_with_terminal(deploy_task, terminal_screen)
    except curses.error:
        print_deploy_progress_without_terminal(deploy_task)


def print_deploy_progress_without_terminal(deploy_task):
    print("Deploying changes to environment with id={0}".format(
        deploy_task.env.id
    ))
    message_len = 0
    try:
        for progress, nodes in deploy_task:
            sys.stdout.write("\r" * message_len)
            message_len = 0
            deployment_message = "[Deployment: {0:3}%]".format(progress)
            sys.stdout.write(deployment_message)
            message_len += len(deployment_message)
            for index, node in enumerate(nodes):
                node_message = "[Node{id:2} {progress:3}%]".format(
                    **node.data
                )
                message_len += len(node_message)
                sys.stdout.write(node_message)
        print("\nFinished deployment!")
    except DeployProgressError as de:
        print(de.message)


def print_deploy_progress_with_terminal(deploy_task, terminal_screen):
    scr_width = terminal_screen.getmaxyx()[1]
    curses.noecho()
    curses.cbreak()
    total_progress_bar = partial(get_bar_for_progress, scr_width - 17)
    node_bar = partial(get_bar_for_progress, scr_width - 28)
    env_id = deploy_task.env.id
    try:
        for progress, nodes in deploy_task:
            terminal_screen.refresh()
            terminal_screen.addstr(
                0, 0,
                "Deploying changes to environment with id={0}".format(
                    env_id
                )
            )
            terminal_screen.addstr(
                1, 0,
                "Deployment: {0} {1:3}%".format(
                    total_progress_bar(progress),
                    progress
                )
            )
            for index, node in enumerate(nodes):
                terminal_screen.addstr(
                    index + 2, 0,
                    "Node{id:3} {status:13}: {bar} {progress:3}%"
                    .format(bar=node_bar(node.progress), **node.data)
                )
    except DeployProgressError as de:
        close_curses()
        print(de.message)
    finally:
        close_curses()


def close_curses():
    curses.echo()
    curses.nocbreak()
    curses.endwin()


def print_health_check(env):
    tests_states = [{"status": "not finished"}]
    finished_tests = set()
    test_counter, total_tests_count = 1, None
    while not all(map(
            lambda t: t["status"] == "finished",
            tests_states
    )):
        tests_states = env.get_state_of_tests()
        all_tests = list(chain(*map(
            itemgetter("tests"),
            filter(
                env.is_in_running_test_sets,
                tests_states
            ))))
        if total_tests_count is None:
            total_tests_count = len(all_tests)
        all_finished_tests = filter(
            lambda t: "running" not in t["status"],
            all_tests
        )
        new_finished_tests = filter(
            lambda t: t["name"] not in finished_tests,
            all_finished_tests
        )
        finished_tests.update(
            map(
                itemgetter("name"),
                new_finished_tests
            )
        )
        for test in new_finished_tests:
            print(
                u"[{0:2} of {1}] [{status}] '{name}' "
                u"({taken:.4} s) {message}".format(
                    test_counter,
                    total_tests_count,
                    **test
                )
            )
            test_counter += 1
        sleep(1)
