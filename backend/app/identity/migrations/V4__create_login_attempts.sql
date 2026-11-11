-- Tentativas de login ficam no banco para que todos os workers do uvicorn
-- compartilhem o mesmo limite. A chave é um hash SHA-256 de IP + usuário
-- normalizado; o horário é epoch em segundos (relógio de parede, comum aos
-- processos).
CREATE TABLE login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_key TEXT NOT NULL,
    attempted_at REAL NOT NULL
);

CREATE INDEX idx_login_attempts_key_time ON login_attempts(attempt_key, attempted_at);
CREATE INDEX idx_login_attempts_time ON login_attempts(attempted_at);
