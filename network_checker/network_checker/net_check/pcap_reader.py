#    Copyright 2015 Mirantis, Inc.
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

import struct
import threading
import time

from scapy.config import conf
from scapy import plist
from scapy.utils import PcapReader


def valid_header(file_obj):
    # following code borrowed from scapy.utils
    magic = file_obj.read(4)
    if magic == "\xa1\xb2\xc3\xd4":
        endian = ">"
    elif magic == "\xd4\xc3\xb2\xa1":
        endian = "<"
    else:
        return None
    hdr = file_obj.read(20)
    if len(hdr) < 20:
        return None
    vermaj, vermin, tz, sig, snaplen, linktype = struct.unpack(
        endian + "HHIIII", hdr)

    return endian, linktype


class NetcheckPcapReader(PcapReader):

    def __init__(self, file_obj):
        self.f = file_obj

        self.endian, self.linktype = valid_header(file_obj)
        try:
            self.LLcls = conf.l2types[self.linktype]
        except KeyError:
            self.LLcls = conf.raw_layer

    def get_packet(self):
        f_pos = self.tell()
        hdr = self.f.read(16)
        if hdr:
            return self.read_packet()
        else:
            self.f.seek(f_pos)
            return None


class PcapWorker(threading.Thread):

    def __init__(self, iface, file_path):
        super(PcapWorker, self).__init__()
        self._stop = threading.Event()
        self.file_path = file_path
        self.raw_pkts = []
        self.iface = iface

    def run(self):
        reader = None
        with open(self.file_path, 'rb') as file_obj:

            while not self.stopped:
                if not reader:
                    # if header is not valid - no data was written to a file
                    if valid_header(file_obj):
                        reader = NetcheckPcapReader(file_obj)
                    else:
                        file_obj.seek(0)
                else:
                    pkt = reader.get_packet()
                    if pkt:
                        self.raw_pkts.append(pkt)
            time.sleep(1)

    def get(self):
        return plist.PacketList(self.raw_pkts)

    def stop(self):
        self._stop.set()

    @property
    def stopped(self):
        return self._stop.isSet()
