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

try:
    user_resp = client.user.delete(key, login)
except xmlrpclib.Fault:
    print "User delete failed :("
    client.auth.logout(key)
    sys.exit(1)

client.auth.logout(key)
