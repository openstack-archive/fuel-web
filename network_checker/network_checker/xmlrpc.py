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

import httplib
import SimpleXMLRPCServer
import socket
import xmlrpclib


class UnixStreamHTTPConnection(httplib.HTTPConnection):

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.host)

    def getreply(self):
        response = self.getresponse()
        self.file = response.fp
        return response.status, response.reason, response.msg

    def getfile(self):
        return self.file


class UnixStreamTransport(xmlrpclib.Transport, object):

    def __init__(self, socket_path):
        self.socket_path = socket_path
        super(UnixStreamTransport, self).__init__()

    def make_connection(self, host):
        return UnixStreamHTTPConnection(self.socket_path)


class UnixStreamHandler(SimpleXMLRPCServer.SimpleXMLRPCRequestHandler):

    # if True leads to calling TCP_NODELAY on AF_UNIX socket
    # which results in Errno 95
    disable_nagle_algorithm = False


class UnixXMLRPCServer(SimpleXMLRPCServer.SimpleXMLRPCServer):

    address_family = socket.AF_UNIX


def get_client(config):
    return xmlrpclib.Server(
        'http://arg_unused',
        transport=UnixStreamTransport(config['unix']))


def get_server(config):
    return UnixXMLRPCServer(
        config['unix'],
        requestHandler=UnixStreamHandler,
        logRequests=False)
