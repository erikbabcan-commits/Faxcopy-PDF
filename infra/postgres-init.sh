#!/bin/sh
# Fresh disposable/local databases only. Existing volumes require owner-reviewed provisioning.
set -eu
: "${MIGRATION_PASSWORD:?Set a generated migration password}"
: "${RUNTIME_PASSWORD:?Set a generated runtime password}"
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=ON_ERROR_STOP=1 \
  --set=migration_password="$MIGRATION_PASSWORD" --set=runtime_password="$RUNTIME_PASSWORD" <<'SQL'
CREATE ROLE presspilot_migrator LOGIN PASSWORD :'migration_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE presspilot_runtime LOGIN PASSWORD :'runtime_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
REVOKE ALL ON DATABASE presspilot FROM PUBLIC;
GRANT CONNECT ON DATABASE presspilot TO presspilot_migrator, presspilot_runtime;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO presspilot_migrator;
GRANT USAGE ON SCHEMA public TO presspilot_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE presspilot_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO presspilot_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE presspilot_migrator IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO presspilot_runtime;
SQL
