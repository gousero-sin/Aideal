-- Migration: V5__create_dre_indicadores_manuais.sql
-- Persistencia mensal de indicadores DRE informados pela ADM.

CREATE TABLE IF NOT EXISTS dre_indicadores_manuais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competencia_ano INTEGER NOT NULL CHECK (competencia_ano BETWEEN 2000 AND 2100),
    competencia_mes INTEGER NOT NULL CHECK (competencia_mes BETWEEN 1 AND 12),
    contas_pagar REAL NOT NULL DEFAULT 0 CHECK (contas_pagar >= 0),
    contas_receber REAL NOT NULL DEFAULT 0 CHECK (contas_receber >= 0),
    total_impostos_retidos_acima_meta REAL NOT NULL DEFAULT 0
        CHECK (total_impostos_retidos_acima_meta >= 0),
    total_impostos_retidos REAL NOT NULL DEFAULT 0 CHECK (total_impostos_retidos >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (competencia_ano, competencia_mes)
);

CREATE INDEX IF NOT EXISTS idx_dre_indicadores_manuais_competencia
ON dre_indicadores_manuais (competencia_ano, competencia_mes);
