#    Copyright 2013 Mirantis, Inc.
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

import fnmatch
import logging
import os
import re
import stat
import tempfile

import fabric.api

from shotgun.utils import execute
from shotgun.utils import is_local


logger = logging.getLogger(__name__)


class CommandOut(object):
    stdout = None
    return_code = None
    stderr = None

    def __eq__(self, other):
        return (
            str(self.stdout) == str(other.stdout) and
            str(self.stderr) == str(other.stderr) and
            str(self.return_code) == str(other.return_code)
        )


class Driver(object):
    @classmethod
    def getDriver(cls, data, conf):
        driver_type = data["type"]
        return {
            "file": File,
            "dir": Dir,
            "subs": Subs,
            "postgres": Postgres,
            "command": Command,
        }.get(driver_type, cls)(data, conf)

    def __init__(self, data, conf):
        logger.debug("Initializing driver %s: host=%s",
                     self.__class__.__name__, data.get("host"))
        self.data = data
        self.host = self.data.get("host", "localhost")
        self.local = is_local(self.host)
        self.conf = conf

    def snapshot(self):
        raise NotImplementedError

    def command(self, command):
        out = CommandOut()
        try:
            if not self.local:
                with fabric.api.settings(host_string=self.host,
                                         timeout=2, warn_only=True):
                    logger.debug("Running remote command: "
                                 "host: %s command: %s", self.host, command)
                    output = fabric.api.run(command, pty=True)
                    out.stdout = output
                    out.return_code = output.return_code
                    out.stderr = output.stderr
            else:
                logger.debug("Running local command: %s", command)
                out.return_code, out.stdout, out.stderr = execute(command)
            logger.debug("Stderr: %s", out.stderr)
        except Exception as e:
            logger.error("Error occured: %s", str(e))
        return out

    def get(self, path, target_path):
        """target_path must be the directory where to put
        copied files or directories
        """
        try:
            if not self.local:
                with fabric.api.settings(host_string=self.host,
                                         timeout=2, warn_only=True):
                    logger.debug("Getting remote file: %s %s",
                                 path, target_path)
                    execute("mkdir -p %s" % target_path)
                    return fabric.api.get(path, target_path)
            else:
                logger.debug("Getting local file: cp -r %s %s",
                             path, target_path)
                execute("mkdir -p %s" % target_path)
                return execute("cp -r %s %s" % (path, target_path))
        except Exception as e:
            logger.error("Error occured: %s", str(e))


class File(Driver):
    def __init__(self, data, conf):
        super(File, self).__init__(data, conf)
        self.path = self.data["path"]
        logger.debug("File to get: %s", self.path)
        self.target_path = str(os.path.join(
            self.conf.target, self.host,
            os.path.dirname(self.path).lstrip("/")))
        logger.debug("File to save: %s", self.target_path)

    def snapshot(self):
        """Example:
        self.conf.target IS /target
        self.host IS host.domain.tld
        self.path IS /var/log/somedir
        self.target_path IS /target/host.domain.tld/var/log
        """
        self.get(self.path, self.target_path)


Dir = File


class Subs(File):
    def __init__(self, data, conf):
        super(Subs, self).__init__(data, conf)
        self.subs = self.data["subs"]

    def decompress(self, filename):
        if re.search(ur".+\.gz$", filename):
            return "gunzip -c"
        elif re.search(ur".+\.bz2$", filename):
            return "bunzip2 -c"
        return ""

    def compress(self, filename):
        if re.search(ur".+\.gz$", filename):
            return "gzip -c"
        elif re.search(ur".+\.bz2$", filename):
            return "bzip2 -c"
        return ""

    def sed(self, from_filename, to_filename, gz=False):
        sedscript = tempfile.NamedTemporaryFile()
        logger.debug("Sed script: %s", sedscript.name)
        for orig, new in self.subs.iteritems():
            logger.debug("Sed script: s/%s/%s/g", orig, new)
            sedscript.write("s/%s/%s/g\n" % (orig, new))
            sedscript.flush()
        command = " | ".join(filter(lambda x: x != "", [
            "cat %s" % from_filename,
            self.decompress(from_filename),
            "sed -f %s" % sedscript.name,
            self.compress(from_filename),
        ]))
        execute(command, to_filename=to_filename)
        sedscript.close()

    def snapshot(self):
        """Example:
        self.conf.target IS /target
        self.host IS host.domain.tld
        self.path IS /var/log/somedir (it can be /var/log/somedir*)
        self.target_path IS /target/host.domain.tld/var/log

        1. we get remote directory host.domain.tld:/var/log/somedir
        2. we put it into /target/host.domain.tld/var/log
        3. we walk through /target/host.domain.tld/var/log
        4. we check fnmatch(/var/log/*, /var/log/somedir)
        """
        # 1.
        # 2.
        super(Subs, self).snapshot()
        # 3.
        walk = os.walk(self.target_path)
        for root, _, files in walk:
            for filename in files:
                # /target/host.domain.tld/var/log/somedir/1/2
                fullfilename = os.path.join(root, filename)
                # 4.
                # /target/host.domain.tld
                tgt_host = os.path.join(self.conf.target, self.host)
                # var/log/somedir/1/2
                rel_tgt_host = os.path.relpath(fullfilename, tgt_host)
                # /var/log/somedir/1/2
                match_orig_path = os.path.join("/", rel_tgt_host)
                if not fnmatch.fnmatch(match_orig_path, self.path):
                    continue
                tempfilename = execute("mktemp")[1].strip()
                self.sed(fullfilename, tempfilename)
                execute("mv -f %s %s" % (tempfilename, fullfilename))


class Postgres(Driver):
    def __init__(self, data, conf):
        super(Postgres, self).__init__(data, conf)
        self.dbhost = self.data.get("dbhost", "localhost")
        self.dbname = self.data["dbname"]
        self.username = self.data.get("username", "postgres")
        self.password = self.data.get("password")
        self.target_path = str(os.path.join(self.conf.target,
                               self.host, "pg_dump"))

    def snapshot(self):
        if self.password:
            authline = "{host}:{port}:{dbname}:{username}:{password}".format(
                host=self.host, port="5432", dbname=self.dbname,
                username=self.username, password=self.password)
            with open(os.path.expanduser("~/.pgpass"), "a+") as fo:
                fo.seek(0)
                auth = False
                for line in fo:
                    if re.search(ur"^%s$" % authline, line):
                        auth = True
                        break
                if not auth:
                    fo.seek(0, 2)
                    fo.write("{0}\n".format(authline))
            os.chmod(os.path.expanduser("~/.pgpass"),
                     stat.S_IRUSR + stat.S_IWUSR)
        temp = self.command("mktemp").stdout.strip()
        self.command("pg_dump -h {dbhost} -U {username} -w "
                     "-f {file} {dbname}".format(
                         dbhost=self.dbhost, username=self.username,
                         file=temp, dbname=self.dbname))
        execute("mkdir -p %s" % self.target_path)
        dump_basename = "%s_%s.sql" % (self.dbhost, self.dbname)

        execute('mv -f {0} {1}'.format(
            temp,
            os.path.join(self.target_path, dump_basename)))


class Command(Driver):
    def __init__(self, data, conf):
        super(Command, self).__init__(data, conf)
        self.cmdname = self.data["command"]
        self.to_file = self.data["to_file"]
        self.target_path = os.path.join(
            self.conf.target, self.host, "commands", self.to_file)

    def snapshot(self):
        out = self.command(self.cmdname)
        execute("mkdir -p {0}".format(os.path.dirname(self.target_path)))
        with open(self.target_path, "w") as f:
            f.write("===== COMMAND =====: {0}\n".format(self.cmdname))
            f.write("===== RETURN CODE =====: {0}\n".format(
                str(out.return_code)))
            f.write("===== STDOUT =====:\n")
            f.write(str(out.stdout))
            f.write("\n===== STDERR =====:\n")
            f.write(str(out.stderr))
