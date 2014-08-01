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

import argparse
from itertools import chain
import os

from fuelclient import __version__
from fuelclient.cli.error import ArgumentException
from fuelclient.client import APIClient

substitutions = {
    #replace from: to
    "env": "environment",
    "nodes": "node",
    "net": "network",
    "rel": "release",
    "list": "--list",
    "set": "--set",
    "delete": "--delete",
    "download": "--download",
    "upload": "--upload",
    "default": "--default",
    "create": "--create",
    "remove": "--delete",
    "config": "--config",
    "--roles": "--role",
    "help": "--help",
}


def group(*args, **kwargs):
    required = kwargs.get("required", False)
    return (required, ) + args


class TaskAction(argparse.Action):
    """Custom argparse.Action subclass to store task ids

    :returns: list of ids
    """
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, map(int, chain(*values)))


class NodeAction(argparse.Action):
    """Custom argparse.Action subclass to store node identity

    :returns: list of ids
    """
    def __call__(self, parser, namespace, values, option_string=None):
        if values:
            node_identities = set(chain(*values))
            input_macs = set(n for n in node_identities if ":" in n)
            only_ids = set()
            for _id in (node_identities - input_macs):
                try:
                    only_ids.add(int(_id))
                except ValueError:
                    raise ArgumentException(
                        "'{0}' is not valid node id.".format(_id))
            if input_macs:
                nodes_mac_to_id_map = dict(
                    (n["mac"], n["id"])
                    for n in APIClient.get_request("nodes/")
                )
                for short_mac in input_macs:
                    target_node = None
                    for mac in nodes_mac_to_id_map:
                        if mac.endswith(short_mac):
                            target_node = mac
                            break
                    if target_node:
                        only_ids.add(nodes_mac_to_id_map[target_node])
                    else:
                        raise ArgumentException(
                            'Node with mac endfix "{0}" was not found.'
                            .format(short_mac)
                        )
            setattr(namespace, self.dest, map(int, only_ids))


class FuelVersionAction(argparse._VersionAction):
    """Custom argparse._VersionAction subclass to compute fuel server version

    :returns: prints fuel server version
    """
    def __call__(self, parser, namespace, values, option_string=None):
        parser.exit(message=APIClient.get_fuel_version())


class SetAction(argparse.Action):
    """Custom argparse.Action subclass to store distinct values

    :returns: Set of arguments
    """
    def __call__(self, _parser, namespace, values, option_string=None):
        try:
            getattr(namespace, self.dest).update(values)
        except AttributeError:
            setattr(namespace, self.dest, set(values))


def get_debug_arg():
    return {
        "args": ["--debug"],
        "params": {
            "dest": "debug",
            "action": "store_true",
            "help": "prints details of all HTTP request",
            "default": False
        }
    }


def get_version_arg():
    return {
        "args": ["-v", "--version"],
        "params": {
            "action": "version",
            "version": __version__
        }
    }


def get_fuel_version_arg():
    return {
        "args": ["--fuel-version"],
        "params": {
            "action": FuelVersionAction,
            "help": "show Fuel server's version number and exit"
        }
    }


def get_arg(name, flags=None, aliases=None, help_=None, **kwargs):
    if "_" in name:
        name = name.replace("_", "-")
    args = ["--" + name, ]
    if flags is not None:
        args.extend(flags)
    if aliases is not None:
        substitutions.update(
            dict((alias, args[0]) for alias in aliases)
        )
    all_args = {
        "args": args,
        "params": {
            "dest": name,
            "help": help_ or name
        }
    }
    all_args["params"].update(kwargs)
    return all_args


def get_boolean_arg(name, **kwargs):
    kwargs.update({
        "action": "store_true",
        "default": False
    })
    return get_arg(name, **kwargs)


def get_env_arg(required=False):
    return get_int_arg(
        "env",
        flags=("--env-id",),
        help="environment id",
        required=required
    )


def get_new_password_arg():
    return get_str_arg(
        "newpass",
        flags=("--new-pass",),
        help="new_password",
        required=False
    )


def get_str_arg(name, **kwargs):
    default_kwargs = {
        "action": "store",
        "type": str,
        "default": None
    }
    default_kwargs.update(kwargs)
    return get_arg(name, **default_kwargs)


def get_int_arg(name, **kwargs):
    default_kwargs = {
        "action": "store",
        "type": int,
        "default": None
    }
    default_kwargs.update(kwargs)
    return get_arg(name, **default_kwargs)


def get_set_type_arg(name, **kwargs):
    default_kwargs = {
        "type": lambda v: v.split(','),
        "action": SetAction,
        "default": None
    }
    default_kwargs.update(kwargs)
    return get_arg(name, **default_kwargs)


def get_delete_from_db_arg(help_msg):
    return get_boolean_arg("delete-from-db", help=help_msg)


def get_network_arg(help_msg):
    return get_boolean_arg("network", flags=("--net",), help=help_msg)


def get_force_arg(help_msg):
    return get_boolean_arg("force", flags=("-f",), help=help_msg)


def get_disk_arg(help_msg):
    return get_boolean_arg("disk", help=help_msg)


def get_deploy_arg(help_msg):
    return get_boolean_arg("deploy", help=help_msg)


def get_provision_arg(help_msg):
    return get_boolean_arg("provision", help=help_msg)


def get_role_arg(help_msg):
    return get_set_type_arg("role", flags=("-r",), help=help_msg)


def get_check_arg(help_msg):
    return get_set_type_arg("check", help=help_msg)


def get_change_password_arg(help_msg):
    return get_boolean_arg("change-password", help=help_msg)


def get_name_arg(help_msg):
    return get_str_arg("name", flags=("--env-name",), help=help_msg)


def get_mode_arg(help_msg):
    return get_arg("mode",
                   action="store",
                   choices=("multinode", "ha"),
                   default=False,
                   flags=("-m", "--deployment-mode"),
                   help_=help_msg)


def get_net_arg(help_msg):
    return get_arg("net",
                   flags=("-n", "--network-mode"),
                   action="store",
                   choices=("nova", "neutron"),
                   help_=help_msg,
                   default="nova")


def get_nst_arg(help_msg):
    return get_arg("nst",
                   flags=("--net-segment-type",),
                   action="store",
                   choices=("gre", "vlan"),
                   help_=help_msg,
                   default=None)


def get_all_arg(help_msg):
    return get_boolean_arg("all", help=help_msg)


def get_create_arg(help_msg):
    return get_boolean_arg(
        "create",
        flags=("-c", "--env-create"),
        help=help_msg)


def get_download_arg(help_msg):
    return get_boolean_arg("download", flags=("-d",), help=help_msg)


def get_list_arg(help_msg):
    return get_boolean_arg("list", flags=("-l",), help=help_msg)


def get_update_arg(help_msg):
    return get_boolean_arg("update",
                           flags=("--env-update",), help=help_msg)


def get_dir_arg(help_msg):
    return get_str_arg("dir", default=os.curdir, help=help_msg)


def get_verify_arg(help_msg):
    return get_boolean_arg("verify", flags=("-v",), help=help_msg)


def get_upload_arg(help_msg):
    return get_boolean_arg("upload", flags=("-u",), help=help_msg)


def get_default_arg(help_msg):
    return get_boolean_arg("default", help=help_msg)


def get_set_arg(help_msg):
    return get_boolean_arg("set", flags=("-s",), help=help_msg)


def get_delete_arg(help_msg):
    return get_boolean_arg("delete", help=help_msg)


def get_release_arg(help_msg, required=False):
    return get_int_arg(
        "release",
        flags=("--rel",),
        required=required,
        help=help_msg)


def get_node_arg(help_msg):
    default_kwargs = {
        "action": NodeAction,
        "flags": ("--node-id",),
        "nargs": '+',
        "type": lambda v: v.split(","),
        "default": None,
        "help": help_msg
    }
    return get_arg("node", **default_kwargs)


def get_task_arg(help_msg):
    default_kwargs = {
        "action": TaskAction,
        "flags": ("--tid", "--task-id"),
        "nargs": '+',
        "type": lambda v: v.split(","),
        "default": None,
        "help": help_msg
    }
    return get_arg("task", **default_kwargs)


def get_config_arg(help_msg):
    return get_boolean_arg("config", flags=("-c",), help=help_msg)


def get_username_arg(help_msg):
    return get_str_arg("username", flags=("-U", "--user"), help=help_msg)


def get_password_arg(help_msg):
    return get_str_arg("password", flags=("-P", "--pass"), help=help_msg)


def get_satellite_arg(help_msg):
    return get_str_arg("satellite_server_hostname", help=help_msg)


def get_activation_key_arg(help_msg):
    return get_str_arg("activation_key", help=help_msg)
