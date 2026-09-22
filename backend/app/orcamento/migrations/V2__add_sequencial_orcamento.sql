-- O código do orçamento passa a ser derivado de um sequencial gerado pelo sistema,
-- em vez de informado pelo usuário. Registros anteriores herdam a ordem de inserção.
ALTER TABLE orcamentos ADD COLUMN sequencial INTEGER;

UPDATE orcamentos SET sequencial = rowid WHERE sequencial IS NULL;

CREATE UNIQUE INDEX idx_orcamentos_sequencial ON orcamentos(sequencial);
