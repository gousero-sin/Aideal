-- ORC-ATU-033: cada alteração do catálogo passa a ter versão e vigência próprias.
-- A tabela orcamento_catalogo continua sendo o ponteiro compatível para a versão atual.
CREATE TABLE orcamento_catalogo_historico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    versao INTEGER NOT NULL UNIQUE CHECK (versao > 0),
    payload TEXT NOT NULL,
    responsavel_user_id TEXT NOT NULL,
    vigente_desde TEXT NOT NULL,
    vigente_ate TEXT,
    created_at TEXT NOT NULL,
    CHECK (vigente_ate IS NULL OR vigente_ate >= vigente_desde)
);

INSERT INTO orcamento_catalogo_historico (
    versao, payload, responsavel_user_id, vigente_desde, vigente_ate, created_at
)
SELECT 1, payload, responsavel_user_id, updated_at, NULL, updated_at
FROM orcamento_catalogo
WHERE id = 1;

-- Só pode existir uma versão vigente por vez. O índice em uma expressão constante
-- transforma todas as linhas abertas no mesmo valor lógico.
CREATE UNIQUE INDEX idx_orcamento_catalogo_historico_vigente
    ON orcamento_catalogo_historico ((1))
    WHERE vigente_ate IS NULL;

CREATE INDEX idx_orcamento_catalogo_historico_vigencia
    ON orcamento_catalogo_historico (vigente_desde, vigente_ate);
