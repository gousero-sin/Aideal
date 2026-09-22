import React, { useEffect, useState } from 'react';
import {
  BarChart3,
  Receipt,
  ShieldCheck,
  WalletCards,
} from 'lucide-react';
import DREIndicatorsAdminPanel from './DREIndicatorsAdminPanel';
import FluxoIndicatorsAdminPanel from './FluxoIndicatorsAdminPanel';
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
  { id: 'indicadores_dre', label: 'Indicadores DRE', icon: <Receipt size={16} aria-hidden="true" /> },
  { id: 'indicadores_fluxo', label: 'Indicadores Fluxo', icon: <WalletCards size={16} aria-hidden="true" /> },
];

export default function AdminPanel({ apiBase, onNotify, onBusyChange, user, csrfToken }) {
  const [activeFlow, setActiveFlow] = useState('dre');
  const [flowState, setFlowState] = useState(createInitialAdminState);
  const [operationBusy, setOperationBusy] = useState(false);
  const activeState = flowState[activeFlow] || {};
  const busy = operationBusy;

  useEffect(() => {
    onBusyChange?.(busy);
  }, [busy, onBusyChange]);

  useEffect(() => () => onBusyChange?.(false), [onBusyChange]);

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
            {user?.displayName || user?.username || 'Admin'}
          </span>
        </div>
      </header>

      {activeFlow === 'indicadores_dre' ? (
        <DREIndicatorsAdminPanel
          apiBase={apiBase}
          csrfToken={csrfToken}
          onNotify={onNotify}
          onBusyChange={setOperationBusy}
        />
      ) : activeFlow === 'indicadores_fluxo' ? (
        <FluxoIndicatorsAdminPanel
          apiBase={apiBase}
          csrfToken={csrfToken}
          onNotify={onNotify}
          onBusyChange={setOperationBusy}
        />
      ) : (
        <UploadPanel
          key={activeFlow}
          fluxo={activeFlow}
          apiBase={apiBase}
          csrfToken={csrfToken}
          onValidation={handleValidation}
          onProcess={handleProcess}
          processamento={activeState.processamento}
          validacao={activeState.validacao}
          onBusyChange={setOperationBusy}
          statusSlot={statusSlot}
        />
      )}
    </section>
  );
}
