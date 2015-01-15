#!/usr/bin/python
import sys
import xmlrpclib

SATELLITE_URL = "https://spacewalktest/rpc/api"
SATELLITE_LOGIN = "admin"
SATELLITE_PASSWORD = "admin"
CHANNEL_BASE = "all-"

client = xmlrpclib.Server(SATELLITE_URL, verbose=0)

key = client.auth.login(SATELLITE_LOGIN, SATELLITE_PASSWORD)

login = sys.argv[1]
password = sys.argv[1]
firstName = "Fuel"
lastName = "Fuel"
email = "mail@nomail.com"

try:
    user_resp = client.user.create(key, login, password, firstName, lastName,
                               email)
except xmlrpclib.Fault:
    print "User creation failed :("
    client.auth.logout(key)
    sys.exit(1)

try:
    my_channels = client.channel.listAllChannels(key)
    for channel in my_channels:
        if channel['label'].startswith(CHANNEL_BASE):
            print "Subscribing to channel: %s" % channel['label']
            try:
                client.channel.software.setUserSubscribable(key, 
                    channel['label'], login, True)
                print "Success!"
            except xmlrpclib.Fault, e:
                print "Failed :( %s " % e
except xmlrpclib.Fault:
    print "Error adding channel permissions to user."
    sys.exit(1)

client.auth.logout(key)
