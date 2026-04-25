-- Migration: V1__create_dre_tables.sql
-- Criação das tabelas de persistência para DRE Cumulativo
-- Data: 02/04/2026

-- Tabela de controle de uploads
CREATE TABLE IF NOT EXISTS dre_uploads (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    arquivo_nome TEXT NOT NULL,
    arquivo_sha256 TEXT NOT NULL,
    competencia_ano INTEGER NOT NULL,
    competencia_mes INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'error')),
    total_linhas INTEGER NOT NULL DEFAULT 0,
    linhas_validas INTEGER NOT NULL DEFAULT 0,
    linhas_rejeitadas INTEGER NOT NULL DEFAULT 0,
    observacao TEXT
);

-- Índice único para evitar upload duplicado do mesmo arquivo (por hash)
CREATE UNIQUE INDEX IF NOT EXISTS idx_dre_uploads_sha256
ON dre_uploads (arquivo_sha256);

-- Índice para busca por competência
CREATE INDEX IF NOT EXISTS idx_dre_uploads_competencia
ON dre_uploads (competencia_ano, competencia_mes);

-- Tabela de lançamentos financeiros
CREATE TABLE IF NOT EXISTS dre_lancamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    upload_id TEXT NOT NULL,
    competencia_ano INTEGER NOT NULL,
    competencia_mes INTEGER NOT NULL,
    data_lancamento TEXT NOT NULL,
    historico TEXT NOT NULL,
    valor_bruto REAL NOT NULL DEFAULT 0,
    credito REAL NOT NULL DEFAULT 0,
    debito REAL NOT NULL DEFAULT 0,
    natureza_raw TEXT,
    natureza_norm TEXT,
    centro_custo TEXT,
    rubrica TEXT,
    conta_pai TEXT,
    linha_origem INTEGER,
    hash_linha TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (upload_id) REFERENCES dre_uploads(id) ON DELETE CASCADE
);

-- Índice para consultas por período (YTD - Year to Date)
CREATE INDEX IF NOT EXISTS idx_dre_lancamentos_periodo
ON dre_lancamentos (competencia_ano, competencia_mes);

-- Índice para agregação por conta pai e mês (usado na aba APOIO)
CREATE INDEX IF NOT EXISTS idx_dre_lancamentos_conta_mes
ON dre_lancamentos (conta_pai, competencia_ano, competencia_mes);

-- Índice para busca por upload (deleção em cascata)
CREATE INDEX IF NOT EXISTS idx_dre_lancamentos_upload
ON dre_lancamentos (upload_id);

-- Índice único para evitar duplicidade de linha no mesmo upload
CREATE UNIQUE INDEX IF NOT EXISTS idx_dre_lancamentos_hash_linha_upload
ON dre_lancamentos (upload_id, hash_linha);

-- Índice para consultas por centro de custo/obra
CREATE INDEX IF NOT EXISTS idx_dre_lancamentos_centro_custo
ON dre_lancamentos (centro_custo);

-- Índice para consultas por natureza
CREATE INDEX IF NOT EXISTS idx_dre_lancamentos_natureza
ON dre_lancamentos (natureza_norm);

-- View para resumo por competência (útil para auditoria)
CREATE VIEW IF NOT EXISTS v_dre_resumo_competencia AS
SELECT 
    competencia_ano,
    competencia_mes,
    COUNT(*) as total_lancamentos,
    SUM(credito) as total_credito,
    SUM(debito) as total_debito,
    SUM(credito - debito) as saldo_liquido,
    COUNT(DISTINCT conta_pai) as total_contas_pai,
    COUNT(DISTINCT centro_custo) as total_centros_custo
FROM dre_lancamentos
GROUP BY competencia_ano, competencia_mes;

-- View para acumulado YTD até determinado mês
CREATE VIEW IF NOT EXISTS v_dre_acumulado_ytd AS
SELECT 
    competencia_ano,
    competencia_mes,
    conta_pai,
    centro_custo,
    SUM(credito) as credito_acumulado,
    SUM(debito) as debito_acumulado,
    SUM(credito - debito) as saldo_acumulado,
    COUNT(*) as quantidade_lancamentos
FROM dre_lancamentos
GROUP BY competencia_ano, competencia_mes, conta_pai, centro_custo;
