-- Migration: V3__create_fluxo_caixa_tables.sql
-- Persistência mensal do Fluxo de Caixa.

CREATE TABLE IF NOT EXISTS fluxo_uploads (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    arquivo_nome TEXT NOT NULL,
    arquivo_sha256 TEXT NOT NULL,
    competencia_ano INTEGER NOT NULL,
    competencia_mes INTEGER NOT NULL,
    banco TEXT,
    status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'error')),
    total_linhas INTEGER NOT NULL DEFAULT 0,
    linhas_validas INTEGER NOT NULL DEFAULT 0,
    linhas_rejeitadas INTEGER NOT NULL DEFAULT 0,
    observacao TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_fluxo_uploads_sha256_competencia
ON fluxo_uploads (arquivo_sha256, competencia_ano, competencia_mes);

CREATE INDEX IF NOT EXISTS idx_fluxo_uploads_competencia
ON fluxo_uploads (competencia_ano, competencia_mes);

CREATE TABLE IF NOT EXISTS fluxo_movimentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    upload_id TEXT NOT NULL,
    competencia_ano INTEGER NOT NULL,
    competencia_mes INTEGER NOT NULL,
    data_movimento TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('credito', 'debito', 'transferencia')),
    descricao TEXT NOT NULL,
    valor REAL NOT NULL DEFAULT 0,
    saldo REAL,
    classificacao TEXT,
    conta_gerencial TEXT,
    banco_origem TEXT NOT NULL,
    arquivo_origem TEXT,
    linha_origem INTEGER,
    aba_origem TEXT,
    hash_linha TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (upload_id) REFERENCES fluxo_uploads(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_fluxo_movimentos_periodo
ON fluxo_movimentos (competencia_ano, competencia_mes);

CREATE INDEX IF NOT EXISTS idx_fluxo_movimentos_data
ON fluxo_movimentos (data_movimento);

CREATE INDEX IF NOT EXISTS idx_fluxo_movimentos_banco
ON fluxo_movimentos (banco_origem);

CREATE INDEX IF NOT EXISTS idx_fluxo_movimentos_upload
ON fluxo_movimentos (upload_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_fluxo_movimentos_hash_linha_upload
ON fluxo_movimentos (upload_id, hash_linha);
