#!/usr/bin/env python

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

#
# Generate and send Ethernet packets to specified interfaces.
# Collect data from interfaces.
# Analyse dumps for packets with special cookie in UDP payload.
#
import argparse
import json
import logging
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import traceback

import logging.handlers


from scapy import config as scapy_config

scapy_config.logLevel = 40
scapy_config.use_pcap = True
import scapy.all as scapy
from scapy import error

from scapy.utils import PcapReader

from network_checker.net_check.utils import signal_timeout


class ActorFabric(object):
    @classmethod
    def getInstance(cls, config):
        if config.get('action') not in ('listen', 'generate'):
            raise Exception(
                'Wrong config, you need define '
                'valid action instead of {0}'.format(config.get('action')))
        if config['action'] in ('listen',):
            return Listener(config)
        elif config['action'] in ('generate',):
            return Sender(config)


class ActorException(Exception):
    def __init__(self, logger, message='', level='error'):
        getattr(logger, level, logger.error)(message)
        super(ActorException, self).__init__(message)


class Actor(object):
    def __init__(self, config=None):
        self.config = {
            'src_mac': None,
            'src': '198.18.1.1',
            'dst': '198.18.1.2',
            'sport': 31337,
            'dport': 31337,
            'cookie': "Nailgun:",
            'pcap_dir': "/var/run/pcap_dir/",
            'duration': 5,
            'repeat': 1,
            'collect_timeout': 300,
        }
        if config:
            self.config.update(config)

        self.logger.debug("Running with config: %s", json.dumps(self.config))
        self.iface_down_after = {}
        self.viface_remove_after = {}

    def _define_logger(self, filename=None,
                       appname='netprobe', level=logging.DEBUG):
        logger = logging.getLogger(appname)
        logger.setLevel(level)

        syslog_formatter = logging.Formatter(
            '{appname}: %(message)s'.format(appname=appname)
        )
        syslog_handler = logging.handlers.SysLogHandler('/dev/log')
        syslog_handler.setFormatter(syslog_formatter)
        logger.addHandler(syslog_handler)

        # A syslog handler should be always. But a file handler is the option.
        # If you don't want it you can keep 'filename' variable as None to skip
        # this handler.
        if filename:
            file_formatter = logging.Formatter(
                '%(asctime)s %(levelname)s %(name)s %(message)s'
            )

            file_handler = logging.FileHandler(filename)
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

        return logger

    def _execute(self, command, expected_exit_codes=(0,)):
        self.logger.debug("Running command: %s" % " ".join(command))
        env = os.environ
        env["PATH"] = "/bin:/usr/bin:/sbin:/usr/sbin"
        p = subprocess.Popen(command, shell=False,
                             env=env, stdout=subprocess.PIPE)
        output, _ = p.communicate()
        if p.returncode not in expected_exit_codes:
            raise ActorException(
                self.logger,
                "Command exited with error: %s: %s" % (" ".join(command),
                                                       p.returncode)
            )
        return output.split('\n')

    def _viface_by_iface_vid(self, iface, vid):
        return (self._try_viface_create(iface, vid) or "%s.%d" % (iface, vid))

    def _iface_name(self, iface, vid=None):
        if vid:
            return self._viface_by_iface_vid(iface, vid)
        return iface

    def _look_for_link(self, iface, vid=None):
        viface = None
        if vid:
            viface = self._viface_by_iface_vid(iface, vid)

        command = ['ip', 'link']
        r = re.compile(ur"(\d+?):\s+((?P<viface>[^:@]+)@)?(?P<iface>[^:]+?):"
                       ".+?(?P<state>UP|DOWN|UNKNOWN).*$")
        for line in self._execute(command):
            m = r.search(line)
            if m:
                md = m.groupdict()
                if (iface == md.get('iface') and
                        viface == md.get('viface') and md.get('state')):
                    return (iface, viface, md.get('state'))
        # If we are here we aren't able to say if iface with vid is up
        raise ActorException(
            self.logger,
            "Cannot find interface %s with vid=%s" % (iface, vid)
        )

    def _try_iface_up(self, iface, vid=None):
        if vid and not self._try_viface_create(iface, vid):
            # if viface does not exist we raise exception
            raise ActorException(
                self.logger,
                "Vlan %s on interface %s does not exist" % (str(vid), iface)
            )

        self.logger.debug("Checking if interface %s with vid %s is up",
                          iface, str(vid))
        _, _, state = self._look_for_link(iface, vid)
        return (state == 'UP')

    def _iface_up(self, iface, vid=None):
        """Brings interface with vid up"""
        if vid and not self._try_viface_create(iface, vid):
            # if viface does not exist we raise exception
            raise ActorException(
                self.logger,
                "Vlan %s on interface %s does not exist" % (str(vid), iface)
            )

        set_iface = self._iface_name(iface, vid)

        self.logger.debug("Brining interface %s with vid %s up",
                          set_iface, str(vid))
        self._execute([
            "ip",
            "link", "set",
            "dev", set_iface,
            "up"])

    def _ensure_iface_up(self, iface, vid=None):
        """Ensures interface is with vid up."""
        if not self._try_iface_up(iface, vid):
            # if iface is not up we try to bring it up
            self._iface_up(iface, vid)
            if self._try_iface_up(iface, vid):
                # if iface was down and we have brought it up
                # we should mark it to be brought down after probing
                self.iface_down_after[self._iface_name(iface, vid)] = True
            else:
                # if viface is still down we raise exception
                raise ActorException(
                    self.logger,
                    "Can not bring interface %s with vid %s up" % (iface,
                                                                   str(vid))
                )

    def _ensure_iface_down(self, iface, vid=None):
        set_iface = self._iface_name(iface, vid)
        if self.iface_down_after.get(set_iface, False):
            # if iface with vid have been marked to be brought down
            # after probing we try to bring it down
            self.logger.debug("Brining down interface %s with vid %s",
                              iface, str(vid))
            self._execute([
                "ip",
                "link", "set",
                "dev", set_iface,
                "down"])
            self.iface_down_after.pop(set_iface)

    def _try_viface_create(self, iface, vid):
        """Tries to find vlan interface on iface with VLAN_ID=vid and return it

            :returns: name of vlan interface if it exists or None
        """
        self.logger.debug("Checking if vlan %s on interface %s exists",
                          str(vid), iface)
        with open("/proc/net/vlan/config", "r") as f:
            for line in f:
                m = re.search(ur'(.+?)\s+\|\s+(.+?)\s+\|\s+(.+?)\s*$', line)
                if m and m.group(2) == str(vid) and m.group(3) == iface:
                    return m.group(1)

    def _viface_create(self, iface, vid):
        """Creates VLAN interface with VLAN_ID=vid on interface iface

            :returns: None
        """
        self.logger.debug("Creating vlan %s on interface %s", str(vid), iface)
        self._execute([
            "ip",
            "link", "add",
            "link", iface,
            "name", self._viface_by_iface_vid(iface, vid),
            "type", "vlan",
            "id", str(vid)])

    def _ensure_viface_create(self, iface, vid):
        """Ensures that vlan interface exists.

        If it does not already
        exist, then we need it to be created. It also marks newly created
        vlan interface to remove it after probing procedure.
        """
        if not self._try_viface_create(iface, vid):
            # if viface does not exist we try to create it
            self._viface_create(iface, vid)
            if self._try_viface_create(iface, vid):
                # if viface had not existed and have been created
                # we mark it to be removed after probing procedure
                self.viface_remove_after[
                    self._viface_by_iface_vid(iface, vid)
                ] = True
            else:
                # if viface had not existed and still does not
                # we raise exception
                raise ActorException(
                    self.logger,
                    "Can not create vlan %d on interface %s" % (vid, iface)
                )

    def _ensure_viface_remove(self, iface, vid):
        viface = self._viface_by_iface_vid(iface, vid)
        if self.viface_remove_after.get(viface, False):
            # if viface have been marked to be removed after probing
            # we try to remove it
            self.logger.debug("Removing vlan %s on interface %s",
                              str(vid), iface)
            self._execute([
                "ip",
                "link", "del",
                "dev", viface])
            self.viface_remove_after.pop(viface)

    def _parse_vlan_list(self, vlan_string):
        self.logger.debug("Parsing vlan list: %s", vlan_string)
        validate = lambda x: (x >= 0) and (x < 4095)
        chunks = vlan_string.split(",")
        vlan_list = []
        for chunk in chunks:
            delim = chunk.find("-")
            try:
                if delim > 0:
                    left = int(chunk[:delim])
                    right = int(chunk[delim + 1:])
                    if validate(left) and validate(right):
                        vlan_list.extend(xrange(left, right + 1))
                    else:
                        raise ValueError
                else:
                    vlan = int(chunk)
                    if validate(vlan):
                        vlan_list.append(vlan)
                    else:
                        raise ValueError
            except ValueError:
                raise ActorException(self.logger, "Incorrect vlan: %s" % chunk)
        self.logger.debug("Parsed vlans: %s", str(vlan_list))
        return vlan_list

    def _ensure_viface_create_and_up(self, iface, vid):
        self._ensure_viface_create(iface, vid)
        self._ensure_iface_up(iface, vid)

    def _ensure_viface_down_and_remove(self, iface, vid):
        self._ensure_iface_down(iface, vid)
        self._ensure_viface_remove(iface, vid)

    def _iface_vlan_iterator(self):
        for iface, vlan_list in self.config['interfaces'].iteritems():
            # Variables iface and vlan_list are getted from decoded JSON
            # and json.dump convert all string data to Python unicode string.
            # We use these variables in logging messages later.
            # CentOS 6.4 uses Python 2.6 and logging module 0.5.0.5 which has
            # a bug with converting unicode strings to message in
            # SysLogHandler. So we need to convert all unicode to plain
            # strings to avoid syslog message corruption.
            for vlan in self._parse_vlan_list(str(vlan_list)):
                yield (str(iface), vlan)

    def _iface_iterator(self):
        for iface in self.config['interfaces']:
            yield iface

    def _log_ifaces(self, prefix="Current interfaces"):
        self.logger.debug("%s: ", prefix)
        for line in self._execute(['ip', 'address']):
            self.logger.debug(line.rstrip())


class Sender(Actor):

    def __init__(self, config=None):
        self.logger = self._define_logger('/var/log/netprobe_sender.log',
                                          'netprobe_sender')
        super(Sender, self).__init__(config)
        self.logger.info("=== Starting Sender ===")
        self._log_ifaces("Interfaces just before sending probing packages")

    def run(self):
        try:
            self._run()
        except Exception as e:
            self.logger.error("An internal error occured: %s\n%s", str(e),
                              traceback.format_exc())

    def _get_iface_mac(self, iface):
        path = '/sys/class/net/{iface}/address'.format(iface=iface)
        with open(path, 'r') as address:
            return address.read().strip('\n')

    def _run(self):
        for iface, vlan in self._iface_vlan_iterator():
            self._ensure_iface_up(iface)
        self._send_packets()
        self._log_ifaces("Interfaces just after sending probing packages")
        for iface in self._iface_iterator():
            self._ensure_iface_down(iface)
        self._log_ifaces("Interfaces just after ensuring them down in sender")
        self.logger.info("=== Sender Finished ===")

    def _send_packets(self):
        start_time = time.time()

        while time.time() - start_time <= self.config['duration']:
            for iface, vlan in self._iface_vlan_iterator():
                self.logger.debug("Sending packets: iface=%s vlan=%s",
                                  iface, str(vlan))
                for _ in xrange(self.config['repeat']):
                    self._sendp(iface, vlan)

    def _sendp(self, iface, vlan):
        try:
            data = str(''.join((self.config['cookie'], iface, ' ',
                       self.config['uid'])))

            p = scapy.Ether(src=self._get_iface_mac(iface),
                            dst="ff:ff:ff:ff:ff:ff")
            if vlan > 0:
                p = p / scapy.Dot1Q(vlan=vlan)
            p = p / scapy.IP(src=self.config['src'], dst=self.config['dst'])
            p = p / scapy.UDP(sport=self.config['sport'],
                              dport=self.config['dport']) / data
            scapy.sendp(p, iface=iface)
        except socket.error as e:
            self.logger.error("Socket error: %s, %s", e, iface)


class Listener(Actor):
    def __init__(self, config=None):
        self.logger = self._define_logger('/var/log/netprobe_listener.log',
                                          'netprobe_listener')
        super(Listener, self).__init__(config)
        self.logger.info("=== Starting Listener ===")
        self._log_ifaces("Interfaces just before starting listerning "
                         "for probing packages")

        self.pidfile = self.addpid('/var/run/net_probe')

        self.neighbours = {}
        self._define_pcap_dir()

    def addpid(self, piddir):
        pid = os.getpid()
        if not os.path.exists(piddir):
            os.mkdir(piddir)
        pidfile = os.path.join(piddir, str(pid))
        with open(pidfile, 'w') as fo:
            fo.write('')
        return pidfile

    def _define_pcap_dir(self):
        if os.path.exists(self.config['pcap_dir']):
            shutil.rmtree(self.config['pcap_dir'])
        os.mkdir(self.config['pcap_dir'])

    def run(self):
        try:
            self._run()
        except Exception as e:
            self.logger.error("An internal error occured: %s\n%s", str(e),
                              traceback.format_exc())

    def _run(self):
        sniffers = set()
        listeners = []

        for iface in self._iface_iterator():
            self._ensure_iface_up(iface)
            if iface not in sniffers:
                listeners.append(self.get_probe_frames(iface))
                listeners.append(self.get_probe_frames(iface, vlan=True))
                sniffers.add(iface)

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.config.get('ready_address', 'locahost'),
                       self.config.get('ready_port', 31338)))
        except socket.error as e:
            self.logger.error("Socket error: %s", e)
        else:
            self.logger.debug("Listener threads have been launched. "
                              "Reporting READY.")
            msg = "READY"
            total_sent = 0
            while total_sent < len(msg):
                sent = s.send(msg[total_sent:])
                if sent == 0:
                    raise ActorException(
                        self.logger,
                        "Socket broken. Cannot send %s status." % msg
                    )
                total_sent += sent
            s.shutdown(socket.SHUT_RDWR)
            s.close()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.debug("Interruption signal catched")

        with signal_timeout(self.config['collect_timeout'], raise_exc=False):
            for listener in listeners:
                # terminate and flush pipes
                listener.terminate()
                out, err = listener.communicate()

                if err and listener.returncode:
                    self.logger.error('Listerner: %s', err)
                elif err:
                    self.logger.warning('Listener: %s', err)

            self.logger.debug('Start reading dumped information.')
            self.read_packets()
            self._log_ifaces("Interfaces just before ensuring interfaces down")

        for iface in self._iface_iterator():
            self._ensure_iface_down(iface)
        self._log_ifaces(
            "Interfaces just after ensuring them down in listener")

        with open(self.config['dump_file'], 'w') as fo:
            fo.write(json.dumps(self.neighbours))
        os.unlink(self.pidfile)
        self.logger.info("=== Listener Finished ===")

    def read_packets(self):
        for iface in self._iface_iterator():
            filenames = ['{0}.pcap'.format(iface),
                         'vlan_{0}.pcap'.format(iface)]
            for filename in filenames:
                self.read_pcap_file(iface, filename)

    def read_pcap_file(self, iface, filename):
        try:
            pcap_file = os.path.join(self.config['pcap_dir'], filename)
            for pkt in PcapReader(pcap_file):
                self.fprn(pkt, iface)
        except (IOError, error.Scapy_Exception) as exc:
            self.logger.exception(
                'Cant read pcap file %s, err: %s', pcap_file, str(exc))

    def fprn(self, p, iface):

        if scapy.Dot1Q in p:
            vlan = p[scapy.Dot1Q].vlan
        else:
            vlan = 0

        self.logger.debug("Catched packet: vlan=%s len=%s payload=%s",
                          str(vlan), p[scapy.UDP].len, p[scapy.UDP].payload)
        received_msg, _ = p[scapy.UDP].extract_padding(p[scapy.UDP].load)
        decoded_msg = received_msg.decode()
        riface, uid = decoded_msg[len(self.config["cookie"]):].split(' ', 1)

        self.neighbours[iface].setdefault(vlan, {})

        if riface not in self.neighbours[iface][vlan].setdefault(uid, []):
            self.neighbours[iface][vlan][uid].append(riface)

    def get_probe_frames(self, iface, vlan=False):
        if iface not in self.neighbours:
            self.neighbours[iface] = {}
        filter_string = 'udp and dst port {0}'.format(self.config['dport'])
        filename = '{0}.pcap'.format(iface)
        if vlan:
            filter_string = '{0} {1}'.format('vlan and', filter_string)
            filename = '{0}_{1}'.format('vlan', filename)
        pcap_file = os.path.join(self.config['pcap_dir'], filename)

        return subprocess.Popen(
            ['tcpdump', '-i', iface, '-w', pcap_file, filter_string],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

# -------------- main ---------------


def define_parser():
    config_examples = """

Config file examples:

Capture frames config file example is:
{"action": "listen", "interfaces": {"eth0": "1-4094"},
 "dump_file": "/var/tmp/net-probe-dump-eth0"}

Simple frame generation config file example is:
{"action": "generate", "uid": "aaa-bb-cccccc",
 "interfaces": { "eth0": "1-4094"}}

Full frame generation config file example is:
{   "action": "generate",
    "uid": "aaa-bb-cccccc", "cookie": "Some cookie",
    "src_mac": "11:22:33:44:55:66",
    "src": "10.0.0.1", "dst": "10.255.255.255",
    "sport": 4056, "dport": 4057,
    "interfaces": {
        "eth0": "10, 15, 20, 201-210, 301-310, 1000-2000",
        "eth1": "1-4094"
    }
}
    """

    parser = argparse.ArgumentParser(epilog=config_examples)
    parser.add_argument(
        '-c', '--config', dest='config', action='store', type=str,
        help='config file', default=None
    )
    return parser


def define_subparsers(parser):
    subparsers = parser.add_subparsers(
        dest="action", help='actions'
    )
    listen_parser = subparsers.add_parser(
        'listen', help='listen for probe packets'
    )
    listen_parser.add_argument(
        '-i', '--interface', dest='interface', action='store', type=str,
        help='interface to listen on', required=True
    )
    listen_parser.add_argument(
        '-v', '--vlans', dest='vlan_list', action='store', type=str,
        help='vlan list to send tagged packets ("100,200-300")', required=True
    )
    listen_parser.add_argument(
        '-k', '--cookie', dest='cookie', action='store', type=str,
        help='cookie string to insert into probe packets payload',
        default='Nailgun:'
    )
    listen_parser.add_argument(
        '-o', '--file', dest='dump_file', action='store', type=str,
        help='file to dump captured packets', default=None
    )
    listen_parser.add_argument(
        '-a', '--address', dest='ready_address', action='store', type=str,
        help='address to report listener ready state', default='localhost'
    )
    listen_parser.add_argument(
        '-p', '--port', dest='ready_port', action='store', type=int,
        help='port to report listener ready state', default=31338
    )
    generate_parser = subparsers.add_parser(
        'generate', help='generate and send probe packets'
    )
    generate_parser.add_argument(
        '-i', '--interface', dest='interface', action='store', type=str,
        help='interface to send packets from', required=True
    )
    generate_parser.add_argument(
        '-v', '--vlans', dest='vlan_list', action='store', type=str,
        help='vlan list to send tagged packets ("100,200-300")', required=True
    )
    generate_parser.add_argument(
        '-k', '--cookie', dest='cookie', action='store', type=str,
        help='cookie string to insert into probe packets payload',
        default='Nailgun:'
    )
    generate_parser.add_argument(
        '-u', '--uid', dest='uid', action='store', type=str,
        help='uid to insert into probe packets payload', default='1'
    )
    generate_parser.add_argument(
        '-d', '--duration', dest='duration', type=int, default=5,
        help='Amount of time to generate network packets. In seconds',
    )
    generate_parser.add_argument(
        '-r', '--repeat', dest='repeat', type=int, default=1,
        help='Amount of packets sended in one iteration.',
    )


def term_handler(signum, sigframe):
    sys.exit()


def main():
    signal.signal(signal.SIGTERM, term_handler)

    parser = define_parser()
    params, other_params = parser.parse_known_args()

    config = {}
    if params.config:
        # if config file is set then we discard all other
        # command line parameters
        try:
            if params.config == '-':
                fo = sys.stdin
            else:
                fo = open(params.config, 'r')
            config = json.load(fo)
            fo.close()
        except IOError:
            print("Can not read config file %s" % params.config)
            exit(1)
        except ValueError as e:
            print("Can not parse config file: %s" % str(e))
            exit(1)

    else:
        define_subparsers(parser)
        params, other_params = parser.parse_known_args()

        if params.action == 'listen':
            config['action'] = 'listen'
            config['interfaces'] = {}
            config['interfaces'][params.interface] = params.vlan_list
            config['cookie'] = params.cookie
            config['ready_address'] = params.ready_address
            config['ready_port'] = params.ready_port
            if params.dump_file:
                config['dump_file'] = params.dump_file
            else:
                config['dump_file'] = "/var/tmp/net-probe-dump-%s" %\
                    config['interface']

        elif params.action == 'generate':
            config['action'] = 'generate'
            config['interfaces'] = {}
            config['interfaces'][params.interface] = params.vlan_list
            config['uid'] = params.uid
            config['cookie'] = params.cookie
            config['duration'] = params.duration
            config['repeat'] = params.repeat

    actor = ActorFabric.getInstance(config)
    actor.run()

if __name__ == "__main__":
    main()
