#    Copyright 2016 Mirantis, Inc.
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

cleanup_server() {
    echo "Stopping Nailgun and waiting $NAILGUN_START_MAX_WAIT_TIME seconds."
    local pid="$(lsof -ti tcp:${NAILGUN_PORT})"
    local kill9=0
    if [[ -z "$pid" ]]; then
        return 0
    fi
    kill ${pid} >/dev/null 2>&1
    for i in $(seq 1 $NAILGUN_START_MAX_WAIT_TIME); do
        if kill -0 ${pid} >/dev/null 2>&1; then
            kill9=1
            sleep 1
        else
            kill9=0
            break
        fi
    done
    if  [[ ${kill9} -ne 0  ]]; then
        kill -9 ${pid} >/dev/null 2>&1
    fi
    return 0
}

cleanup_nailgun_env() {
    rm -f "$NAILGUN_LOGS/nailgun.log"
    rm -f "$NAILGUN_LOGS/app.log"
    rm -f "$NAILGUN_LOGS/api.log"
    rm -f "${NAILGUN_CONFIG}"
}

prepare_nailgun_env() {
    mkdir -p $(dirname "${NAILGUN_CONFIG}")
    mkdir -p $(dirname "${NAILGUN_LOGS}")
    cat > "${NAILGUN_CONFIG}" <<EOL
DEVELOPMENT: 1
STATIC_DIR: "${NAILGUN_STATIC}"
TEMPLATE_DIR: "${NAILGUN_TEMPLATES}"
DATABASE:
  name: "${NAILGUN_DB}"
  engine: "postgresql"
  host: "${NAILGUN_DB_HOST}"
  port: "${NAILGUN_DB_PORT}"
  user: "${NAILGUN_DB_USER}"
  passwd: "${NAILGUN_DB_PW}"
API_LOG: "${NAILGUN_LOGS}/api.log"
APP_LOG: "${NAILGUN_LOGS}/app.log"
RPC_CONSUMER_LOG_PATH: "${NAILGUN_LOGS}/receiverd.log"
ASSASSIN_LOG_PATH: "${NAILGUN_LOGS}/assassind.log"
STATS_LOGS_PATH: ${NAILGUN_LOGS}
EOL
}

prepare_server() {
    python ${NAILGUN_ROOT}/manage.py syncdb > /dev/null
    python ${NAILGUN_ROOT}/manage.py loaddefault > /dev/null
    if test -n "$NAILGUN_FIXTURE_FILES"; then
        for nailgun_fixture_file in $NAILGUN_FIXTURE_FILES; do
            python ${NAILGUN_ROOT}/manage.py loaddata $nailgun_fixture_file > /dev/null
        done
    fi

    python ${NAILGUN_ROOT}/manage.py run \
        --port=$NAILGUN_PORT \
        --config="$NAILGUN_CONFIG" \
        --fake-tasks \
        --fake-tasks-tick-count=80 \
        --fake-tasks-tick-interval=1 >> "$NAILGUN_LOGS/nailgun.log" 2>&1 &

    which curl >/dev/null 2>&1
    if [[ $? -ne 0 ]]; then
        echo "WARNING: Cannot check whether Nailgun is running bacause curl is not available."
        return 1
    fi

    echo "INFO: Waiting $NAILGUN_START_MAX_WAIT_TIME in order to let it start properly."

    local check_url="http://127.0.0.1:${NAILGUN_PORT}${NAILGUN_CHECK_URL}"
    local nailgun_status=1
    for i in $(seq 1 $NAILGUN_START_MAX_WAIT_TIME); do
        echo "Trying to send a request: curl -s -w %{http_code} -o /dev/null ${check_url}"
        local http_code=$(curl -s -w %{http_code} -o /dev/null ${check_url})
        if [[ "$http_code" = "200" ]]; then
            echo "OK: Nailgun server seems working and ready to use."
            nailgun_status=0
            break
        fi
        sleep 1
    done
    if test $nailgun_status -ne 0; then
        echo "CRITICAL: Nailgun failed to start before the timeout exceeded."
        echo "          It's possible to increase waiting time setting the required"
        echo "          number of seconds in NAILGUN_START_MAX_WAIT_TIME environment variable."
        return 1
    fi
    return 0
}

cleanup_pgpass() {
    rm -f ${DB_ROOTPGPASS}
}

prepare_pgpass() {
    echo "Preparing pgpass file ${DB_ROOTPGPASS}"
    mkdir -p $(dirname ${DB_ROOTPGPASS})
    echo "*:*:*:${DB_ROOT}:${DB_ROOTPW}" > ${DB_ROOTPGPASS}
    chmod 600 ${DB_ROOTPGPASS}
    export PGPASSFILE=${DB_ROOTPGPASS}
}

cleanup_database_role() {
    # requires pgpass
    echo "Dropping role ${NAILGUN_DB_USER} if exists"
    psql -h ${NAILGUN_DB_HOST} -p ${NAILGUN_DB_PORT} -U ${DB_ROOT} -c "DROP ROLE IF EXISTS ${NAILGUN_DB_USER}"
}

cleanup_database() {
    # requires pgpass
    echo "Terminating database activities for ${NAILGUN_DB} if there are any"
    psql -h ${NAILGUN_DB_HOST} -p ${NAILGUN_DB_PORT} -U ${DB_ROOT} \
        -c "SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '${NAILGUN_DB}'
            AND pid <> pg_backend_pid()"
    echo "Dropping database ${NAILGUN_DB} if exists"
    psql -h ${NAILGUN_DB_HOST} -p ${NAILGUN_DB_PORT} -U ${DB_ROOT} -c "DROP DATABASE IF EXISTS ${NAILGUN_DB}"
}

prepare_database_role() {
    # requires pgpass
    echo "Trying to find out if role ${NAILGUN_DB_USER} exists"
    local roles=$(psql -h 127.0.0.1 -U ${DB_ROOT} -t -c "SELECT 'HERE' from pg_roles where rolname='${NAILGUN_DB_USER}'")
    if [[ ${roles} == *HERE ]]; then
        echo "Role ${NAILGUN_DB_USER} exists. Setting password ${NAILGUN_DB_PW}"
        psql -h ${NAILGUN_DB_HOST} -p ${NAILGUN_DB_PORT} -U ${DB_ROOT} -c "ALTER ROLE ${NAILGUN_DB_USER} WITH SUPERUSER LOGIN PASSWORD '${NAILGUN_DB_PW}'"
    else
        echo "Creating role ${NAILGUN_DB_USER} with password ${NAILGUN_DB_PASSWD}"
        psql -h ${NAILGUN_DB_HOST} -p ${NAILGUN_DB_PORT} -U ${DB_ROOT} -c "CREATE ROLE ${NAILGUN_DB_USER} WITH SUPERUSER LOGIN PASSWORD '${NAILGUN_DB_PW}'"
    fi
}

prepare_database() {
    # requires pgpass
    echo "Trying to find out if database ${NAILGUN_DB} exists"
    local databases=$(psql -h ${NAILGUN_DB_HOST} -p ${NAILGUN_DB_PORT} -U ${DB_ROOT} -t -c "SELECT 'HERE' from pg_database where datname='${NAILGUN_DB}'")
    if [[ ${databases} == *HERE ]]; then
        echo "Database ${NAILGUN_DB} exists"
    else
        echo "Creating database ${NAILGUN_DB}"
        psql -h ${NAILGUN_DB_HOST} -p ${NAILGUN_DB_PORT} -U ${DB_ROOT} -c "CREATE DATABASE ${NAILGUN_DB} OWNER ${NAILGUN_DB_USER}"
    fi
}
