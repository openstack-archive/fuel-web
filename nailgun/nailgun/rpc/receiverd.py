# -*- coding: utf-8 -*-

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

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import traceback

import six

from kombu import Connection
from kombu.mixins import ConsumerMixin

import amqp.exceptions as amqp_exceptions

from nailgun.db import db
from nailgun.errors import errors
from nailgun.logger import logger
import nailgun.rpc as rpc
from nailgun.rpc.receiver import NailgunReceiver
from nailgun.rpc import utils


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
            db().commit()
        except errors.CannotFindTask as e:
            logger.warn(str(e))
            db().rollback()
        except Exception:
            logger.error(traceback.format_exc())
            db().rollback()
        finally:
            msg.ack()
            db().expire_all()

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
    logger.info("Starting standalone RPC consumer...")
    with Connection(rpc.conn_str) as conn:
        try:
            RPCConsumer(conn, NailgunReceiver).run()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Stopping standalone RPC consumer...")
