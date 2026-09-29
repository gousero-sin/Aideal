import React, { useEffect, useMemo, useRef, useState } from 'react';
import { BarChart3, Calculator, Database, Loader2, Users, WalletCards } from 'lucide-react';
import { useLiquidLoaderController } from 'goflow-core';
import AidealPartnershipLoader from './components/AidealPartnershipLoader';
import AccessManagementPanel from './components/AccessManagementPanel';
import AdminPanel from './components/AdminPanel';
import AppSidebar from './components/AppSidebar';
import PainelDRE from './components/PainelDRE';
import OrcamentoPanel from './components/OrcamentoPanel';
import PainelFluxoCaixa from './components/PainelFluxoCaixa';
import { filterAccessibleModules } from './components/accessControlModel';
import { LoginScreen, PasswordChangeScreen, useAuth } from './auth';
import './styles/access-control.css';

const API_BASE = '/api';

const VIEW_META = Object.freeze({
  dre: {
    title: 'Painel DRE',
    subtitle: 'Resultado por obra e centro de custos',
    icon: BarChart3,
  },
  fluxo_caixa: {
    title: 'Painel Fluxo de Caixa',
    subtitle: 'Entradas, saídas, bancos e classificações',
    icon: WalletCards,
  },
  admin_banco: {
    title: 'Admin Banco',
    subtitle: 'Operações protegidas de banco',
    icon: Database,
  },
  usuarios: {
    title: 'Controle de Acessos',
    subtitle: 'Usuários, painéis liberados e permissões',
    icon: Users,
  },
  orcamento: {
    title: 'Orçamento',
    subtitle: 'Orçamentos, revisões e situação documental',
    icon: Calculator,
  },
});

const getRequestedView = () => {
  if (typeof window === 'undefined') return null;
  const params = new URLSearchParams(window.location.search);
  const candidate = params.get('painel') || params.get('view');
  return VIEW_META[candidate] ? candidate : null;
};

export default function App() {
  const auth = useAuth();
  const [activeView, setActiveView] = useState(getRequestedView);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [notification, setNotification] = useState(null);
  const [busy, setBusy] = useState(false);
  const loader = useLiquidLoaderController({
    intervalMs: 3200,
    minVisibleMs: 1400,
    exitMs: 420,
  });
  const loaderVisibleRef = useRef(false);
  const visibleModules = useMemo(
    () => filterAccessibleModules(auth.modules, auth.permissions),
    [auth.modules, auth.permissions],
  );
  const visibleIds = useMemo(
    () => visibleModules.map(({ id }) => id),
    [visibleModules],
  );
  const canRenderActiveView = activeView !== null && visibleIds.includes(activeView);
  const activeMeta = canRenderActiveView ? VIEW_META[activeView] : null;

  useEffect(() => {
    if (auth.status !== 'authenticated') return;
    if (!canRenderActiveView) setActiveView(visibleIds[0] || null);
  }, [auth.status, canRenderActiveView, visibleIds]);

  useEffect(() => {
    if (!activeView || typeof window === 'undefined') return;
    const nextUrl = new URL(window.location.href);
    nextUrl.searchParams.set('painel', activeView);
    nextUrl.searchParams.delete('view');
    window.history.replaceState(null, '', nextUrl);
  }, [activeView]);

  useEffect(() => {
    if (busy && !loaderVisibleRef.current) {
      loader.show(1);
      loaderVisibleRef.current = true;
    }
    if (!busy && loaderVisibleRef.current) {
      loader.hide();
      loaderVisibleRef.current = false;
    }
  }, [busy, loader]);

  const handleSelectView = (view) => {
    if (!visibleIds.includes(view)) return;
    setNotification(null);
    setActiveView(view);
  };

  const handleLogout = async () => {
    setSidebarOpen(false);
    setNotification(null);
    try {
      await auth.logout();
      setActiveView(null);
    } catch (requestError) {
      setNotification({
        type: 'error',
        message: requestError.message || 'Não foi possível encerrar a sessão.',
      });
    }
  };

  if (auth.status === 'loading' && !auth.authenticated) {
    return (
      <main className="access-login-shell" aria-busy="true">
        <p className="access-loading" role="status">
          <Loader2 className="access-spin" size={18} aria-hidden="true" />
          Verificando sessão...
        </p>
      </main>
    );
  }

  if (!auth.authenticated) return <LoginScreen />;
  if (auth.passwordChangeRequired) return <PasswordChangeScreen />;

  const ActiveIcon = activeMeta?.icon || BarChart3;

  return (
    <div className="access-app-layout" data-theme-mode="dark">
      <AppSidebar
        modules={visibleModules}
        permissions={auth.permissions}
        activeView={activeView}
        onSelectView={handleSelectView}
        user={auth.user}
        onLogout={handleLogout}
        open={sidebarOpen}
        onOpenChange={setSidebarOpen}
      />

      <main className="aideal-shell access-app-main">
        <AidealPartnershipLoader
          visible={loader.visible}
          exiting={loader.exiting}
          scene={loader.scene}
          title="AIDEAL × GoFlowOS"
          subtitle="Processando inteligência financeira"
        />

        <header className="aideal-header">
          <div className="aideal-brand">
            <img src="/logo-aideal-peq-2.png" alt="AIDEAL Engenharia de Superfície" />
            <div>
              <h1>AIDEAL GoFlowOS</h1>
              <p>{activeMeta?.subtitle || 'Acesso configurado pelo administrador'}</p>
            </div>
          </div>
          {activeMeta && (
            <div className="aideal-header-actions">
              <div className="aideal-context-chip">
                <ActiveIcon size={15} aria-hidden="true" />
                {activeMeta.title}
              </div>
            </div>
          )}
        </header>

        {notification && (
          <section
            className={`aideal-panel ${
              notification.type === 'success' ? 'aideal-panel-neutral' : 'aideal-panel-error'
            } aideal-notification`}
          >
            <strong>{notification.type === 'success' ? 'Operação concluída' : 'Operação com erro'}</strong>
            <div>{notification.message}</div>
          </section>
        )}

        {visibleModules.length === 0 && (
          <section className="aideal-panel access-no-modules" role="status">
            <h2>Nenhum painel liberado</h2>
            <p>Solicite ao administrador Eduardo a liberação do acesso necessário.</p>
          </section>
        )}

        {canRenderActiveView && activeView === 'dre' && (
          <PainelDRE
            apiBase={API_BASE}
            csrfToken={auth.csrfToken}
            onBusyChange={setBusy}
            onNotify={setNotification}
          />
        )}

        {canRenderActiveView && activeView === 'fluxo_caixa' && (
          <PainelFluxoCaixa apiBase={API_BASE} onBusyChange={setBusy} />
        )}

        {canRenderActiveView && activeView === 'admin_banco' && (
          <AdminPanel
            apiBase={API_BASE}
            user={auth.user}
            csrfToken={auth.csrfToken}
            onNotify={setNotification}
            onBusyChange={setBusy}
          />
        )}

        {canRenderActiveView && activeView === 'usuarios' && (
          <AccessManagementPanel
            apiBase={API_BASE}
            csrfToken={auth.csrfToken}
            currentUserId={auth.user?.id}
            onNotify={setNotification}
            onBusyChange={setBusy}
          />
        )}

        {canRenderActiveView && activeView === 'orcamento' && (
          <OrcamentoPanel
            apiBase={API_BASE}
            csrfToken={auth.csrfToken}
            onNotify={setNotification}
            permissions={auth.permissions}
          />
        )}
      </main>
    </div>
  );
}
