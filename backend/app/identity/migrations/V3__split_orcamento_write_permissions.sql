-- Leitura do Orçamento não concede criação, edição nem transição de situação.
INSERT INTO permissions (code, position, description) VALUES
    ('orcamento.edit', 51, 'Criar e editar orçamentos e revisões'),
    ('orcamento.transition', 52, 'Alterar a situação de revisões de orçamento');

-- O proprietário do sistema mantém administração total após o upgrade.
-- Usuários comuns com apenas orcamento.view permanecem somente leitura.
INSERT OR IGNORE INTO user_permissions (
    user_id, permission_code, granted_at, granted_by_user_id
)
SELECT id, 'orcamento.edit', CURRENT_TIMESTAMP, id
FROM users
WHERE is_system_owner = 1;

INSERT OR IGNORE INTO user_permissions (
    user_id, permission_code, granted_at, granted_by_user_id
)
SELECT id, 'orcamento.transition', CURRENT_TIMESTAMP, id
FROM users
WHERE is_system_owner = 1;
