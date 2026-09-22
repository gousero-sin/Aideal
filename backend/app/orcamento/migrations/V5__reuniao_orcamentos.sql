-- Preserve os números e snapshots já emitidos. Novos orçamentos começam em R0.
CREATE TABLE orcamento_revisoes_nova (
 id TEXT PRIMARY KEY,
 orcamento_id TEXT NOT NULL REFERENCES orcamentos(id) ON DELETE RESTRICT,
 numero INTEGER NOT NULL CHECK(numero >= 0),
 situacao TEXT NOT NULL CHECK(situacao IN ('rascunho','em_revisao','pronto_para_proposta','emitido','inativo')),
 escopo TEXT NOT NULL DEFAULT '',
 modalidade TEXT CHECK(modalidade IS NULL OR modalidade IN ('HH','Spot','Rotina','m²')),
 regiao TEXT, prazo_execucao_dias INTEGER CHECK(prazo_execucao_dias IS NULL OR prazo_execucao_dias > 0),
 saldo_mao_de_obra REAL CHECK(saldo_mao_de_obra IS NULL OR saldo_mao_de_obra >= 0),
 dados_contratante TEXT, mobilizacao TEXT, desmobilizacao TEXT, area_unidade_base TEXT,
 regime_tributario TEXT, versao_regras TEXT NOT NULL, autor_user_id TEXT NOT NULL,
 motivo TEXT, emitido_em TEXT, valido_ate TEXT, created_at TEXT NOT NULL,
 dfp_payload TEXT NOT NULL DEFAULT '{}',
 UNIQUE(orcamento_id,numero),
 CHECK((emitido_em IS NULL AND valido_ate IS NULL) OR (emitido_em IS NOT NULL AND valido_ate IS NOT NULL))
);
INSERT INTO orcamento_revisoes_nova SELECT * FROM orcamento_revisoes;
CREATE TABLE orcamento_situacao_eventos_nova (
 id TEXT PRIMARY KEY,
 revisao_id TEXT NOT NULL REFERENCES orcamento_revisoes_nova(id) ON DELETE RESTRICT,
 situacao TEXT NOT NULL CHECK(situacao IN ('rascunho','em_revisao','pronto_para_proposta','emitido','inativo')),
 motivo TEXT NOT NULL,responsavel_user_id TEXT NOT NULL,created_at TEXT NOT NULL
);
INSERT INTO orcamento_situacao_eventos_nova SELECT * FROM orcamento_situacao_eventos;
DROP TABLE orcamento_situacao_eventos;
DROP TABLE orcamento_revisoes;
ALTER TABLE orcamento_revisoes_nova RENAME TO orcamento_revisoes;
ALTER TABLE orcamento_situacao_eventos_nova RENAME TO orcamento_situacao_eventos;
CREATE INDEX idx_orcamento_revisoes_orcamento_id ON orcamento_revisoes(orcamento_id);
CREATE INDEX idx_orcamento_situacao_eventos_revisao_id ON orcamento_situacao_eventos(revisao_id);
CREATE TABLE orcamento_edicao_eventos (
 id TEXT PRIMARY KEY,revisao_id TEXT NOT NULL REFERENCES orcamento_revisoes(id),
 tipo TEXT NOT NULL,responsavel_user_id TEXT NOT NULL,
 antes TEXT NOT NULL,depois TEXT NOT NULL,created_at TEXT NOT NULL
);
CREATE INDEX idx_orcamento_edicao_revisao ON orcamento_edicao_eventos(revisao_id);
CREATE TABLE orcamento_catalogo (
 id INTEGER PRIMARY KEY CHECK(id=1),payload TEXT NOT NULL,
 responsavel_user_id TEXT NOT NULL,updated_at TEXT NOT NULL
);
