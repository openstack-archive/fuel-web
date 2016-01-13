#!/bin/sh

cat > ${NAILGUN_CONFIG} <<EOL
DEVELOPMENT: 1
STATIC_DIR: ${NAILGUN_STATIC}
TEMPLATE_DIR: ${NAILGUN_TEMPLATES}
DATABASE:
  name: "${NAILGUN_DB}"
  engine: "postgresql"
  host: "localhost"
  port: "5432"
  user: "${NAILGUN_DB_USER}"
  passwd: "${NAILGUN_DB_PW}"
API_LOG: ${NAILGUN_LOGS}/api.log
APP_LOG: ${NAILGUN_LOGS}/app.log
RPC_CONSUMER_LOG_PATH: "${NAILGUN_LOGS}/receiverd.log"
ASSASSIN_LOG_PATH: "${NAILGUN_LOGS}/assassind.log"
EOL
