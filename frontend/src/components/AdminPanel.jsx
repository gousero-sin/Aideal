import React, { useEffect, useState } from 'react';
import {
  BarChart3,
  Loader2,
  LockKeyhole,
  LogOut,
  ShieldCheck,
  WalletCards,
} from 'lucide-react';
import { PanelHero, PanelSkeleton } from './PanelShared';
import StatusPanel from './StatusPanel';
import UploadPanel from './UploadPanel';
import {
  buildProcessNotification,
  buildValidationNotification,
  createInitialAdminState,
  updateAdminFlowState,
} from './adminPanelModel';

const adminFlows = [
  { id: 'dre', label: 'DRE', icon: <BarChart3 size={16} aria-hidden="true" /> },
  { id: 'fluxo_caixa', label: 'Fluxo de Caixa', icon: <WalletCards size={16} aria-hidden="true" /> },
];

const emptyLogin = {
  username: '',
  password: '',
};

export default function AdminPanel({ apiBase, onNotify, onBusyChange }) {
  const [session, setSession] = useState({ authenticated: false, username: null });
  const [login, setLogin] = useState(emptyLogin);
  const [activeFlow, setActiveFlow] = useState('dre');
  const [flowState, setFlowState] = useState(createInitialAdminState);
  const [sessionLoading, setSessionLoading] = useState(true);
  const [loginBusy, setLoginBusy] = useState(false);
  const [logoutBusy, setLogoutBusy] = useState(false);
  const [operationBusy, setOperationBusy] = useState(false);
  const [error, setError] = useState(null);
  const activeState = flowState[activeFlow] || {};
  const busy = sessionLoading || logoutBusy || operationBusy;

  useEffect(() => {
    onBusyChange?.(busy);
  }, [busy, onBusyChange]);

  useEffect(() => () => onBusyChange?.(false), [onBusyChange]);

  useEffect(() => {
    let cancelled = false;

    const loadSession = async () => {
      setSessionLoading(true);
      try {
        const response = await fetch(`${apiBase}/admin/session`, {
          credentials: 'same-origin',
        });
        if (!response.ok) {
          throw new Error('Não foi possível verificar a sessão admin.');
        }
        const payload = await response.json();
        if (!cancelled) {
          setSession(payload);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message);
        }
      } finally {
        if (!cancelled) {
          setSessionLoading(false);
        }
      }
    };

    loadSession();
    return () => {
      cancelled = true;
    };
  }, [apiBase]);

  const handleLoginChange = (key, value) => {
    setLogin((prev) => ({ ...prev, [key]: value }));
  };

  const handleLogin = async (event) => {
    event.preventDefault();
    if (loginBusy) return;
    setLoginBusy(true);
    setError(null);

    try {
      const response = await fetch(`${apiBase}/admin/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify(login),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail?.detail || 'Credenciais inválidas.');
      }
      const payload = await response.json();
      setSession(payload);
      setLogin(emptyLogin);
      onNotify?.({ type: 'success', message: 'Admin Banco autenticado.' });
    } catch (err) {
      setError(err.message);
      onNotify?.({ type: 'error', message: err.message });
    } finally {
      setLoginBusy(false);
    }
  };

  const handleLogout = async () => {
    setLogoutBusy(true);
    setError(null);

    try {
      await fetch(`${apiBase}/admin/logout`, {
        method: 'POST',
        credentials: 'same-origin',
      });
    } finally {
      setSession({ authenticated: false, username: null });
      setFlowState(createInitialAdminState());
      setLogoutBusy(false);
      onNotify?.({ type: 'success', message: 'Sessão Admin Banco encerrada.' });
    }
  };

  const handleValidation = (result) => {
    setFlowState((prev) => updateAdminFlowState(prev, activeFlow, { validacao: result }));
    const notification = buildValidationNotification(activeFlow, result);
    if (notification) {
      onNotify?.(notification);
    }
  };

  const handleProcess = (result) => {
    setFlowState((prev) => updateAdminFlowState(prev, activeFlow, { processamento: result }));
    const notification = buildProcessNotification(activeFlow, result);
    if (notification) {
      onNotify?.(notification);
    }
  };

  if (sessionLoading) {
    return (
      <section className="aideal-panel-page">
        <PanelSkeleton />
      </section>
    );
  }

  if (!session.authenticated) {
    return (
      <section className="aideal-panel-page aideal-admin-page">
        <PanelHero
          kicker="Admin Banco"
          title="Acesso administrativo"
          description="Operações de banco e geração de arquivos ficam isoladas nesta área protegida."
          meta={[
            { label: 'Sessão', value: 'Bloqueada' },
            { label: 'Escopo', value: 'DRE e Fluxo' },
          ]}
          actions={(
            <span className="aideal-context-chip">
              <LockKeyhole size={15} aria-hidden="true" />
              Login obrigatório
            </span>
          )}
        />

        <form className="aideal-admin-login aideal-card" onSubmit={handleLogin}>
          <div className="aideal-card-heading">
            <span className="aideal-card-icon">
              <ShieldCheck size={20} aria-hidden="true" />
            </span>
            <div>
              <h2>Entrar no Admin Banco</h2>
              <p>Use a credencial administrativa configurada no servidor.</p>
            </div>
          </div>

          <label className="aideal-field">
            Usuário
            <input
              type="text"
              autoComplete="username"
              value={login.username}
              onChange={(event) => handleLoginChange('username', event.target.value)}
            />
          </label>
          <label className="aideal-field">
            Senha
            <input
              type="password"
              autoComplete="current-password"
              value={login.password}
              onChange={(event) => handleLoginChange('password', event.target.value)}
            />
          </label>

          {error && <p className="aideal-inline-error">{error}</p>}

          <button
            className="aideal-action aideal-action-primary"
            type="submit"
            disabled={!login.username || !login.password}
          >
            <LockKeyhole size={16} aria-hidden="true" />
            <span>Entrar</span>
          </button>
        </form>
      </section>
    );
  }

  const statusSlot =
    activeState.validacao || activeState.processamento ? (
      <StatusPanel
        validacao={activeState.validacao}
        processamento={activeState.processamento}
        fluxo={activeFlow}
      />
    ) : null;

  return (
    <section className="aideal-panel-page aideal-admin-page">
      <header className="aideal-admin-topbar">
        <div className="aideal-admin-topbar-id">
          <span className="aideal-admin-topbar-icon">
            <ShieldCheck size={18} aria-hidden="true" />
          </span>
          <div>
            <strong>Admin Banco</strong>
            <p>Operações protegidas · {operationBusy ? 'Processando' : 'Pronto'}</p>
          </div>
        </div>

        <div className="aideal-admin-flow-tabs" role="tablist" aria-label="Fluxo administrativo">
          {adminFlows.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`aideal-admin-flow-tab ${activeFlow === item.id ? 'is-active' : ''}`}
              onClick={() => setActiveFlow(item.id)}
              role="tab"
              aria-selected={activeFlow === item.id}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          ))}
        </div>

        <div className="aideal-admin-topbar-session">
          <span className="aideal-admin-session-user">
            <ShieldCheck size={14} aria-hidden="true" />
            {session.username || 'Admin'}
          </span>
          <button
            className="aideal-action aideal-action-secondary"
            type="button"
            onClick={handleLogout}
            disabled={logoutBusy}
          >
            {logoutBusy ? <Loader2 size={16} aria-hidden="true" /> : <LogOut size={16} aria-hidden="true" />}
            <span>{logoutBusy ? 'Saindo...' : 'Sair'}</span>
          </button>
        </div>
      </header>

      <UploadPanel
        key={activeFlow}
        fluxo={activeFlow}
        apiBase={apiBase}
        onValidation={handleValidation}
        onProcess={handleProcess}
        processamento={activeState.processamento}
        validacao={activeState.validacao}
        onBusyChange={setOperationBusy}
        statusSlot={statusSlot}
      />
    </section>
  );
}
