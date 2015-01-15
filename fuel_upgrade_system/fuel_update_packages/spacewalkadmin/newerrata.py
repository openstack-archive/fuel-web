#!/usr/bin/python
from datetime import datetime
import sys
import time
import urllib
import xmlrpclib

SATELLITE_URL = "https://spacewalktest/rpc/api"
SATELLITE_LOGIN = "admin"
SATELLITE_PASSWORD = "admin"
CHANNEL="fuel60"

client = xmlrpclib.Server(SATELLITE_URL, verbose=0)

key = client.auth.login(SATELLITE_LOGIN, SATELLITE_PASSWORD)


synopsis = "Synposis goes here"
advisory_name = "MIRA-001"
advisory_release = 1
#Valid choices: 'Security Advisory', 'Product Enhancement Advisory', 
#               'Bug Fix Advisory'
advisory_type = 'Bug Fix Advisory'
product = 'Mirantis OpenStack 6.0'
errataFrom = "Mirantis"
topic = "MySQL update"
description = '''
How to apply this erratum:
service mysql stop
yum update --advisory MIRA-001
service mysql start'''
references = ""
notes = ""
solution = "See description"
bugs = [{'id': 100000, 'summary': 'MySQL update', 'url':
        'http://bugs.launchpad.net/bug/100000'}]
keywords = []
packages = [9766,]
publish = True
publishChannels = ['fuel60',]

errata_info = {
    'synopsis': synopsis,
    'advisory_name': advisory_name,
    'advisory_release': advisory_release,
    'advisory_type': advisory_type,
    'product': product,
    'errataFrom': errataFrom,
    'topic': topic,
    'description': description,
    'references': references,
    'notes': notes,
    'solution': solution}

errata_resp = client.errata.create(key, errata_info, bugs, keywords, packages,
                                   publish, publishChannels)
print errata_resp
client.auth.logout(key)
