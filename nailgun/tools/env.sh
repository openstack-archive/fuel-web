#!/bin/bash

echo $NAILGUN_PORT

# Sends SIGING to the running instance of Nailgun, if it exists.
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
    if  [ ${kill9} -ne 0  ]; then
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
  host: "localhost"
  port: "5432"
  user: "${NAILGUN_DB_USER}"
  passwd: "${NAILGUN_DB_PW}"
API_LOG: "${NAILGUN_LOGS}/api.log"
APP_LOG: "${NAILGUN_LOGS}/app.log"
EOL
}

prepare_server() {
    python manage.py syncdb > /dev/null
    python manage.py loaddefault > /dev/null
    if test -n $NAILGUN_DATA_FILE; then
        python manage.py loaddata $NAILGUN_DATA_FILE > /dev/null
    fi

    python manage.py run \
        --port=$NAILGUN_PORT \
        --config="$NAILGUN_CONFIG" \
        --fake-tasks \
        --fake-tasks-tick-count=80 \
        --fake-tasks-tick-interval=1 >> "$NAILGUN_LOGS/nailgun.log" 2>&1 &

    which curl >/dev/null 2>&1
    if test $? -ne 0; then
        echo "WARNING: Cannot check whether Nailgun is running bacause curl is not available."
        echo "         Waiting $NAILGUN_STARTUP_TIMEOUT in order to let it start properly."
        echo "         It's possible to increase waiting time by settings the required number of"
        echo "         seconds in NAILGUN_STARTUP_TIMEOUT environment variable."
        return 1
    fi

    local check_url="http://0.0.0.0:${NAILGUN_PORT}${NAILGUN_CHECK_URL}"

    local nailgun_status=1
    for i in $(seq 1 $NAILGUN_START_MAX_WAIT_TIME); do
        http_code=$(curl -s -w %{http_code} -o /dev/null ${check_url})
        if test "$http_code" = "200"; then
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
    psql -h 127.0.0.1 -U ${DB_ROOT} -c "DROP ROLE IF EXISTS ${NAILGUN_DB_USER}"
}

cleanup_database() {
    # requires pgpass
    echo "Dropping database ${NAILGUN_DB} if exists"
    psql -h 127.0.0.1 -U ${DB_ROOT} -c "DROP DATABASE IF EXISTS ${NAILGUN_DB}"
}

prepare_database_role() {
    # requires pgpass
    echo "Trying to find out if role ${NAILGUN_DB_USER} exists"
    local roles=$(psql -h 127.0.0.1 -U ${DB_ROOT} -t -c "SELECT 'HERE' from pg_roles where rolname='${NAILGUN_DB_USER}'")
    if [[ ${roles} == *HERE ]];then
        echo "Role ${NAILGUN_DB_USER} exists. Setting password ${NAILGUN_DB_PW}"
        psql -h 127.0.0.1 -U ${DB_ROOT} -c "ALTER ROLE ${NAILGUN_DB_USER} WITH SUPERUSER LOGIN PASSWORD '${NAILGUN_DB_PW}'"
    else
        echo "Creating role ${NAILGUN_DB_USER} with password ${NAILGUN_DB_PASSWD}"
        psql -h 127.0.0.1 -U ${DB_ROOT} -c "CREATE ROLE ${NAILGUN_DB_USER} WITH SUPERUSER LOGIN PASSWORD '${NAILGUN_DB_PW}'"
    fi
}

prepare_database() {
    # requires pgpass
    echo "Creating database ${NAILGUN_DB}"
    psql -h 127.0.0.1 -U ${DB_ROOT} -c "CREATE DATABASE ${NAILGUN_DB} OWNER ${NAILGUN_DB_USER}"
}

prepare_fuelclient() {
    if test "$FUELCLIENT_CLONE" = "yes" -a ! -d "$FUELCLIENT_ROOT"; then
        echo "Cloning $FUELCLIENT_REPO repo"
        git clone --depth 1 $FUELCLIENT_REPO "$FUELCLIENT_ROOT" || \
            { echo "Failed to clone fuelclient"; exit 1; }
    fi
    if test -d "$FUELCLIENT_ROOT"; then
        echo "Checking out $FUELCLIENT_COMMIT"
        pushd "$FUELCLIENT_ROOT" > /dev/null
        git checkout "$FUELCLIENT_COMMIT" || \
            { echo "Failed to checkout to $FUELCLIENT_COMMIT"; exit 1; }
        popd > /dev/null
    fi
}

cleanup_fuelclient() {
    if test -d "$FUELCLIENT_ROOT"; then
        pushd "$FUELCLIENT_ROOT" > /dev/null
        tox -e cleanup
        popd > /dev/null
    fi
}

test_fuelclient() {
    if test -d "$FUELCLIENT_ROOT"; then
        pushd "$FUELCLIENT_ROOT" > /dev/null
        tox -e functional
        popd > /dev/null
    fi
}

case $1 in
    prepare_nailgun_env)
        prepare_nailgun_env
        ;;
    cleanup_nailgun_env)
        cleanup_nailgun_env
        ;;
    prepare_nailgun_database)
        prepare_pgpass
        prepare_database_role
        prepare_database
        ;;
    cleanup_nailgun_database)
        prepare_pgpass
        cleanup_database
        cleanup_database_role
        cleanup_pgpass
        ;;
    cleanup_nailgun_server)
        cleanup_server
        ;;
    prepare_nailgun_server)
        prepare_server
        ;;
    cleanup_fuelclient)
        cleanup_fuelclient
        ;;
    prepare_fuelclient)
        prepare_fuelclient
        ;;
    test_fuelclient)
        test_fuelclient
        ;;
    *)
        echo "Not supported subcommand"
        exit 1
        ;;
esac
