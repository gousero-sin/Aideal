-- Migration: V6__create_fluxo_indicadores_manuais.sql
-- Persistencia anual de indicadores do Fluxo de Caixa informados pela ADM.

CREATE TABLE IF NOT EXISTS fluxo_indicadores_manuais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competencia_ano INTEGER NOT NULL CHECK (competencia_ano BETWEEN 2000 AND 2100),
    saldo_ano_anterior REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (competencia_ano)
);

CREATE INDEX IF NOT EXISTS idx_fluxo_indicadores_manuais_ano
ON fluxo_indicadores_manuais (competencia_ano);
