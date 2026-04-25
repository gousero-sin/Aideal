-- Migration: V2__dedupe_upload_by_hash_and_competencia.sql
-- Ajusta deduplicação de uploads DRE para escopo por competência.
-- Evita falso "already_processed" em outro mês/ano com mesmo arquivo.

DROP INDEX IF EXISTS idx_dre_uploads_sha256;

CREATE UNIQUE INDEX IF NOT EXISTS idx_dre_uploads_sha256_competencia
ON dre_uploads (arquivo_sha256, competencia_ano, competencia_mes);
