import sys
import os
import logging
import requests
import argparse

sys.path[:0] = [os.path.join(os.path.dirname(__file__), '..')]
from fuel_agent_ci.drivers.simple_http_driver import CustomHTTPServer


logging.basicConfig(level=logging.DEBUG)
LOG = logging.getLogger(__name__)

def start():
    server = CustomHTTPServer('0.0.0.0', 10010, '/tmp', piddir='/var/run/fuel')
    server.start()

def status():
    try:
        r = requests.get('http://localhost:10010/status')
        print r.status_code
    except:
        print 'FAILED'


def stop():
    server = CustomHTTPServer('0.0.0.0', 10010, '/tmp', piddir='/var/run/fuel')
    server.stop()

def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='action')
    start_parser = subparsers.add_parser('start')
    status_parser = subparsers.add_parser('status')
    stop_parser = subparsers.add_parser('stop')

    options, other = parser.parse_known_args()
    if options.action == 'start':
        start()
    elif options.action == 'status':
        status()
    elif options.action == 'stop':
        stop()

if __name__ == '__main__':
    main()