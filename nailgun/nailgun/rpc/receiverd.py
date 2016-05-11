# -*- coding: utf-8 -*-

#    Copyright 2013-2014 Mirantis, Inc.
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

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import traceback

import amqp.exceptions as amqp_exceptions
from kombu import Connection
from kombu.mixins import ConsumerMixin
import six
from sqlalchemy.exc import OperationalError

from nailgun.db import db
from nailgun import errors
import nailgun.rpc as rpc
from nailgun.rpc.receiver import NailgunReceiver
from nailgun.rpc import utils
from nailgun.settings import settings
from nailgun.utils import logs


logger = logging.getLogger('receiverd')


class RPCConsumer(ConsumerMixin):

    def __init__(self, connection, receiver):
        self.connection = connection
        self.receiver = receiver

    def get_consumers(self, Consumer, channel):
        return [Consumer(queues=[rpc.nailgun_queue],
                         callbacks=[self.consume_msg])]

    def consume_msg(self, body, msg):
        callback = getattr(self.receiver, body["method"])
        try:
            callback(**body["args"])
        except errors.CannotFindTask as e:
            logger.warn(str(e))
            msg.ack()
        except OperationalError as e:
            if (
                'TransactionRollbackError' in e.message or
                'deadlock' in e.message
            ):
                logger.exception("Deadlock on message: %s", msg)
                msg.requeue()
            else:
                logger.exception("Operational error on message: %s", msg)
                msg.ack()
        except Exception:
            logger.exception("Message consume failed: %s", msg)
            msg.ack()
        except KeyboardInterrupt:
            logger.error("Receiverd interrupted.")
            msg.requeue()
            raise
        else:
            db.commit()
            msg.ack()
        finally:
            db.remove()

    def on_precondition_failed(self, error_msg):
        logger.warning(error_msg)
        utils.delete_entities(
            self.connection, rpc.nailgun_exchange, rpc.nailgun_queue)

    def run(self, *args, **kwargs):
        try:
            super(RPCConsumer, self).run(*args, **kwargs)
        except amqp_exceptions.PreconditionFailed as e:
            self.on_precondition_failed(six.text_type(e))
            self.run(*args, **kwargs)


def run():
    logger = logs.prepare_submodule_logger('receiverd',
                                           settings.RPC_CONSUMER_LOG_PATH)
    logger.info("Starting standalone RPC consumer...")
    with Connection(rpc.conn_str) as conn:
        try:
            RPCConsumer(conn, NailgunReceiver).run()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Stopping standalone RPC consumer...")
