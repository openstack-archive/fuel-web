# -*- coding: utf-8 -*-

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

import six

from nailgun.api.v1.handlers import base
from nailgun.api.v1.handlers.base import handle_errors
from nailgun.api.v1.handlers.base import validate
from nailgun.api.v1.handlers.deployment_graph import \
    RelatedDeploymentGraphCollectionHandler
from nailgun.api.v1.handlers.deployment_graph import \
    RelatedDeploymentGraphHandler
from nailgun.api.v1.validators import plugin as validators
from nailgun import errors
from nailgun import objects
from nailgun.plugins.manager import PluginManager
from nailgun.plugins.package_manager import manager


class PluginHandler(base.SingleHandler):

    validator = validators.PluginValidator
    single = objects.Plugin

    @handle_errors
    @validate
    def DELETE(self, obj_id):
        """Remove plugin from API service and uninstall the plugin package.

        :return: Empty string

        :http: * 204 (object successfully deleted)
               * 400 (invalid object data specified)
               * 404 (object not found in db)
        """
        obj = self.get_object_or_404(self.single, obj_id)
        self.checked_data(self.validator.validate_delete, instance=obj)
        try:
            prm = manager.PackageRemoveManager(obj.name, obj.version)
        except errors.PackageVersionIsNotCompatible as exc:
            raise self.http(400, exc.message)

        self.single.delete(obj)
        prm.remove()

        raise self.http(204)


# Remains for compatibility.
# For manipulation with plugins is used the PluginUploadHandler.
class PluginCollectionHandler(base.CollectionHandler):

    collection = objects.PluginCollection
    validator = validators.PluginValidator

    @handle_errors
    @validate
    def POST(self):
        """:returns: JSONized REST object.

        :http: * 201 (object successfully created)
               * 400 (invalid object data specified)
               * 409 (object with such parameters already exists)
        """
        data = self.checked_data(self.validator.validate)
        obj = self.collection.single.get_by_name_version(
            data['name'], data['version'])
        if obj:
            raise self.http(409, self.collection.single.to_json(obj))
        return super(PluginCollectionHandler, self).POST()


class PluginSyncHandler(base.BaseHandler):

    validator = validators.PluginSyncValidator

    @handle_errors
    @validate
    def POST(self):
        """:returns: JSONized REST object.

        :http: * 200 (plugins successfully synced)
               * 404 (plugin not found in db)
               * 400 (problem with parsing metadata file)
        """
        data = self.checked_data()
        ids = data.get('ids', None)

        try:
            PluginManager.sync_plugins_metadata(plugin_ids=ids)
        except errors.ParseError as exc:
            raise self.http(400, msg=six.text_type(exc))

        raise self.http(200, {})


class PluginDeploymentGraphHandler(RelatedDeploymentGraphHandler):
    """Plugin Handler for deployment graph configuration."""

    related = objects.Plugin


class PluginDeploymentGraphCollectionHandler(
        RelatedDeploymentGraphCollectionHandler):
    """Plugin Handler for deployment graphs configuration."""

    related = objects.Plugin


class PluginUploadHandler(base.CollectionHandler):

    collection = objects.PluginCollection
    validator = validators.PluginValidator

    @handle_errors
    @validate
    def POST(self):
        """Processing of uploaded file of plugin package.

        :returns: JSONized REST object.

        :http: * 201 (object successfully created)
               * 400 (invalid object data specified)
               * 406 (action not acceptable)
               * 409 (conflict, object with such parameters already exists)
               * 500 (internal server error)
        """
        try:
            with manager.PackageInstallManager() as pim:
                last_action = pim.process_file()
                metadata = self.checked_data(data=pim.get_metadata())
                obj_id = pim.get_plugin_id()

            if obj_id:
                obj = self.get_object_or_404(self.collection.single, obj_id)
                new_obj = self.collection.single.update(obj, metadata)
            else:
                try:
                    new_obj = self.collection.create(metadata)
                except errors.CannotCreate as exc:
                    # rollback plugin installation
                    prm = manager.PackageRemoveManager(
                        metadata.name,
                        metadata.version,
                        metadata.package_version)
                    prm.remove()
                    raise self.http(400, exc.message)
        except (errors.InvalidData,
                errors.PackageFormatIsNotCompatible,
                errors.PackageVersionIsNotCompatible) as exc:
            raise self.http(400, exc.message)
        except (errors.UpgradeIsNotSupported,
                errors.DowngradeIsNotSupported) as exc:
            raise self.http(406, exc.message)
        except errors.AlreadyExists as exc:
            raise self.http(409, exc.message)
        except Exception as exc:
            raise self.http(500, exc.message or str(exc))

        raise self.http(201, {
            'action': last_action,
            'plugin': self.collection.single.to_json(new_obj)
        })
