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

import web

from nailgun.api.handlers import base
from nailgun.api.validators import verifications
from nailgun.db.sqlalchemy import models
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.task import manager


class VerificationHandler(base.DeferredTaskHandler):

    actions = {'l2': manager.VerifyNetworksTaskManager,
               'validate_networks': manager.CheckNetworksTaskManager}
    validator = verifications.VerificationsValidator

    @base.content_json
    def PUT(self, cluster_id):
        """:returns: JSONized Task object.
        :http: * 202 (task successfully executed)
               * 400 (invalid object data specified)
               * 404 (environment is not found)
               * 409 (task with such parameters already exists)
        """
        cluster = self.get_object_or_404(models.Cluster, cluster_id)
        logger.info(self.log_message.format(env_id=cluster_id))
        data = self.checked_data(actions=self.actions)
        task_manager = self.actions[data['task_name']]
        args = data.get('args', ())
        kwargs = data.get('kwargs', {})

        try:
            task_manager = task_manager(cluster_id=cluster.id)
            task = task_manager.execute(*args, **kwargs)
        except (
            errors.AlreadyExists,
            errors.StopAlreadyRunning
        ) as exc:
            err = web.conflict()
            err.message = exc.message
            raise err
        except (
            errors.DeploymentNotRunning
        ) as exc:
            raise web.badrequest(message=exc.message)
        except Exception as exc:
            logger.error(
                self.log_error.format(
                    env_id=cluster_id,
                    error=str(exc)
                )
            )
            # let it be 500
            raise

        raise web.webapi.HTTPError(
            status="202 Accepted",
            data=self.single.to_json(task)
        )
