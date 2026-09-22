CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    username_key TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    is_system_owner INTEGER NOT NULL DEFAULT 0 CHECK (is_system_owner IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE permissions (
    code TEXT PRIMARY KEY,
    position INTEGER NOT NULL UNIQUE,
    description TEXT NOT NULL
);

INSERT INTO permissions (code, position, description) VALUES
    ('dre.view', 10, 'Visualizar o painel DRE'),
    ('fluxo.view', 20, 'Visualizar o painel de Fluxo de Caixa'),
    ('admin_banco.use', 30, 'Executar operações administrativas de banco'),
    ('users.manage', 40, 'Gerenciar usuários e permissões'),
    ('orcamento.view', 50, 'Visualizar o aplicativo de Orçamento');

CREATE TABLE user_permissions (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    permission_code TEXT NOT NULL REFERENCES permissions(code) ON DELETE RESTRICT,
    granted_at TEXT NOT NULL,
    granted_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    PRIMARY KEY (user_id, permission_code)
);

CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    csrf_token_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    last_used_at TEXT,
    revoked_at TEXT,
    revoked_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);

CREATE TABLE audit_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    actor_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    target_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX idx_audit_events_created_at ON audit_events(created_at);
