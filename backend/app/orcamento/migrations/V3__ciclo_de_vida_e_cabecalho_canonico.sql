-- Alinha o módulo à especificação do vault (Orçamento.md e Orc_Proposta_Técnica.md):
--
-- 1. O ciclo de vida do ORÇAMENTO é Rascunho -> Em revisão -> Pronto para proposta
--    -> Emitido -> Inativo. Os estados 'em_elaboracao'/'pronta_para_emissao'
--    pertencem à PROPOSTA TÉCNICA, não ao orçamento; foram trocados por engano.
-- 2. A validade comercial conta a partir da EMISSÃO, não da criação, e o último
--    dia integra o período válido. Por isso valido_ate vira DATE e passa a ser
--    nulo enquanto a revisão não for emitida.
-- 3. O cabeçalho canônico exige campos que estavam ausentes.
--
-- SQLite não altera CHECK constraints, então a tabela é reconstruída.

CREATE TABLE orcamento_revisoes_nova (
    id TEXT PRIMARY KEY,
    orcamento_id TEXT NOT NULL REFERENCES orcamentos(id) ON DELETE RESTRICT,
    numero INTEGER NOT NULL,
    situacao TEXT NOT NULL CHECK (
        situacao IN ('rascunho', 'em_revisao', 'pronto_para_proposta', 'emitido', 'inativo')
    ),
    escopo TEXT NOT NULL DEFAULT '',
    modalidade TEXT CHECK (modalidade IS NULL OR modalidade IN ('HH', 'Spot')),
    regiao TEXT,
    prazo_execucao_dias INTEGER
        CHECK (prazo_execucao_dias IS NULL OR prazo_execucao_dias > 0),
    saldo_mao_de_obra REAL
        CHECK (saldo_mao_de_obra IS NULL OR saldo_mao_de_obra >= 0),
    dados_contratante TEXT,
    mobilizacao TEXT,
    desmobilizacao TEXT,
    area_unidade_base TEXT,
    regime_tributario TEXT,
    versao_regras TEXT NOT NULL,
    autor_user_id TEXT NOT NULL,
    motivo TEXT,
    emitido_em TEXT,
    valido_ate TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (orcamento_id, numero),
    -- Emissão e validade andam juntas: uma não existe sem a outra.
    CHECK (
        (emitido_em IS NULL AND valido_ate IS NULL)
        OR (emitido_em IS NOT NULL AND valido_ate IS NOT NULL)
    )
);

INSERT INTO orcamento_revisoes_nova (
    id, orcamento_id, numero, situacao, escopo, modalidade, regiao,
    prazo_execucao_dias, saldo_mao_de_obra, versao_regras, autor_user_id,
    motivo, emitido_em, valido_ate, created_at
)
SELECT
    id, orcamento_id, numero,
    CASE situacao WHEN 'em_elaboracao' THEN 'rascunho' ELSE situacao END,
    escopo,
    CASE WHEN modalidade IN ('HH', 'Spot') THEN modalidade ELSE NULL END,
    regiao, prazo_execucao_dias, saldo_mao_de_obra, versao_regras,
    autor_user_id, motivo, NULL, NULL, created_at
FROM orcamento_revisoes;

-- A trilha é reconstruída antes de remover a tabela pai antiga. Sua FK aponta
-- para a tabela pai nova, preservando upgrades que já possuem eventos.
CREATE TABLE orcamento_situacao_eventos_nova (
    id TEXT PRIMARY KEY,
    revisao_id TEXT NOT NULL REFERENCES orcamento_revisoes_nova(id) ON DELETE RESTRICT,
    situacao TEXT NOT NULL CHECK (
        situacao IN ('rascunho', 'em_revisao', 'pronto_para_proposta', 'emitido', 'inativo')
    ),
    motivo TEXT NOT NULL,
    responsavel_user_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);

INSERT INTO orcamento_situacao_eventos_nova (
    id, revisao_id, situacao, motivo, responsavel_user_id, created_at
)
SELECT
    id, revisao_id,
    CASE situacao WHEN 'em_elaboracao' THEN 'rascunho' ELSE situacao END,
    motivo, responsavel_user_id, created_at
FROM orcamento_situacao_eventos;

DROP TABLE orcamento_situacao_eventos;

DROP TABLE orcamento_revisoes;

ALTER TABLE orcamento_revisoes_nova RENAME TO orcamento_revisoes;

ALTER TABLE orcamento_situacao_eventos_nova RENAME TO orcamento_situacao_eventos;

CREATE INDEX idx_orcamento_revisoes_orcamento_id ON orcamento_revisoes(orcamento_id);

CREATE INDEX idx_orcamento_situacao_eventos_revisao_id
    ON orcamento_situacao_eventos(revisao_id);
