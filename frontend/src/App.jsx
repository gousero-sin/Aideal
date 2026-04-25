import React, { useState } from 'react';
import FlowSelector from './components/FlowSelector';
import UploadPanel from './components/UploadPanel';
import StatusPanel from './components/StatusPanel';
import { resolveProcessamentoTotal } from './components/statusPanelModel.js';

const API_BASE = '/api';

export default function App() {
  const [fluxoSelecionado, setFluxoSelecionado] = useState(null);
  const [notification, setNotification] = useState(null);
  const [validacao, setValidacao] = useState(null);
  const [processamento, setProcessamento] = useState(null);

  const handleFluxoSelect = (fluxo) => {
    setFluxoSelecionado(fluxo);
    setValidacao(null);
    setProcessamento(null);
    setNotification(null);
  };

  const handleValidationResult = (result) => {
    if (!result) {
      setValidacao(null);
      setNotification(null);
      return;
    }

    setValidacao(result);
    if (result.valido) {
      setNotification({ type: 'success', message: 'Estrutura validada com sucesso.' });
    } else {
      setNotification({
        type: 'error',
        message: `Validação com ${result.erros?.length || 0} erro(s) bloqueante(s).`,
      });
    }
  };

  const handleProcessResult = (result) => {
    if (!result) {
      setProcessamento(null);
      setNotification(null);
      return;
    }

    setProcessamento(result);

    const temErro = result?.erros?.length > 0 || result?.status === 'error' || result?.sucesso === false;
    const total = resolveProcessamentoTotal(result);
    const stage = result?._stage;
    const fluxoLabel = fluxoSelecionado === 'dre' ? 'DRE' : 'Fluxo de Caixa';

    if (temErro) {
      setNotification({
        type: 'error',
        message:
          stage === 'ingestao'
            ? `Ingestão com ${result?.erros?.length || 0} erro(s).`
            : stage === 'limpeza'
              ? `Limpeza da base com ${result?.erros?.length || 0} erro(s).`
              : `Processamento ${fluxoLabel} com ${result?.erros?.length || 0} erro(s).`,
      });
      return;
    }

    if (stage === 'ingestao') {
      if (result?.status === 'already_processed') {
        setNotification({
          type: 'success',
          message: `Arquivo já estava processado para ${result?.competencia || 'a competência informada'}.`,
        });
        return;
      }
      setNotification({
        type: 'success',
        message: `Mês salvo no banco com ${total} lançamento(s).`,
      });
      return;
    }

    if (stage === 'limpeza') {
      const removidos = result?.lancamentos_removidos ?? result?.movimentos_removidos ?? 0;
      setNotification({
        type: 'success',
        message: `Base ${fluxoLabel} limpa (${result?.uploads_removidos || 0} uploads e ${removidos} lançamentos removidos).`,
      });
      return;
    }

    setNotification({
      type: 'success',
      message:
        total > 0
          ? `${fluxoLabel} final gerado com ${total} lançamento(s).`
          : `${fluxoLabel} final gerado com sucesso.`,
    });
  };

  const handleVoltar = () => {
    setFluxoSelecionado(null);
    setValidacao(null);
    setProcessamento(null);
    setNotification(null);
  };

  return (
    <main className="aideal-shell">
      <header className="aideal-header">
        <div className="aideal-brand">
          <h1>AIDEAL GoFlowOS</h1>
          <p>Motor de consolidação financeira • MVP • Fase 2 operacional do DRE</p>
        </div>
        <div className="aideal-badge">Cloudflare browser-first + local/server</div>
      </header>

      {notification && (
        <section
          className={`aideal-panel ${
            notification.type === 'success' ? 'aideal-panel-neutral' : 'aideal-panel-error'
          }`}
          style={{ marginBottom: '14px' }}
        >
          <strong>{notification.type === 'success' ? 'Operação concluída' : 'Operação com erro'}</strong>
          <div style={{ marginTop: '6px', color: 'var(--aideal-text-soft)' }}>{notification.message}</div>
        </section>
      )}

      {!fluxoSelecionado ? (
        <FlowSelector onSelect={handleFluxoSelect} />
      ) : (
        <section className="aideal-card" style={{ padding: '16px' }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '12px',
              gap: '10px',
            }}
          >
            <div>
              <h2 style={{ margin: 0, color: 'var(--aideal-primary-dark)', fontSize: '1.1rem' }}>
                {fluxoSelecionado === 'dre' ? 'Fluxo DRE' : 'Fluxo de Caixa'}
              </h2>
              <p style={{ margin: '4px 0 0', fontSize: '0.84rem', color: 'var(--aideal-text-soft)' }}>
                {fluxoSelecionado === 'dre'
                  ? 'Validação, geração e download do DRE final no template oficial.'
                  : 'Ingestão mensal, seleção de meses e geração do consolidado oficial.'}
              </p>
            </div>
            <button className="aideal-action aideal-action-secondary" onClick={handleVoltar}>
              Voltar
            </button>
          </div>

          <UploadPanel
            fluxo={fluxoSelecionado}
            apiBase={API_BASE}
            onValidation={handleValidationResult}
            onProcess={handleProcessResult}
            processamento={processamento}
            validacao={validacao}
          />
          {(validacao || processamento) && (
            <StatusPanel
              validacao={validacao}
              processamento={processamento}
              fluxo={fluxoSelecionado}
            />
          )}
        </section>
      )}
    </main>
  );
}
