import React, { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { BarChart3, Calculator, Database, Loader2, Users, WalletCards } from 'lucide-react';
import { useLiquidLoaderController } from 'goflow-core';
import AidealKineticLoader from './components/AidealKineticLoader';
import AppSidebar from './components/AppSidebar';
import ViewErrorBoundary from './components/ViewErrorBoundary';
import { filterAccessibleModules } from './components/accessControlModel';
import { LoginScreen, PasswordChangeScreen, useAuth } from './auth';
import { clearPanelData, panelDataCache } from './services/panelDataCache';
import './styles/access-control.css';

const API_BASE = '/api';

// Cada painel vira um chunk próprio; o import é memorizado pelo navegador, então
// pré-carregar no hover/foco da sidebar e renderizar depois usam o mesmo módulo.
const VIEW_LOADERS = Object.freeze({
  dre: () => import('./components/PainelDRE'),
  fluxo_caixa: () => import('./components/PainelFluxoCaixa'),
  admin_banco: () => import('./components/AdminPanel'),
  usuarios: () => import('./components/AccessManagementPanel'),
  orcamento: () => import('./components/OrcamentoPanel'),
});

// Primeira consulta de cada painel financeiro (sem filtros). Ela sai junto com o
// download do chunk; o hook do painel reaproveita a mesma requisição em voo.
const VIEW_INITIAL_DATA = Object.freeze({
  dre: { url: `${API_BASE}/dre/painel`, errorMessage: 'Erro ao carregar Painel DRE' },
  fluxo_caixa: {
    url: `${API_BASE}/fluxo_caixa/painel`,
    errorMessage: 'Erro ao carregar Painel Fluxo de Caixa',
  },
});

const PainelDRE = lazy(VIEW_LOADERS.dre);
const PainelFluxoCaixa = lazy(VIEW_LOADERS.fluxo_caixa);
const AdminPanel = lazy(VIEW_LOADERS.admin_banco);
const AccessManagementPanel = lazy(VIEW_LOADERS.usuarios);
const OrcamentoPanel = lazy(VIEW_LOADERS.orcamento);

const prefetchView = (view) => {
  VIEW_LOADERS[view]?.().catch(() => {
    // Falha de rede na pré-carga é tratada quando o painel for aberto.
  });
};

const scheduleIdle = (callback) => {
  if (typeof window === 'undefined') return () => {};
  if (typeof window.requestIdleCallback === 'function') {
    const handle = window.requestIdleCallback(callback, { timeout: 4000 });
    return () => window.cancelIdleCallback(handle);
  }
  const handle = window.setTimeout(callback, 1800);
  return () => window.clearTimeout(handle);
};

function ViewFallback() {
  return (
    <section className="aideal-view-fallback" role="status" aria-label="Carregando painel">
      <span className="aideal-skeleton-line is-short" />
      <span className="aideal-skeleton-line is-wide" />
      <span className="aideal-skeleton-line is-medium" />
    </section>
  );
}


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
    minVisibleMs: 1700,
    exitMs: 720,
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
  const userId = auth.user?.id || null;

  // Respostas em cache pertencem à sessão que as buscou.
  useEffect(() => () => clearPanelData(), [userId]);

  useEffect(() => {
    if (auth.status !== 'authenticated' || auth.passwordChangeRequired || !canRenderActiveView) return;
    const initialData = VIEW_INITIAL_DATA[activeView];
    if (initialData) panelDataCache.load(initialData.url, { errorMessage: initialData.errorMessage }).catch(() => {});
  }, [activeView, auth.passwordChangeRequired, auth.status, canRenderActiveView]);

  // Depois que a tela atual assentar, baixa os outros painéis liberados em segundo plano.
  useEffect(() => {
    if (auth.status !== 'authenticated' || auth.passwordChangeRequired) return undefined;
    return scheduleIdle(() => visibleIds.forEach(prefetchView));
  }, [auth.passwordChangeRequired, auth.status, visibleIds]);

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

  const handleSelectView = useCallback((view) => {
    if (!visibleIds.includes(view)) return;
    setNotification(null);
    setActiveView(view);
  }, [visibleIds]);

  const handleLogout = async () => {
    setSidebarOpen(false);
    setNotification(null);
    try {
      await auth.logout();
      clearPanelData();
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
        onPrefetchView={prefetchView}
      />

      <main className="aideal-shell access-app-main">
        <AidealKineticLoader
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
              <div className="aideal-context-chip" title={activeMeta.title}>
                <ActiveIcon size={15} aria-hidden="true" />
                <span>{activeMeta.title}</span>
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

        <ViewErrorBoundary resetKey={activeView}>
          <Suspense fallback={<ViewFallback />}>
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
                currentUserId={auth.user?.id}
                onNotify={setNotification}
                permissions={auth.permissions}
              />
            )}
          </Suspense>
        </ViewErrorBoundary>
      </main>
    </div>
  );
}
