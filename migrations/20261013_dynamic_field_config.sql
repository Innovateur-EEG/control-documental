-- Migration: add metadata configuration to dynamic fields.
-- Run once against the application's PostgreSQL database before deploying this commit.
ALTER TABLE configuracion_campos
    ADD COLUMN IF NOT EXISTS configuracion_json JSONB NOT NULL DEFAULT '{}'::jsonb;
