import React, { useState } from 'react';
import { Loader2, LockKeyhole, ShieldCheck } from 'lucide-react';
import { useAuth } from './AuthContext';
import '../styles/access-control.css';

const EMPTY_CREDENTIALS = Object.freeze({ username: '', password: '' });

export default function LoginScreen() {
  const { login, status, error: sessionError } = useAuth();
  const [credentials, setCredentials] = useState({ ...EMPTY_CREDENTIALS });
  const [submitError, setSubmitError] = useState(null);
  const busy = status === 'loading';

  const updateCredential = (field, value) => {
    setCredentials((current) => ({ ...current, [field]: value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (busy || !credentials.username.trim() || !credentials.password) return;
    setSubmitError(null);
    try {
      await login({
        username: credentials.username.trim(),
        password: credentials.password,
      });
      setCredentials({ ...EMPTY_CREDENTIALS });
    } catch (requestError) {
      setSubmitError(requestError.message);
    }
  };

  return (
    <main className="access-login-shell">
      <section className="access-login-card" aria-labelledby="access-login-title">
        <div className="access-login-brand">
          <img src="/logo-aideal-peq-2.png" alt="AIDEAL Engenharia de Superficie" />
          <span><ShieldCheck size={18} aria-hidden="true" /> Acesso protegido</span>
        </div>

        <div className="access-login-heading">
          <LockKeyhole size={28} aria-hidden="true" />
          <div>
            <h1 id="access-login-title">Entrar no GoFlow</h1>
            <p>Use o usuario criado pelo administrador para acessar seus paineis.</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} noValidate>
          <label className="access-field">
            <span>Usuario</span>
            <input
              name="username"
              type="text"
              autoComplete="username"
              value={credentials.username}
              onChange={(event) => updateCredential('username', event.target.value)}
              required
              autoFocus
            />
          </label>

          <label className="access-field">
            <span>Senha</span>
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              value={credentials.password}
              onChange={(event) => updateCredential('password', event.target.value)}
              required
            />
          </label>

          {(submitError || sessionError) && (
            <p className="access-feedback access-feedback-error" role="alert">
              {submitError || sessionError}
            </p>
          )}

          <button
            className="access-primary-button"
            type="submit"
            disabled={busy || !credentials.username.trim() || !credentials.password}
          >
            {busy ? <Loader2 className="access-spin" size={17} aria-hidden="true" /> : <LockKeyhole size={17} aria-hidden="true" />}
            {busy ? 'Entrando...' : 'Entrar'}
          </button>
        </form>
      </section>
    </main>
  );
}
