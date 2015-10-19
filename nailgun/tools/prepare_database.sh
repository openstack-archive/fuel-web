#!/bin/sh

root_roles=$(sudo -H -u postgres psql -t -c "SELECT 'HERE' from pg_roles where rolname='${NAILGUN_DB_USER}'")
if [[ ${root_roles} == *HERE ]];then
  sudo -H -u postgres psql -c "ALTER ROLE ${NAILGUN_DB_USER} WITH SUPERUSER LOGIN PASSWORD '${NAILGUN_DB_PASSWD}'"
else
  sudo -H -u postgres psql -c "CREATE ROLE ${NAILGUN_DB_USER} WITH SUPERUSER LOGIN PASSWORD '${NAILGUN_DB_PASSWD}'"
fi

psql -h 127.0.0.1 -U ${NAILGUN_DB_USER} -d template1 -c "DROP DATABASE IF EXISTS ${NAILGUN_DB}"
createdb -h 127.0.0.1 -U ${NAILGUN_DB_USER} -l C -T template0 -E utf8 ${NAILGUN_DB}
