CREATE TABLE orcamentos (
    id TEXT PRIMARY KEY,
    codigo TEXT NOT NULL,
    codigo_key TEXT NOT NULL UNIQUE,
    contratante TEXT NOT NULL,
    criado_por_user_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE orcamento_revisoes (
    id TEXT PRIMARY KEY,
    orcamento_id TEXT NOT NULL REFERENCES orcamentos(id) ON DELETE RESTRICT,
    numero INTEGER NOT NULL,
    situacao TEXT NOT NULL
        CHECK (situacao IN ('em_elaboracao', 'pronto_para_proposta', 'inativo')),
    escopo TEXT NOT NULL DEFAULT '',
    modalidade TEXT,
    regiao TEXT,
    prazo_execucao_dias INTEGER
        CHECK (prazo_execucao_dias IS NULL OR prazo_execucao_dias > 0),
    saldo_mao_de_obra REAL
        CHECK (saldo_mao_de_obra IS NULL OR saldo_mao_de_obra >= 0),
    versao_regras TEXT NOT NULL,
    autor_user_id TEXT NOT NULL,
    motivo TEXT,
    valido_ate TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (orcamento_id, numero)
);

CREATE INDEX idx_orcamento_revisoes_orcamento_id ON orcamento_revisoes(orcamento_id);

CREATE TABLE orcamento_situacao_eventos (
    id TEXT PRIMARY KEY,
    revisao_id TEXT NOT NULL REFERENCES orcamento_revisoes(id) ON DELETE RESTRICT,
    situacao TEXT NOT NULL
        CHECK (situacao IN ('em_elaboracao', 'pronto_para_proposta', 'inativo')),
    motivo TEXT NOT NULL,
    responsavel_user_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_orcamento_situacao_eventos_revisao_id
    ON orcamento_situacao_eventos(revisao_id);
