#!/usr/bin/python
import errno
import itertools
import json
import logging
import os
import re
import subprocess
import sys
import time
import urllib
import xmlrpclib
import yaml

import errors
from fuel_upgrade.clients import NailgunClient

logger = logging.getLogger(__name__)


def make_sure_path_exists(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise

def read_yaml_config(path):                                                     
    """Reads yaml config                                                        
                                                                                
    :param str path: path to config                                             
    :returns: deserialized object                                               
    """                                                                         
    return yaml.load(open(path, 'r'))                                           
                                                                                
def get_fuel_uuid(uuid_file='/etc/fuel/fuel-uuid'):
    with open(uuid_file, 'r') as u:
        uuid = u.readlines()[0].strip().replace('-','')
    return uuid

def get_version_from_api(path):                                              
    """Retrieves version from config file                                       
                                                                                
    :param str path: path to config                                             
    """
    master_ip = '10.20.0.2'
    keystone_credentials = {                                                    
        'username': 'admin',                                        
        'password': 'admin',                                             
        'auth_url': 'http://{0}:5000/v2.0/tokens'.format(master_ip),            
        'tenant_name': 'admin'} 

    nailgun_endpoint = {                               
    'port': 8000,                                
    'host': '0.0.0.0',                           
    'keystone_credentials': keystone_credentials}

    nailgun = NailgunClient(**nailgun_endpoint)  
    full_releases = nailgun.get_releases()
    releases = []
    for rel in full_releases:
        releases.append({'os': rel['operating_system'], 'version': rel['version']})
    #TODO(mattymo): return all with OSes instead of just latest Ubuntu
    maxver = ""
    for rel in releases:
        if rel['version'] > maxver:
            maxver = rel['version']
    return maxver

def get_version_from_config(path):  
    """Retrieves version from config file

    :param str path: path to config
    """
    return read_yaml_config(path)['VERSION']['release']

def exec_cmd_iterator(cmd):
    """Execute command with logging.

    :param cmd: shell command
    :returns: generator where yeach item
              is line from stdout
    """
    logger.debug(u'Execute command "%s"', cmd)
    child = subprocess.Popen(
        cmd, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True)

    logger.debug(u'Stdout and stderr of command "%s":', cmd)
    for line in child.stdout:
        logger.debug(line.rstrip())
        yield line

    _wait_and_check_exit_code(cmd, child)

def _wait_and_check_exit_code(cmd, child):
    """Wait for child and check it's exit code

    :param cmd: command
    :param child: object which returned by subprocess.Popen
    :raises: ExecutedErrorNonZeroExitCode
    """
    child.wait()
    exit_code = child.returncode

    if exit_code != 0:
        raise errors.ExecutedErrorNonZeroExitCode(
            u'Shell command executed with "{0}" '
            'exit code: {1} '.format(exit_code, cmd))

    logger.debug(u'Command "%s" successfully executed', cmd)

def spacewalk_login(url, login, password):
    client = xmlrpclib.Server(url, verbose=0)
    key = client.auth.login(login, password)
    return client, key

def local_centos_packages(centos_path):
    nvrs = []
    command = "rpm -qp --queryformat '%%{name}-%%{version}-%%{release}\n' " \
              "%s/*.rpm" \
        % centos_path
    for nvr in exec_cmd_iterator(command):
        nvrs.append(nvr.rstrip())
    return nvrs

def local_ubuntu_packages(ubuntu_path):
    nvs = []
    command = "bash -c 'for p in %s/*.deb; do\
                 echo \"$(dpkg-deb -f $p package)-$(dpkg-deb -f $p version)\";\
               done'" % ubuntu_path
    for nv in exec_cmd_iterator(command):
        nvs.append(nv.rstrip())
    return nvs

def missing_packages(old, new):
    missing = []
    for newpkg in new:
        if newpkg not in old:
            print "Package to add: %s" % newpkg
            missing.append(newpkg)
    return missing

def gen_ubuntu_repo(repodir):
    command = "regenerate_ubuntu_repo.sh %s precise" % repodir
    lines = []
    for line in exec_cmd_iterator(command):
        lines.append(line)
    
def gen_centos_repo(repodir):
    command = "bash -c 'cd %s && createrepo -q .'" % repodir
    lines = []
    for line in exec_cmd_iterator(command):
        lines.append(line)

def report_packages(distro, channel, pkglist):
    total_download = 0
    for pkg in pkglist:
        print pkg['name']
        total_download += int(pkg['size'])
    report_message("Operating System: %s\nChannel: %s\nNew packages: %s\n\
Download size: %sM" % (distro, channel, len(pkglist), total_download / 1024 / 1024))

def report_message(message):
    print "Cast message to nailgun: %s" % message

#Spacewalk config
SATELLITE_URL = "https://spacewalktest/rpc/api"
login = get_fuel_uuid()
SATELLITE_LOGIN = login
SATELLITE_PASSWORD = login
#SATELLITE_LOGIN = "admin"
#SATELLITE_PASSWORD = "admin"
#CHANNEL="fuel60"

#Paths
version_path = '/etc/fuel/version.yaml'
repo_root = '/var/www/nailgun'
release = get_version_from_api(version_path)
ubuntu_path = os.path.join(repo_root, release, "ubuntu/x86_64/pool/main")
centos_path = os.path.join(repo_root, release, "centos/x86_64/Packages/")



def main():
    client, key = spacewalk_login(SATELLITE_URL, SATELLITE_LOGIN, 
                                  SATELLITE_PASSWORD)
    my_channels = client.channel.listAllChannels(key)
    print "My channels: %s" % my_channels
    package_list = dict()
    nvrs = dict()
    #Evaluate what is upstream
    for channel in my_channels:
        package_list[channel['label']] = \
            client.channel.software.listLatestPackages(key, channel['label'])
        packages = []
        for package in package_list[channel['label']]:
            nvr = "%s-%s-%s" % (package['name'], package['version'], package['release'])
            #strip trailing -X from ubuntu packages
            nvr = re.sub(r'-X$', '', nvr)

            packages.append(nvr)
        nvrs[channel['label']] = sorted(packages)
    #Evaluate local
    #TODO(mattymo): dirwalk to name directories and repos when repos are split
    local_packages = dict()
    local_packages['centos'] = local_centos_packages(centos_path)
    local_packages['ubuntu'] = local_ubuntu_packages(ubuntu_path)

    #Compare
    new_packages = dict()
    new_centos = [v for k, v in nvrs.iteritems() if 'centos' in k]
    new_ubuntu = [v for k, v in nvrs.iteritems() if 'ubuntu' in k]
    new_centos2 = list(itertools.chain.from_iterable(new_centos))
    new_ubuntu2 = list(itertools.chain.from_iterable(new_ubuntu))
    print "Processing centos"
    new_packages['centos'] = missing_packages(old=local_packages['centos'],
                                              new=new_centos2)
    print "Processing ubuntu"
    new_packages['ubuntu'] = missing_packages(old=local_packages['ubuntu'],
                                              new=new_ubuntu2)
    #Download new packages
    for distro in ['ubuntu','centos']:
        repodir = os.path.join(repo_root, release, distro, "updates")
        make_sure_path_exists(repodir)
        for channel in my_channels:
            if distro not in channel['label']:
                continue
            pkgs_to_download = []
            for package in package_list[channel['label']]:
                #print package['name']
                if any (package['name'] in p for p in new_packages[distro]):
                    pkgDetails = client.packages.getDetails(key, package['id'])
                    pkgs_to_download.append(pkgDetails)
        report_packages(distro, channel['label'], pkgs_to_download)
        for pkg in pkgs_to_download:
            pkgUrl = client.packages.getPackageUrl(key, pkg['id'])
            urllib.urlretrieve(pkgUrl,"%s/%s" % 
                               (repodir, pkgUrl.split('/')[-1]))
        report_message("Downloaded %s packages for distro %s" % (len(pkgs_to_download), distro))
        #Build new repo
        print "Generating repository in %s..." % repodir
        if distro == 'ubuntu':
           gen_ubuntu_repo(repodir)
        elif distro == 'centos':
           gen_centos_repo(repodir)
        else:
           raise

    client.auth.logout(key)


if '__main__'==__name__:
    main()
