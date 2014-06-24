import os

from fabric.api import env
from fabric.colors import green
from fabric.context_managers import hide
from fabric.context_managers import settings
from fabric.contrib.files import exists
from fabric.contrib.project import rsync_project
from fabric.operations import run

from common import backup_file
from common import escape_path
from common import install_package
from common import revert_file
from common import run_in_container


REMOTE_DEST_DIR = '/etc/fuel/development/'
NGINX_CONFIG_FILE = '/etc/nginx/conf.d/nailgun.conf'
NGINX_CONFIG_FILE_BACKUP = '{0}_backup'.format(NGINX_CONFIG_FILE)
NGINX_CONTAINER_NAME = 'nginx'

NAILGUN_CONTAINER_NAME = 'nailgun'
NAILGUN_APPS = ('assassind', 'nailgun', 'receiverd')

SUPERVISORD_CONFIG_FILE = '/etc/supervisord.conf'
SUPERVISORD_CONFIG_FILE_BACKUP = '{0}_backup'.format(
    SUPERVISORD_CONFIG_FILE
)


def install_required_packages():
    install_package('rsync')


def sync(nailgun_dir, remote_dir=REMOTE_DEST_DIR):
    print(green("Synchronizing Nailgun code"))
    if not exists(remote_dir):
        run('mkdir -p {0}'.format(remote_dir))
    rsync_project(remote_dir, local_dir=nailgun_dir, delete=True,
                  extra_opts='-a', exclude=('*pyc',))
    print(green("Nailgun code synchronized"))


def configure_nginx():
    print(green("Configuring nginx"))
    backup_file(
        NGINX_CONTAINER_NAME,
        NGINX_CONFIG_FILE,
        NGINX_CONFIG_FILE_BACKUP
    )

    replaces = (
        ('/usr/share/nailgun/static',
         os.path.join(REMOTE_DEST_DIR, 'nailgun', 'static')),
        ('access_nailgun.log', 'access_nailgun_dev.log'),
        ('error_nailgun.log', 'error_nailgun_dev.log'),
    )
    for f, t in replaces:
        command = 'sed -i.bak -r -e \'s/{0}/{1}/g\' $(echo "{2}")'.format(
            escape_path(f),
            escape_path(t),
            NGINX_CONFIG_FILE
        )
        run_in_container(NGINX_CONTAINER_NAME, command)
    print(green("Nginx configured"))


def reload_nginx():
    print(green("Reloading nginx configs"))
    run_in_container(
        NGINX_CONTAINER_NAME,
        'service nginx reload'
    )
    print(green("Nginx configs reloaded"))


def is_supervisord_configured(dev_env_string):
    # grep return code is not 0 in this case
    with settings(hide('warnings'), warn_only=True):
        result = run_in_container(
            NAILGUN_CONTAINER_NAME,
            'grep -Fxc "{0}" {1}'.format(
                dev_env_string,
                SUPERVISORD_CONFIG_FILE
            )
        )
    return bool(result and int(result))


def configure_supervisord():
    print(green("Configuring supervisord"))
    backup_file(
        NAILGUN_CONTAINER_NAME,
        SUPERVISORD_CONFIG_FILE,
        SUPERVISORD_CONFIG_FILE_BACKUP
    )

    dev_env_string = 'environment=PYTHONPATH=/etc/fuel/development/nailgun'

    if is_supervisord_configured(dev_env_string):
        print(green("Supervisord already configured"))
    else:
        for app in NAILGUN_APPS:
            header = '\[program:{0}\]'.format(app)
            header_dev = '{0}\\n{1}'.format(header, dev_env_string)
            command = 'sed -i.bak -r -e \'s/{0}/{1}/g\' $(echo "{2}")'.format(
                header,
                escape_path(header_dev),
                SUPERVISORD_CONFIG_FILE
            )
            run_in_container(NAILGUN_CONTAINER_NAME, command)
        print(green("Supervisor configured"))


def reload_supervisord():
    print(green("Reloading supervisord configs"))
    run_in_container(
        NAILGUN_CONTAINER_NAME,
        'service supervisord reload'
    )
    print(green("Supervisord configs reloaded"))


def restart_nailgun():
    print(green("Restarting nailgun applications"))
    for app in NAILGUN_APPS:
        print(green("Restarting application {0}".format(app)))
        command = 'supervisorctl restart {0}'.format(app)
        run_in_container(NAILGUN_CONTAINER_NAME, command)
        print(green("Application {0} restarted".format(app)))
    print(green("Nailgun applications restarted"))


def revert_nginx():
    print(green("Restoring origin nginx configuration"))
    with settings(warn_only=True):
        revert_file(
            NGINX_CONTAINER_NAME,
            NGINX_CONFIG_FILE_BACKUP,
            NGINX_CONFIG_FILE
        )
    reload_nginx()
    print(green("Origin nginx configuration restored"))


def revert_supervisord():
    print(green("Restoring origin supervisord configuration"))
    with settings(warn_only=True):
        revert_file(
            NAILGUN_CONTAINER_NAME,
            SUPERVISORD_CONFIG_FILE_BACKUP,
            SUPERVISORD_CONFIG_FILE
        )
    reload_supervisord()
    print(green("Origin supervisord configuration restored"))


def deploy(params):
    print(green("Deploying development environment to {0}".format(
        env.host_string
    )))
    nailgun_dir = params.nailgun_dir
    if params.synconly:
        sync(nailgun_dir)
        restart_nailgun()
    else:
        install_required_packages()
        sync(nailgun_dir)
        configure_supervisord()
        reload_supervisord()
        restart_nailgun()
        configure_nginx()
        reload_nginx()
    print(green("Development environment deployed to {0}".format(
        env.host_string
    )))


def revert():
    print(green("Restoring production environment on {0}".format(
        env.host_string
    )))
    revert_nginx()
    revert_supervisord()
    restart_nailgun()
    print(green("Production environment restored on {0}".format(
        env.host_string
    )))


def action(params):
    if params.command == 'deploy':
        deploy(params)
    elif params.command == 'revert':
        revert()
