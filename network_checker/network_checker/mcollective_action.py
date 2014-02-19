import os
import sys
import json


class MCollectiveActionNoEnv(Exception):
    pass


class MCollectiveActionFileError(Exception):
    pass


class MCollectiveAction(object):

    def __init__(self, *args, **kwargs):
        try:
            self.infile = os.environ['MCOLLECTIVE_REQUEST_FILE']
        except KeyError:
            raise MCollectiveActionNoEnv('No MCOLLECTIVE_REQUEST_FILE'
                                         ' environment variable')
        try:
            self.outfile = os.environ['MCOLLECTIVE_REPLY_FILE']
        except KeyError:
            raise MCollectiveActionNoEnv('No MCOLLECTIVE_REPLY_FILE'
                                         ' environment variable')

        self.request = {}
        self.reply = {}

        self.load()

    def load(self):
        if not self.infile:
            return False
        with open(self.infile, 'r') as infile:
            try:
                self.request = json.load(infile)
            except IOError, e:
                raise MCollectiveActionFileError(
                    'Could not read request '
                    'file `%s`: %s' % (self.infile, e))
            except json.JSONDecodeError, e:
                raise MCollectiveActionFileError(
                    'Could not parse JSON data'
                    ' in file `%s`: %s', (self.infile, e))

    def send(self):
        if not getattr(self, 'outfile', None):
            return False
        with open(self.outfile, 'w') as outfile:
            try:
                json.dump(self.reply, outfile)
            except IOError, e:
                raise MCollectiveActionFileError(
                    "Could not write reply file `%s`: %s" % (self.outfile, e))

    def error(self, msg):
        """Prints line to STDERR that will be logged
            at error level in the mcollectived log file
        """
        sys.stderr.write("%s\n" % msg)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_value is not None:
            self.fail(str(exc_value))

    def fail(self, msg):
        """Logs error message and exitst with RPCAborted"""
        self.error(msg)
        sys.exit(1)

    def info(self, msg):
        """Prints line to STDOUT that will be logged
            at info level in the mcollectived log file
        """
        sys.stdout.write("%s\n" % msg)

    def __del__(self):
        self.send()
