import React, { useEffect, useRef, useState } from 'react';
import { BarChart3, Database, WalletCards } from 'lucide-react';
import {
  WaveBar,
  useLiquidLoaderController,
} from 'goflow-core';
import AidealPartnershipLoader from './components/AidealPartnershipLoader';
import AdminPanel from './components/AdminPanel';
import PainelDRE from './components/PainelDRE';
import PainelFluxoCaixa from './components/PainelFluxoCaixa';

const API_BASE = '/api';

const views = {
  dre: {
    title: 'Painel DRE',
    subtitle: 'Resultado por obra e centro de custos',
    icon: <BarChart3 size={15} />,
  },
  fluxo_caixa: {
    title: 'Painel Fluxo de Caixa',
    subtitle: 'Entradas, saídas, bancos e classificações',
    icon: <WalletCards size={15} />,
  },
  admin_banco: {
    title: 'Admin Banco',
    subtitle: 'Operações protegidas de banco',
    icon: <Database size={15} />,
  },
};

const getInitialView = () => {
  if (typeof window === 'undefined') return 'dre';
  const params = new URLSearchParams(window.location.search);
  const candidate = params.get('painel') || params.get('view');
  return views[candidate] ? candidate : 'dre';
};

export default function App() {
  const [activeView, setActiveView] = useState(getInitialView);
  const [notification, setNotification] = useState(null);
  const [busy, setBusy] = useState(false);
  const loader = useLiquidLoaderController({
    intervalMs: 3200,
    minVisibleMs: 1400,
    exitMs: 420,
  });
  const loaderVisibleRef = useRef(false);
  const activeMeta = views[activeView] || views.dre;

  const handleSelectView = (view) => {
    setActiveView(view);
    if (typeof window === 'undefined') return;
    const nextUrl = new URL(window.location.href);
    nextUrl.searchParams.set('painel', view);
    window.history.replaceState(null, '', nextUrl);
  };

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

  return (
    <main className="aideal-shell" data-theme-mode="dark">
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
            <p>{activeMeta.subtitle}</p>
          </div>
        </div>
        <div className="aideal-header-actions">
          <div className="aideal-context-chip">
            {activeMeta.icon}
            {activeMeta.title}
          </div>
          <WaveBar
            activeId={activeView}
            onSelect={handleSelectView}
            items={[
              { id: 'dre', label: 'Painel DRE', icon: <BarChart3 size={15} /> },
              { id: 'fluxo_caixa', label: 'Painel Fluxo', icon: <WalletCards size={15} /> },
              { id: 'admin_banco', label: 'Admin Banco', icon: <Database size={15} /> },
            ]}
          />
        </div>
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

      {activeView === 'dre' && (
        <PainelDRE apiBase={API_BASE} onBusyChange={setBusy} />
      )}

      {activeView === 'fluxo_caixa' && (
        <PainelFluxoCaixa apiBase={API_BASE} onBusyChange={setBusy} />
      )}

      {activeView === 'admin_banco' && (
        <AdminPanel apiBase={API_BASE} onNotify={setNotification} onBusyChange={setBusy} />
      )}
    </main>
  );
}
