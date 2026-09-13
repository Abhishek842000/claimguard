-- Enabled on every fresh ClaimGuard Postgres volume.
-- The pgvector image ships the extension; this makes it available in the app DB.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
