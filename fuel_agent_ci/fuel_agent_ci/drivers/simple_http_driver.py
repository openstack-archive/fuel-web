# Copyright 2014 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import atexit
import BaseHTTPServer
import logging
import multiprocessing
import os
import signal
import SimpleHTTPServer
import sys
import time

import requests

LOG = logging.getLogger(__name__)


class Cwd(object):
    def __init__(self, path):
        self.path = path
        self.orig_path = os.getcwd()

    def __enter__(self):
        os.chdir(self.path)

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.chdir(self.orig_path)


class CustomHTTPRequestHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == self.server.parent.shutdown_url:
            LOG.info('Shutdown request has been received: %s' % (self.path))
            self.send_response(200)
            self.end_headers()
            self.server.parent.stop_self()
        elif self.path == self.server.parent.status_url:
            LOG.info('Status request has been received: %s' % (self.path))
            self.send_response(200)
            self.end_headers()
        else:
            with Cwd(self.server.parent.rootpath):
                SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)

    def do_HEAD(self):
        with Cwd(self.server.parent.rootpath):
            SimpleHTTPServer.SimpleHTTPRequestHandler.do_HEAD(self)


class CustomHTTPServer(object):
    def __init__(self, host, port, rootpath,
                 shutdown_url='/shutdown',
                 status_url='/status',
                 piddir='/var/run',
                 pidfile='custom_httpd.pid',
                 stdin=None, stdout=None, stderr=None):

        self.host = str(host)
        self.port = int(port)

        self.rootpath = rootpath
        self.shutdown_url = shutdown_url
        self.status_url = status_url
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.pidfile = os.path.join(piddir, pidfile)

        # We cannot just inherit BaseHTTPServer.HTTPServer because
        # it tries to bind socket during initialization but we need it
        # to be done during actual launching.
        self.server = None

    def stop_self(self):
        if self.server:
            # We cannot use server.shutdown() here because
            # it sets _BaseServer__shutdown_request to True
            # end wait for _BaseServer__is_shut_down event to be set
            # that locks thread forever. We can use shutdown() method
            # from outside this thread.
            self.server._BaseServer__shutdown_request = True

    def daemonize(self):
        # in order to avoid http process
        # to become zombie we need to fork twice
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError as e:
            sys.stderr.write('Error while fork#1 HTTP server: '
                             '%d (%s)' % (e.errno, e.strerror))
            sys.exit(1)

        os.chdir('/')
        os.setsid()
        os.umask(0)

        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError as e:
            sys.stderr.write('Error while fork#2 HTTP server: '
                             '%d (%s)' % (e.errno, e.strerror))
            sys.exit(1)

        if self.stdin:
            si = file(self.stdin, 'r')
            os.dup2(si.fileno(), sys.stdin.fileno())
        if self.stdout:
            sys.stdout.flush()
            so = file(self.stdout, 'a+')
            os.dup2(so.fileno(), sys.stdout.fileno())
        if self.stderr:
            sys.stderr.flush()
            se = file(self.stderr, 'a+', 0)
            os.dup2(se.fileno(), sys.stderr.fileno())

        atexit.register(self.delpid)
        pid = str(os.getpid())
        with open(self.pidfile, 'w+') as f:
            f.write('%s\n' % pid)
            f.flush()

    def delpid(self):
        os.remove(self.pidfile)

    def run(self):
        self.server = BaseHTTPServer.HTTPServer(
            (self.host, self.port), CustomHTTPRequestHandler)
        self.server.parent = self
        self.server.serve_forever()

    def start(self):
        try:
            with open(self.pidfile) as f:
                pid = int(f.read().strip())
        except (IOError, ValueError):
            pid = None
        if pid:
            message = 'pidfile %s already exists. Daemon already running?\n'
            sys.stderr.write(message % self.pidfile)
            sys.exit(1)
        self.daemonize()
        self.run()

    def stop(self):
        try:
            with open(self.pidfile) as f:
                pid = int(f.read().strip())
        except (IOError, ValueError):
            pid = None
        if not pid:
            message = 'pidfile %s does not exist. Daemon not running?\n'
            sys.stderr.write(message % self.pidfile)
            return
        try:
            while True:
                os.kill(pid, signal.SIGTERM)
                time.sleep(1)
        except OSError as err:
            err = str(err)
            if err.find('No such process') > 0:
                if os.path.exists(self.pidfile):
                    os.remove(self.pidfile)
            else:
                sys.stdout.write(str(err))
                sys.exit(1)


def http_start(http):
    def start():
        server = CustomHTTPServer(
            http.env.net_by_name(http.network).ip, http.port,
            os.path.join(http.env.envdir, http.http_root),
            status_url=http.status_url, shutdown_url=http.shutdown_url,
            pidfile=os.path.join(http.env.envdir,
                                 http.env.name + '_custom_httpd.pid'))
        server.start()
    multiprocessing.Process(target=start).start()


def http_stop(http):
    if http_status(http):
        requests.get(
            'http://%s:%s%s' % (http.env.net_by_name(http.network).ip,
                                http.port, http.shutdown_url))


def http_status(http):
    try:
        status = requests.get(
            'http://%s:%s%s' % (http.env.net_by_name(http.network).ip,
                                http.port, http.status_url),
            timeout=1
        )
        if status.status_code == 200:
            return True
    except Exception:
        pass
    return False
