-- Migration: V4__create_contas_gerenciais.sql
-- Catalogo canonico de nomes por codigo de conta gerencial.

CREATE TABLE IF NOT EXISTS contas_gerenciais (
    codigo TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    rotulo TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_contas_gerenciais_nome
ON contas_gerenciais (nome);
