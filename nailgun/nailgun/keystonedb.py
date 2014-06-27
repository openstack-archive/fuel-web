# -*- coding: UTF-8 -*-
import os
import re
import sys

from nailgun.settings import settings
from nailgun.urls import public_urls

from keystoneclient.middleware import auth_token


class NailgunAuthProtocol(auth_token.AuthProtocol):
    """A wrapper on Keystone auth_token middleware.

    Does not perform verification of authentication tokens
    for public routes in the API.

    """
    def __init__(self, app):
        self.public_api_routes = {}
        conf = {'auth_protocol': 'http',
                'admin_token': settings.KEYSTONE_ADMIN_TOKEN,
                'admin_user': 'admin',
                'admin_password': 'admin',
                'admin_tenant': 'admin'
                }
        try:
            for route_tpl, methods in public_urls().iteritems():
                self.public_api_routes[re.compile(route_tpl)] = methods
        except re.error as e:
            msg = 'Cannot compile public API routes: %s' % e

            auth_token.LOG.error(msg)
            raise Exception(error_msg=msg)

        super(NailgunAuthProtocol, self).__init__(app, conf)

    def __call__(self, env, start_response):
        path = env.get('PATH_INFO')
        method = env.get('REQUEST_METHOD')

        # The information whether the API call is being performed against the
        # public API may be useful. Saving it to the
        # WSGI environment is reasonable thereby.
        env['is_public_api'] = False
        for pattern, methods in self.public_api_routes.iteritems():
            if re.match(pattern, path):
                if method in methods:
                    env['is_public_api'] = True
                    break

        if env['is_public_api']:
            return self.app(env, start_response)
        return super(NailgunAuthProtocol, self).__call__(env, start_response)


def sync_keystone_db():
    from oslo.config import cfg
    orig_sys = sys.path[:]
    orig_conf = cfg.CONF
    cfg.CONF = cfg.ConfigOpts()

    #for development enviorment when running in virtualenv
    sys.path.append('/usr/lib/python2.7/dist-packages')
    from keystone.cli import DbSync

    #make sure that keystone conf file is available
    keystone_conf_file = '/etc/keystone/keystone.conf'
    if not os.path.exists(keystone_conf_file):
        raise Exception('No {0} file'.format(keystone_conf_file))
    cfg.CONF(default_config_files=[keystone_conf_file])

    #create tables
    DbSync.main()

    #revert all
    sys.path = orig_sys
    cfg.CONF = orig_conf


def drop_keystone_db():
    from oslo.config import cfg
    orig_sys = sys.path[:]
    orig_conf = cfg.CONF
    cfg.CONF = cfg.ConfigOpts()

    #for development enviorment when running in virtualenv
    sys.path.append('/usr/lib/python2.7/dist-packages')
    from keystone.common.sql import core

    #make sure that keystone conf file is available
    keystone_conf_file = '/etc/keystone/keystone.conf'
    if not os.path.exists(keystone_conf_file):
        raise Exception('No {0} file'.format(keystone_conf_file))
    cfg.CONF(default_config_files=[keystone_conf_file])

    #init connection
    base = core.Base()
    conn = base.get_engine().connect()

    #get all tables and delete them
    query = "select * from pg_tables where schemaname='public';"
    all_tables = conn.execute(query)
    for table in all_tables.fetchall():
        table_name = table[1]
        conn.execute('drop table "{0}" cascade'.format(table_name))

    #revert all
    sys.path = orig_sys
    cfg.CONF = orig_conf
