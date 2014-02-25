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

"""
Handlers dealing with exclusive Red Hat tasks
"""

import traceback

import web

from nailgun.api.handlers.base import BaseHandler
from nailgun.api.handlers.base import content_json
from nailgun.api.validators.redhat import RedHatAccountValidator
from nailgun.db import db
from nailgun.db.sqlalchemy.models import RedHatAccount
from nailgun.db.sqlalchemy.models import Release
from nailgun.logger import logger
from nailgun.objects import Task
from nailgun.task.manager import RedHatSetupTaskManager


class RedHatAccountHandler(BaseHandler):
    """Red Hat account handler
    """

    fields = (
        'username',
        'password',
        'license_type',
        'satellite',
        'activation_key'
    )
    model = RedHatAccount

    @content_json
    def GET(self):
        """:returns: JSONized RedHatAccount object.
        :http: * 200 (OK)
               * 404 (account not found in db)
        """
        account = db().query(RedHatAccount).first()
        if not account:
            raise web.notfound()
        return self.render(account)

    @content_json
    def POST(self):
        """:returns: JSONized RedHatAccount object.
        :http: * 200 (OK)
               * 400 (invalid account data specified)
               * 404 (account not found in db)
        """
        data = self.checked_data()

        license_type = data.get("license_type")
        if license_type == 'rhsm':
            data["satellite"] = ""
            data["activation_key"] = ""

        release_id = data.pop('release_id')
        release_db = db().query(Release).get(release_id)
        if not release_db:
            raise web.notfound(
                "No release with ID={0} found".format(release_id)
            )
        account = db().query(RedHatAccount).first()
        if account:
            db().query(RedHatAccount).update(data)
        else:
            account = RedHatAccount(**data)
            db().add(account)
        db().commit()
        return self.render(account)


class RedHatSetupHandler(BaseHandler):
    """Red Hat setup handler
    """

    validator = RedHatAccountValidator

    @content_json
    def POST(self):
        """Starts Red Hat setup and download process

        :returns: JSONized Task object.
        :http: * 202 (setup task created and started)
               * 400 (invalid account data specified)
               * 404 (release not found in db)
        """
        data = self.checked_data()

        license_type = data.get("license_type")
        if license_type == 'rhsm':
            data["satellite"] = ""
            data["activation_key"] = ""

        release_data = {'release_id': data['release_id']}
        release_id = data.pop('release_id')
        release_db = db().query(Release).get(release_id)
        if not release_db:
            raise web.notfound(
                "No release with ID={0} found".format(release_id)
            )
        release_data['redhat'] = data
        release_data['release_name'] = release_db.name

        account = db().query(RedHatAccount).first()
        if account:
            db().query(RedHatAccount).update(data)
        else:
            account = RedHatAccount(**data)
            db().add(account)
        db().commit()

        task_manager = RedHatSetupTaskManager(release_data)
        try:
            task = task_manager.execute()
        except Exception as exc:
            logger.error(u'RedHatAccountHandler: error while execution'
                         ' Red Hat validation task: {0}'.format(str(exc)))
            logger.error(traceback.format_exc())
            raise web.badrequest(str(exc))

        raise web.accepted(data=Task.to_json(task))
