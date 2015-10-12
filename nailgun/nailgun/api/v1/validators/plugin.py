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


from nailgun.api.v1.validators.base import BasicValidator
from nailgun.api.v1.validators.json_schema import plugin
from nailgun.errors import errors
from nailgun.objects import ComponentCollection
from nailgun.objects import Plugin


class PluginValidator(BasicValidator):

    @classmethod
    def validate_delete(cls, data, instance):
        if instance.clusters:
            raise errors.CannotDelete(
                "Can't delete plugin which is enabled "
                "for some environment."
            )

    @classmethod
    def validate(cls, data):
        parsed = super(PluginValidator, cls).validate(data)
        cls.validate_schema(parsed, plugin.PLUGIN_SCHEMA)
        return parsed

    @classmethod
    def validate_update(cls, data, instance):
        data = cls.validate(data)
        return cls.validate_provided_components(data, instance.id)

    @classmethod
    def validate_create(cls, data):
        data = cls.validate(data)
        return cls.validate_provided_components(data)

    @classmethod
    def validate_provided_components(cls, data, plugin_id=None):
        for provided_component in data.get('provides', []):
            installed_components = list(ComponentCollection.filter_by(
                None, name=provided_component['name']))
            if plugin_id:
                installed_components = [comp for comp in installed_components
                                        if comp.plugin_id != plugin_id]
            if len(installed_components):
                raise errors.AlreadyExists(
                    "One or more plugin components has been installed "
                    "in system already"
                )
        return data


class PluginSyncValidator(BasicValidator):

    @classmethod
    def validate(cls, data):
        if data:
            parsed = super(PluginSyncValidator, cls).validate(data)
            cls.validate_schema(parsed, plugin.SYNC_SCHEMA)
            # Check plugin with given id exists in DB
            # otherwise raise ObjectNotFound exception
            for plugin_id in parsed.get('ids'):
                Plugin.get_by_uid(plugin_id, fail_if_not_found=True)

            return parsed
        else:
            return {}
