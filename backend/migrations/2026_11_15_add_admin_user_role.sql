-- Add the ADMIN role used by application-level authorization.
-- Safe to run on an existing CargoPilot database; existing role values remain valid.
ALTER TABLE users
MODIFY COLUMN role ENUM('ADMIN', 'MANAGER', 'OFFICER')
NOT NULL DEFAULT 'OFFICER';
