-- Runs automatically on first container start (docker-entrypoint-initdb.d).
-- The main "procurement" database is created by POSTGRES_DB already;
-- this adds the second one tests run against.
CREATE DATABASE procurement_test;
GRANT ALL PRIVILEGES ON DATABASE procurement_test TO procurement;
