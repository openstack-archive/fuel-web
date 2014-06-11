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

import jsonschema

from fuel_agent import errors


PARTITION_VALIDATION_SCHEMA = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'title': 'Partition scheme',
    'type': 'array',
    'minItems': 1,
    'uniqueItems': True,
    'items': {
        'anyOf': [
            {
                'type': 'object',
                'required': ['type', 'id', 'volumes', 'name',
                             'size', 'extra', 'free_space'],
                'properties': {
                    'type': {'enum': ['disk']},
                    'id':  {'type': 'string'},
                    'name': {'type': 'string'},
                    'size': {'type': 'integer'},
                    'free_space': {'type': 'integer'},
                    'extra': {
                        'type': 'array',
                        'items': {'type': 'string'},
                    },
                    'volumes': {
                        'type': 'array',
                        'items': {
                            'anyOf': [
                                {
                                    'type': 'object',
                                    'required': ['type', 'size',
                                                 'lvm_meta_size', 'vg'],
                                    'properties': {
                                        'type': {'enum': ['pv']},
                                        'size': {'type': 'integer'},
                                        'lvm_meta_size': {'type': 'integer'},
                                        'vg': {'type': 'string'}
                                    }
                                },
                                {
                                    'type': 'object',
                                    'required': ['type', 'size'],
                                    'properties': {
                                        'type': {'enum': ['raid']},
                                        'size': {'type': 'integer'},
                                        'mount': {'type': 'string'},
                                        'file_system': {'type': 'string'},
                                        'name': {'type': 'string'}
                                    }
                                },
                                {
                                    'type': 'object',
                                    'required': ['type', 'size'],
                                    'properties': {
                                        'type': {'enum': ['boot']},
                                        'size': {'type': 'integer'}
                                    }
                                },
                                {
                                    'type': 'object',
                                    'required': ['type', 'size'],
                                    'properties': {
                                        'type': {'enum': ['lvm_meta_pool']},
                                        'size': {'type': 'integer'}
                                    }
                                },

                            ]
                        }
                    }
                }
            },
            {
                'type': 'object',
                'required': ['type', 'id', 'volumes'],
                'properties': {
                    'type': {'enum': ['vg']},
                    'id':  {'type': 'string'},
                    'label': {'type': 'string'},
                    'min_size': {'type': 'integer'},
                    '_allocate_size': {'type': 'string'},
                    'volumes': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'required': ['type', 'size', 'name'],
                            'properties': {
                                'type': {'enum': ['lv']},
                                'size': {'type': 'integer'},
                                'name': {'type': 'string'},
                                'mount': {'type': 'string'},
                                'file_system': {'type': 'string'},
                            }
                        }
                    }
                }
            }
        ]
    }
}


class PartitionDriver(object):
    """This class is partly based on pmanager.py which
    is used in cobbler puppet module to prepare kickstart and preseed scripts
    """

    def __init__(self, pm_data):

        if isinstance(pm_data, (str, unicode)):
            self.pm_data = json.loads(pm_data)
        else:
            self.pm_data = pm_data

        self.scheme = self.pm_data['ks_spaces']
        self._validate_scheme(self.scheme)

        self.kernel_params = self.pm_data['kernel_params']

        self.factor = 1
        self.unit = "MiB"
        self._pre = []
        self._kick = []
        self._post = []
        self.raid_count = 0

        self._pcount = {}
        self._pend = {}
        self._rcount = 0
        self._pvcount = 0


    def _validate_scheme(self, scheme=None):
        """Validates a given partition scheme using jsonschema.

        :param scheme: partition scheme to validate
        """
        try:
            checker = jsonschema.FormatChecker()
            jsonschema.validate(scheme, PARTITION_VALIDATION_SCHEMA,
                                format_checker=checker)
        except Exception as exc:
            raise errors.WrongPartitionSchemeError(str(exc))

        # scheme is not valid if the number of disks is 0
        if not [d for d in scheme if d['type'] == 'disk']:
            raise errors.WrongPartitionSchemeError(
                'Partition scheme seems empty')

        # TODO(kozhukalov): need to have additional logical verifications
        # maybe sizes and format of string values

    def plains(self, volume_filter=None):
        if volume_filter is None:
            volume_filter = lambda x: True

        ceph_osds = self.num_ceph_osds()
        journals_left = ceph_osds
        ceph_journals = self.num_ceph_journals()

        for disk in self.iterdisks():
            for part in filter(lambda p: p["type"] == "partition" and
                               volume_filter(p), disk["volumes"]):
                if part["size"] <= 0:
                    continue

                if part.get('name') == 'cephjournal':
                    # We need to allocate a journal partition for each ceph OSD
                    # Determine the number of journal partitions we need on each device
                    ratio = math.ceil(float(ceph_osds) / ceph_journals)

                    # No more than 10GB will be allocated to a single journal partition
                    size = part["size"] / ratio
                    if size > 10240:
                        size = 10240

                    # This will attempt to evenly spread partitions across
                    # multiple devices e.g. 5 osds with 2 journal devices will
                    # create 3 partitions on the first device and 2 on the
                    # second
                    if ratio < journals_left:
                        end = ratio
                    else:
                        end = journals_left

                    for i in range(0, end):
                        journals_left -= 1
                        pcount = self.pcount(disk["id"], 1)

                        self.pre("parted -a none -s /dev/{0} "
                                 "unit {4} mkpart {1} {2} {3}".format(
                                     disk["id"],
                                     self._parttype(pcount),
                                     self.psize(disk["id"]),
                                     self.psize(disk["id"], size * self.factor),
                                     self.unit))

                        self.post("chroot /mnt/sysimage sgdisk "
                                  "--typecode={0}:{1} /dev/{2}".format(
                                    pcount, part["partition_guid"],disk["id"]))
                    continue

                pcount = self.pcount(disk["id"], 1)
                self.pre("parted -a none -s {0} "
                         "unit {4} mkpart {1} {2} {3}".format(
                             self._disk_dev(disk),
                             self._parttype(pcount),
                             self.psize(disk["id"]),
                             self.psize(disk["id"], part["size"] * self.factor),
                             self.unit))

                fstype = self._getfstype(part)
                size = self._getsize(part)
                tabmount = part["mount"] if part["mount"] != "swap" else "none"
                tabfstype = self._gettabfstype(part)
                tabfsoptions = self._gettabfsoptions(part)
                if part.get("partition_guid"):
                    self.post("chroot /mnt/sysimage sgdisk "
                              "--typecode={0}:{1} {2}".format(
                                  pcount, part["partition_guid"],
                                  self._disk_dev(disk)))
                if size > 0 and size <= 16777216 and part["mount"] != "none" \
                        and tabfstype != "xfs":
                    self.kick("partition {0} "
                              "--onpart={2}"
                              "{3}{4}".format(part["mount"], size,
                                           self._disk_dev(disk),
                                           self._pseparator(disk["id"]),
                                           pcount))

                else:
                    if part["mount"] != "swap" and tabfstype != "none":
                        disk_label = self._getlabel(part.get('disk_label'))
                        self.post("mkfs.{0} {1} {2}"
                                  "{3}{4} {5}".format(
                                      tabfstype,
                                      tabfsoptions,
                                      self._disk_dev(disk),
                                      self._pseparator(disk["id"]),
                                      pcount, disk_label))
                        if part["mount"] != "none":
                            self.post("mkdir -p /mnt/sysimage{0}".format(
                                part["mount"]))

                    if tabfstype != "none":
                        self.post("echo 'UUID=$(blkid -s UUID -o value "
                                  "{0}{1}{2}) "
                                  "{3} {4} defaults 0 0'"
                                  " >> /mnt/sysimage/etc/fstab".format(
                                      self._disk_dev(disk),
                                      self._pseparator(disk["id"]),
                                      pcount, tabmount, tabfstype))
