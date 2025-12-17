-- Database initialization for Server Agent vNext
-- This script is executed when the Postgres container starts for the first time

\echo 'Initializing server-agent database...'

-- The database and user should be created by POSTGRES_DB and POSTGRES_USER env vars
-- This script runs after those are created

\echo 'Running schema creation...'
\i /docker-entrypoint-initdb.d/schema.sql

\echo 'Database initialization complete!'
