-- The role the API connects as. It must NOT be a superuser and must NOT have BYPASSRLS,
-- otherwise row-level security would be ignored. Migrations run as a different (owner) role.
-- Local development credentials only; real environments use their own role and secret.
-- Idempotent: safe to run repeatedly. Run inside each application database.
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'factory_app') THEN
    CREATE ROLE factory_app LOGIN PASSWORD 'factory_app'
      NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
  END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO factory_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO factory_app;
-- Tables created later by migrations (run as "factory") are granted automatically.
ALTER DEFAULT PRIVILEGES FOR ROLE factory IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO factory_app;
