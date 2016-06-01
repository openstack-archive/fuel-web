# -*- coding: utf-8 -*-
#
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

import os

from fuelclient.cli import error
from fuelclient.cli.serializers import Serializer
from fuelclient.commands import base
from fuelclient.common import data_utils


class FileMethodsMixin(object):
    @classmethod
    def check_file_path(cls, file_path):
        if not os.path.exists(file_path):
            raise error.InvalidFileException(
                "File '{0}' doesn't exist.".format(file_path))

    @classmethod
    def check_dir(cls, directory):
        if not os.path.exists(directory):
            raise error.InvalidDirectoryException(
                "Directory '{0}' doesn't exist.".format(directory))
        if not os.path.isdir(directory):
            raise error.InvalidDirectoryException(
                "Error: '{0}' is not a directory.".format(directory))


class GraphUpload(base.BaseCommand, FileMethodsMixin):
    """Upload deployment graph configuration."""
    entity_name = 'graph'

    @classmethod
    def read_tasks_data_from_file(cls, file_path=None, serializer=None):
        """Read Tasks data from given path.

        :param file_path: path
        :type file_path: str
        :param serializer: serializer object
        :type serializer: object
        :return: data
        :rtype: list|object
        """
        cls.check_file_path(file_path)
        return (serializer or Serializer()).read_from_full_path(file_path)

    def get_parser(self, prog_name):
        parser = super(GraphUpload, self).get_parser(prog_name)
        graph_class = parser.add_mutually_exclusive_group()

        graph_class.add_argument('-e',
                                 '--env',
                                 type=int,
                                 required=False,
                                 help='Id of the environment')
        graph_class.add_argument('-r',
                                 '--release',
                                 type=int,
                                 required=False,
                                 help='Id of the release')
        graph_class.add_argument('-p',
                                 '--plugin',
                                 type=int,
                                 required=False,
                                 help='Id of the plugin')

        parser.add_argument('-t',
                            '--type',
                            type=str,
                            default=None,
                            required=False,
                            help='Type of the deployment graph')
        parser.add_argument('-f',
                            '--file',
                            type=str,
                            required=True,
                            default=None,
                            help='YAML file that contains '
                                 'deployment graph data.')
        return parser

    def take_action(self, args):
        parameters_to_graph_class = (
            ('env', 'clusters'),
            ('release', 'releases'),
            ('plugin', 'plugins'),
        )

        for parameter, graph_class in parameters_to_graph_class:
            model_id = getattr(args, parameter)
            if model_id:
                self.client.upload(
                    data=self.read_tasks_data_from_file(args.file),
                    related_model=graph_class,
                    related_id=model_id,
                    graph_type=args.type
                )
                break

        self.app.stdout.write(
            "Deployment graph was uploaded from {0}\n".format(args.file)
        )


class GraphExecute(base.BaseCommand):
    """Start deployment with given graph type."""
    entity_name = 'graph'

    def get_parser(self, prog_name):
        parser = super(GraphExecute, self).get_parser(prog_name)
        parser.add_argument('-e',
                            '--env',
                            type=int,
                            required=True,
                            help='Id of the environment')
        parser.add_argument('-t',
                            '--type',
                            type=str,
                            default=None,
                            required=False,
                            help='Type of the deployment graph')
        parser.add_argument('-n',
                            '--nodes',
                            type=int,
                            nargs='+',
                            required=False,
                            help='Ids of the nodes to use for deployment.')
        parser.add_argument('-d',
                            '--dry-run',
                            action="store_true",
                            required=False,
                            default=False,
                            help='Specifies to dry-run a deployment by '
                                 'configuring task executor to dump the '
                                 'deployment graph to a dot file.')
        return parser

    def take_action(self, args):
        self.client.execute(
            env_id=args.env,
            graph_type=args.type,
            nodes=args.nodes,
            dry_run=args.dry_run
        )
        self.app.stdout.write(
            "Deployment was executed\n"
        )


class GraphDownload(base.BaseCommand):
    """Download deployment graph configuration."""
    entity_name = 'graph'

    def get_parser(self, prog_name):
        parser = super(GraphDownload, self).get_parser(prog_name)
        tasks_level = parser.add_mutually_exclusive_group()
        parser.add_argument('-e',
                            '--env',
                            type=int,
                            required=True,
                            help='Id of the environment')

        tasks_level.add_argument('-a',
                                 '--all',
                                 action="store_true",
                                 required=False,
                                 default=False,
                                 help='Download merged graph for the '
                                      'environment')
        tasks_level.add_argument('-c',
                                 '--cluster',
                                 action="store_true",
                                 required=False,
                                 default=False,
                                 help='Download cluster-specific tasks')
        tasks_level.add_argument('-p',
                                 '--plugins',
                                 action="store_true",
                                 required=False,
                                 default=False,
                                 help='Download plugins-specific tasks')
        tasks_level.add_argument('-r',
                                 '--release',
                                 action="store_true",
                                 required=False,
                                 default=False,
                                 help='Download release-specific tasks')

        parser.add_argument('-t',
                            '--type',
                            type=str,
                            default=None,
                            required=False,
                            help='Graph type string')
        parser.add_argument('-f',
                            '--file',
                            type=str,
                            required=False,
                            default=None,
                            help='YAML file that contains tasks data.')
        return parser

    @classmethod
    def get_default_tasks_data_path(cls):
        return os.path.join(
            os.path.abspath(os.curdir),
            "cluster_graph"
        )

    @classmethod
    def write_tasks_to_file(cls, tasks_data, serializer=None, file_path=None):
        serializer = serializer or Serializer()
        if file_path:
            return serializer.write_to_full_path(
                file_path,
                tasks_data
            )
        else:
            return serializer.write_to_path(
                cls.get_default_tasks_data_path(),
                tasks_data
            )

    def take_action(self, args):
        tasks_data = []
        for tasks_level_name in ('all', 'cluster', 'release', 'plugins'):
            if getattr(args, tasks_level_name):
                tasks_data = self.client.download(
                    env_id=args.env,
                    level=tasks_level_name,
                    graph_type=args.type
                )
                break

        # write to file
        graph_data_file_path = self.write_tasks_to_file(
            tasks_data=tasks_data,
            serializer=Serializer(),
            file_path=args.file)

        self.app.stdout.write(
            "Tasks were downloaded to {0}\n".format(graph_data_file_path)
        )


class GraphList(base.BaseListCommand):
    """Upload deployment graph configuration."""
    entity_name = 'graph'
    columns = ("id",
               "name",
               "tasks",
               "relations")

    def get_parser(self, prog_name):
        parser = super(GraphList, self).get_parser(prog_name)
        parser.add_argument('-e',
                            '--env',
                            type=int,
                            required=True,
                            help='Id of the environment')
        return parser

    def take_action(self, parsed_args):
        data = self.client.list(
            env_id=parsed_args.env
        )
        # format fields
        for d in data:
            d['relations'] = "\n".join(
                'as "{type}" to {model}(ID={model_id})'
                .format(**r) for r in d['relations']
            )
            d['tasks'] = ', '.join(sorted(t['id'] for t in d['tasks']))
        data = data_utils.get_display_data_multi(self.columns, data)
        scolumn_ids = [self.columns.index(col)
                       for col in parsed_args.sort_columns]
        data.sort(key=lambda x: [x[scolumn_id] for scolumn_id in scolumn_ids])
        return self.columns, data
