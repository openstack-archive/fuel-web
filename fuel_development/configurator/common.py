from fabric.api import run
from fabric.colors import green
from fabric.colors import yellow
from fabric.context_managers import hide
from fabric.context_managers import settings


def is_package_installed(package):
    print(green("Checking package {0} is installed".format(package)))
    with settings(hide('warnings'), warn_only=True):
        result = run('rpm -qa | grep {0}'.format(package))
        if result.succeeded:
            print(green("Package {0} is installed".format(package)))
        else:
            print(yellow("Package {0} is not installed".format(package)))
        return result.succeeded


def install_package(package):
    if not is_package_installed(package):
        print(green("Installing package {0}".format(package)))
        run('sudo yum -y install {0}'.format(package))
        print(green("Package {0} installed".format(package)))


def run_in_container(container_name, command):
    return run('dockerctl shell {0} {1}'.format(container_name, command))


def backup_file(container_name, origin, backup):
    command = 'cp --no-clobber {0} {1}'.format(origin, backup)
    run_in_container(container_name, command)


def revert_file(container_name, backup, origin):
    command = 'cp {0} {1}'.format(backup, origin)
    run_in_container(container_name, command)


def escape_path(s):
    return s.replace('/', '\/')
