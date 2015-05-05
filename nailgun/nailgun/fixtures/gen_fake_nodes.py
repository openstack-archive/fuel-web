#!/usr/bin/env python
# -*- coding: utf-8 -*-

import collections
import copy
import json
import random
import string
import sys

MANUFACTURERS = {
    "real": (
        "Supermicro",
        "80AD",
        "Intel",
        "Samsung",
    ),
    "virtual": (
        "VirtualBox",
    )
}

MCOUNTER = collections.Counter()

SAMPLE_CPUS = {
    "real": (
        {
            "model": "Intel(R) Xeon(R) CPU E5-2620 0 @ 2.00GHz",
            "frequency": 2001
        },
        {
            "model": "Intel(R) Xeon(R) CPU E31230 @ 3.20GHz",
            "frequency": 3201
        },
    ),
    "virtual": (
        {
            "model": "QEMU Virtual CPU version 1.0",
            "frequency": 1999
        },
    )
}

SAMPLE_INTERFACE = {
    "mac": "00:25:90:6a:b1:10",
    "max_speed": 1000,
    "name": "eth0",
    "current_speed": 1000,
    "driver": "igb",
    "bus_info": "0000:01:00.0"
}

SAMPLE_DISKS = [
    {
        "model": "TOSHIBA MK1002TS",
        "name": "sda",
        "disk": "sda",
        "size": 1000204886016
    },
    {
        "model": "Virtual Floppy0",
        "name": "sde",
        "disk": "sde",
        "size": 0
    },
    {
        "model": "Silicon-Power16G",
        "name": "sdb",
        "disk": "sdb",
        "size": 15518924800
    },
    {
        "model": "WDC WD3200BPVT-7",
        "name": "sda",
        "disk": "sda",
        "size": 320072933376
    }
]

SAMPLE_MEMORY = [
    {
        "frequency": 1333,
        "type": "DDR3",
        "size": 8589934592
    },
    {
        "frequency": 1333,
        "type": "DDR3",
        "size": 4294967296
    }
]


SAMPLE_NODE = {
    "pk": 1,
    "model": "nailgun.node",
    "fields": {
        "manufacturer": "Supermicro",
        "status": "discover",
        "name": "Supermicro X9DRW",
        "online": True,
        "timestamp": "",
        "meta": {
            "cpu": {
                "real": 0,
                "total": 0,
                "spec": []
            },
            "interfaces": [],
            "disks": [],
            "system": {
                "product": "X9DRW",
                "family": "To be filled by O.E.M.",
                "fqdn": "srv08-srt.srt.mirantis.net",
                "version": "0123456789",
                "serial": "0123456789",
                "manufacturer": "Supermicro"
            },
            "memory": {
                "slots": 1,
                "total": 137455730688,
                "maximum_capacity": 274894684160,
                "devices": []
            }
        }
    }
}


def generate_random_mac():
    mac = (random.randint(0x00, 0x7f) for _ in xrange(6))
    return ':'.join(map(lambda x: "%02x" % x, mac)).lower()


def generate_ifaces_with_one_predefined_mac(known_mac, amount):
    ifaces = []
    for i in xrange(amount):
        new_iface = SAMPLE_INTERFACE.copy()
        new_iface["mac"] = generate_random_mac()
        new_iface["name"] = "eth{0}".format(i)
        new_iface["bus_info"] = "0000:0{0}:00.0".format(i)
        new_iface["max_speed"] = random.choice([100, 1000, 56000])
        new_iface["current_speed"] = random.choice([100, 1000, None])
        ifaces.append(new_iface)

    ifaces[random.randint(0, amount-1)]["mac"] = known_mac
    return ifaces


def generate_disks(amount):
    disks = []
    for i in xrange(amount):
        letter = string.ascii_lowercase[i]
        new_disk = random.choice(SAMPLE_DISKS).copy()
        new_disk["name"] = new_disk["disk"] = "sd{0}".format(letter)
        disks.append(new_disk)
    return disks


def create_node(pk):
    new_node = copy.deepcopy(SAMPLE_NODE)
    new_node["pk"] = pk

    mac = generate_random_mac()
    new_node["fields"]["mac"] = mac

    kind = random.choice(["real", "virtual"])

    manuf = random.choice(MANUFACTURERS[kind])
    new_node["fields"]["manufacturer"] = manuf
    new_node["fields"]["name"] = manuf + " ({0})".format(
        MCOUNTER[manuf] + 1 if manuf in MCOUNTER else 1
    )
    MCOUNTER[manuf] += 1

    new_node["fields"]["meta"]["system"]["manufacturer"] = manuf
    new_node["fields"]["meta"]["system"]["version"] = "".join(
        [str(random.randint(0, 9)) for _ in xrange(10)]
    )
    new_node["fields"]["meta"]["system"]["serial"] = "".join(
        [str(random.randint(0, 9)) for _ in xrange(10)]
    )

    real_proc = random.choice([1, 2, 4])
    total_proc = real_proc * random.choice([1, 2, 4])
    new_node["fields"]["meta"]["cpu"]["real"] = real_proc
    new_node["fields"]["meta"]["cpu"]["total"] = total_proc

    proc = random.choice(SAMPLE_CPUS[kind])
    new_node["fields"]["meta"]["cpu"]["spec"] = [
        proc.copy() for i in xrange(total_proc)
    ]

    new_node["fields"]["meta"]["interfaces"] = \
        generate_ifaces_with_one_predefined_mac(mac, random.randrange(1, 7))

    new_node["fields"]["meta"]["disks"] = generate_disks(
        random.randrange(1, 7)
    )

    maxcap = 1024 ** 3 * random.choice([8, 16, 32, 64])
    new_node["fields"]["meta"]["memory"]["slots"] = random.choice([1, 2, 4])

    total = 0
    for i in xrange(random.randrange(2, 9)):
        new_memory = random.choice(SAMPLE_MEMORY).copy()
        if (total + new_memory["size"]) > maxcap:
            break
        total += new_memory["size"]
        new_node["fields"]["meta"]["memory"]["devices"].append(new_memory)

    new_node["fields"]["meta"]["memory"]["total"] = total

    return new_node


if __name__ == "__main__":
    res = []
    for i in xrange(1, 51):
        res.append(create_node(i))

    sys.stdout.write(json.dumps(res, indent=4))
