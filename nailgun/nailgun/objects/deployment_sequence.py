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

from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun import errors
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects.serializers import deployment_sequence as serializer


class DeploymentSequence(NailgunObject):

    model = models.DeploymentSequence
    serializer = serializer.DeploymentSequenceSerializer

    @classmethod
    def get_by_name_for_release(cls, release, name,
                                fail_if_not_found=False,
                                lock_for_update=False):
        """Get sequence by name.

        :param release: the release object
        :param name: the name of sequence
        :param fail_if_not_found: True means raising of exception
                   in case if object is not found
        :param lock_for_update: True means acquiring exclusive access
                                for object
        :return: deployment sequence object
        """

        q = db().query(cls.model).filter_by(release_id=release.id, name=name)
        if lock_for_update:
            q = q.order_by('id')
            q = q.with_lockmode('update')
        res = q.first()

        if not res and fail_if_not_found:
            raise errors.ObjectNotFound(
                "Sequence with name='{0}' is not found for release {1}"
                .format(name, release.id)
            )
        return res


class DeploymentSequenceCollection(NailgunCollection):

    single = DeploymentSequence

    @classmethod
    def get_for_release(cls, release):
        """Get all sequences are associated with release."""
        return cls.filter_by(None, release_id=release.id)
