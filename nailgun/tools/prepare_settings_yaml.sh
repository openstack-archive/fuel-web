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
LOGS:
  - id: receiverd
    name: "RPC consumer"
    remote: False
    multiline: True
    path: "${NAILGUN_LOGS}/receiverd.log"
    log_format_id: python
    regexp: '^(?P<date>\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})(?P<msecs>\.\d{3})?\s(?P<level>[A-Z]+)\s(?P<text>.*)$'
    date_format: '%Y-%m-%d %H:%M:%S'
    levels:
      - DEBUG
      - INFO
      - WARNING
      - ERROR
      - CRITICAL
  - id: assassin
    name: "Assassin"
    remote: False
    multiline: True
    path: "${NAILGUN_LOGS}/assassind.log"
    log_format_id: python
    regexp: '^(?P<date>\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})(?P<msecs>\.\d{3})?\s(?P<level>[A-Z]+)\s(?P<text>.*)$'
    date_format: '%Y-%m-%d %H:%M:%S'
    levels:
      - DEBUG
      - INFO
      - WARNING
      - ERROR
      - CRITICAL
EOL
