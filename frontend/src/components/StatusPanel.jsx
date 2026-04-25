import React from 'react';
import { resolveProcessamentoTotal } from './statusPanelModel.js';

const formatStatus = (status) => {
  if (!status) return 'Pendente';
  if (status === 'completed' || status === 'concluido') return 'Concluído';
  if (status === 'processing') return 'Processando';
  if (status === 'validating') return 'Validando';
  if (status === 'error') return 'Erro';
  return String(status);
};

const formatMeses = (meses) => {
  if (!Array.isArray(meses) || meses.length === 0) return '-';
  return meses
    .map((m) => String(m).padStart(2, '0'))
    .join(', ');
};

export default function StatusPanel({ validacao, processamento, fluxo }) {
  const fluxoLabel = fluxo === 'dre' ? 'DRE' : 'Fluxo de Caixa';
  const validationErrors = validacao?.erros || [];
  const validationWarnings = validacao?.warnings || [];
  const processErrors = processamento?.erros || [];
  const processWarnings = processamento?.warnings || [];
  const processamentoMeta = processamento?.metadata || {};
  const validacaoMeta = validacao?.metadata || {};
  const periodoMeta = { ...validacaoMeta, ...processamentoMeta };
  const totalWarnings = validationWarnings.length + processWarnings.length;
  const validationOk = validacao ? validacao.valido : null;
  const processCompleted =
    processamento && (processamento.status === 'completed' || processamento.status === 'concluido');
  const processErro = processamento?.status === 'error' || processErrors.length > 0;
  const validationClass =
    validationOk === true ? 'aideal-status-ok' : validationOk === false ? 'aideal-status-error' : '';
  const processClass = processCompleted ? 'aideal-status-ok' : processErro ? 'aideal-status-error' : '';
  const totalLinhasValidadas = validacao?.total_linhas || 0;
  const totalRegistrosReais = resolveProcessamentoTotal(processamento);
  const downloadUrl =
    processamento?.download_url || (processamento?.id ? `/api/processamentos/${processamento.id}/download` : null);

  return (
    <section style={{ marginTop: '14px' }}>
      <div className="aideal-grid-4" style={{ marginBottom: '12px' }}>
        <article className="aideal-kpi">
          <p className="aideal-kpi-label">Validação</p>
          <p className={`aideal-kpi-value ${validationClass}`}>
            {validationOk === null ? 'Pendente' : validationOk ? 'Válido' : 'Inválido'}
          </p>
        </article>

        <article className="aideal-kpi">
          <p className="aideal-kpi-label">Processamento</p>
          <p className={`aideal-kpi-value ${processClass}`}>
            {processamento ? formatStatus(processamento.status) : 'Pendente'}
          </p>
        </article>

        <article className="aideal-kpi">
          <p className="aideal-kpi-label">Registros reais</p>
          <p className="aideal-kpi-value">
            {totalRegistrosReais}
          </p>
        </article>

        <article className="aideal-kpi">
          <p className="aideal-kpi-label">Warnings</p>
          <p className="aideal-kpi-value" style={{ color: totalWarnings > 0 ? '#aa7d00' : 'var(--aideal-text)' }}>
            {totalWarnings}
          </p>
        </article>
      </div>

      {validationErrors.length > 0 && (
        <article className="aideal-panel aideal-panel-error" style={{ marginBottom: '10px' }}>
          <h4 style={{ margin: '0 0 8px', color: 'var(--aideal-accent-red)' }}>Erros de validação</h4>
          {validationErrors.map((e, i) => (
            <div key={i} style={{ marginBottom: '8px' }}>
              <div style={{ fontSize: '0.84rem', fontWeight: 700 }}>{e.campo}</div>
              <div style={{ fontSize: '0.82rem', color: 'var(--aideal-text-soft)' }}>{e.mensagem}</div>
              {e.sugestao && (
                <div style={{ fontSize: '0.79rem', color: 'var(--aideal-primary-dark)', marginTop: '2px' }}>
                  Sugestão: {e.sugestao}
                </div>
              )}
            </div>
          ))}
        </article>
      )}

      {validationWarnings.length > 0 && (
        <article className="aideal-panel aideal-panel-warning" style={{ marginBottom: '10px' }}>
          <h4 style={{ margin: '0 0 8px', color: '#aa7d00' }}>Warnings de validação</h4>
          {validationWarnings.map((w, i) => (
            <div key={i} style={{ marginBottom: '8px' }}>
              <div style={{ fontSize: '0.84rem', fontWeight: 700 }}>{w.campo}</div>
              <div style={{ fontSize: '0.82rem', color: 'var(--aideal-text-soft)' }}>{w.mensagem}</div>
              {w.sugestao && (
                <div style={{ fontSize: '0.79rem', color: 'var(--aideal-primary-dark)', marginTop: '2px' }}>
                  Sugestão: {w.sugestao}
                </div>
              )}
            </div>
          ))}
        </article>
      )}

      {processWarnings.length > 0 && (
        <article className="aideal-panel aideal-panel-warning" style={{ marginBottom: '10px' }}>
          <h4 style={{ margin: '0 0 8px', color: '#aa7d00' }}>Warnings de processamento</h4>
          {processWarnings.map((w, i) => (
            <div key={i} style={{ marginBottom: '8px' }}>
              <div style={{ fontSize: '0.84rem', fontWeight: 700 }}>{w.campo}</div>
              <div style={{ fontSize: '0.82rem', color: 'var(--aideal-text-soft)' }}>{w.mensagem}</div>
              {w.sugestao && (
                <div style={{ fontSize: '0.79rem', color: 'var(--aideal-primary-dark)', marginTop: '2px' }}>
                  Sugestão: {w.sugestao}
                </div>
              )}
            </div>
          ))}
        </article>
      )}

      {processErrors.length > 0 && (
        <article className="aideal-panel aideal-panel-error" style={{ marginBottom: '10px' }}>
          <h4 style={{ margin: '0 0 8px', color: 'var(--aideal-accent-red)' }}>Erros de processamento</h4>
          {processErrors.map((e, i) => (
            <div key={i} style={{ marginBottom: '8px' }}>
              <div style={{ fontSize: '0.84rem', fontWeight: 700 }}>{e.campo}</div>
              <div style={{ fontSize: '0.82rem', color: 'var(--aideal-text-soft)' }}>{e.mensagem}</div>
              {e.sugestao && (
                <div style={{ fontSize: '0.79rem', color: 'var(--aideal-primary-dark)', marginTop: '2px' }}>
                  Sugestão: {e.sugestao}
                </div>
              )}
            </div>
          ))}
        </article>
      )}

      {(validacao || processamento) && (
        <article className="aideal-panel aideal-panel-neutral">
          <h4 style={{ margin: '0 0 8px', color: 'var(--aideal-primary-dark)' }}>
            Detalhes técnicos ({fluxo === 'dre' ? 'DRE' : 'Fluxo de Caixa'})
          </h4>
          <div style={{ fontSize: '0.82rem', lineHeight: 1.7, color: 'var(--aideal-text-soft)' }}>
            {totalLinhasValidadas > 0 ? <div>Total de linhas validadas (arquivo bruto): {totalLinhasValidadas}</div> : null}
            {processamentoMeta?.bd_fluxo_range_fisico && (
              <div>BD_FLUXO (range físico): {processamentoMeta.bd_fluxo_range_fisico}</div>
            )}
            {processamentoMeta?.bd_fluxo_linhas_entrada_reescritas != null && (
              <div>Linhas reescritas pelo lote: {processamentoMeta.bd_fluxo_linhas_entrada_reescritas}</div>
            )}
            {processamentoMeta?.bd_fluxo_limpeza_faixa_aplicada != null && (
              <div>
                Limpeza total da faixa BD_FLUXO: {processamentoMeta.bd_fluxo_limpeza_faixa_aplicada ? 'sim' : 'não'}
              </div>
            )}
            {processamentoMeta?.bd_fluxo_cabecalho_linha && (
              <div>Cabeçalho BD_FLUXO: linha {processamentoMeta.bd_fluxo_cabecalho_linha}</div>
            )}
            {processamentoMeta?.bd_fluxo_ultima_linha_dados_reais && (
              <div>Última linha com dados reais: {processamentoMeta.bd_fluxo_ultima_linha_dados_reais}</div>
            )}
            {processamentoMeta?.bd_fluxo_linhas_sem_lancamento_faixa && (
              <div>
                Linhas sem lançamento real: {processamentoMeta.bd_fluxo_linhas_sem_lancamento_faixa}
                {' '} (fórmulas/estrutura do template)
              </div>
            )}
            {processamentoMeta?.bd_fluxo_linhas_sem_lancamento_ocultadas === true && (
              <div>Visual: linhas sem lançamento foram ocultadas automaticamente no BD_FLUXO.</div>
            )}
            {validacao?.abas_encontradas && <div>Abas encontradas: {validacao.abas_encontradas.join(', ')}</div>}
            {periodoMeta?.dre_periodo_modo_cumulativo === true && (
              <div>Modo cumulativo: ativo (jan até a competência).</div>
            )}
            {periodoMeta?.dre_periodo_modo_cumulativo === false && (
              <div style={{ color: '#aa7d00' }}>Modo cumulativo: desativado (teste).</div>
            )}
            {periodoMeta?.dre_periodo_competencia && (
              <div>Competência informada: {periodoMeta.dre_periodo_competencia}</div>
            )}
            {periodoMeta?.dre_periodo_data_min && periodoMeta?.dre_periodo_data_max && (
              <div>
                Período detectado no arquivo: {periodoMeta.dre_periodo_data_min} até{' '}
                {periodoMeta.dre_periodo_data_max}
              </div>
            )}
            {Array.isArray(periodoMeta?.dre_periodo_anos_encontrados) &&
              periodoMeta.dre_periodo_anos_encontrados.length > 0 && (
                <div>Anos encontrados: {periodoMeta.dre_periodo_anos_encontrados.join(', ')}</div>
            )}
            {Array.isArray(periodoMeta?.dre_periodo_meses_encontrados_ano_competencia) &&
              periodoMeta.dre_periodo_meses_encontrados_ano_competencia.length > 0 && (
                <div>
                  Meses encontrados no ano da competência:{' '}
                  {formatMeses(periodoMeta.dre_periodo_meses_encontrados_ano_competencia)}
                </div>
            )}
            {periodoMeta?.dre_periodo_contagem_linhas_por_mes_ano_competencia &&
              typeof periodoMeta.dre_periodo_contagem_linhas_por_mes_ano_competencia === 'object' &&
              Object.keys(periodoMeta.dre_periodo_contagem_linhas_por_mes_ano_competencia).length > 0 && (
                <div>
                  Linhas por mês (ano da competência):{' '}
                  {Object.entries(periodoMeta.dre_periodo_contagem_linhas_por_mes_ano_competencia)
                    .map(([mes, qtd]) => `${String(mes).padStart(2, '0')}: ${qtd}`)
                    .join(' | ')}
                </div>
            )}
            {Array.isArray(periodoMeta?.dre_periodo_meses_esperados_ano_competencia) &&
              periodoMeta.dre_periodo_meses_esperados_ano_competencia.length > 0 && (
                <div>
                  Meses esperados (jan..competência):{' '}
                  {formatMeses(periodoMeta.dre_periodo_meses_esperados_ano_competencia)}
                </div>
            )}
            {Array.isArray(periodoMeta?.dre_periodo_meses_faltantes_ano_competencia) &&
              periodoMeta.dre_periodo_meses_faltantes_ano_competencia.length > 0 && (
                <div style={{ color: 'var(--aideal-accent-red)' }}>
                  Meses faltantes para cumulativo:{' '}
                  {formatMeses(periodoMeta.dre_periodo_meses_faltantes_ano_competencia)}
                </div>
            )}
            {processamento?.id && <div>ID do processamento: {processamento.id}</div>}
            {processamento?.arquivo_saida && <div>Arquivo de saída: {processamento.arquivo_saida}</div>}
            {processamento?.estrategia_meses && (
              <div>Estratégia de meses: {processamento.estrategia_meses}</div>
            )}
            {Array.isArray(processamento?.meses_disponiveis) &&
              processamento.meses_disponiveis.length > 0 && (
                <div>Meses disponíveis no banco: {formatMeses(processamento.meses_disponiveis)}</div>
            )}
            {Array.isArray(processamento?.meses_solicitados) &&
              processamento.meses_solicitados.length > 0 && (
                <div>Meses solicitados na geração: {formatMeses(processamento.meses_solicitados)}</div>
            )}
            {Array.isArray(processamento?.meses_utilizados) &&
              processamento.meses_utilizados.length > 0 && (
                <div>Meses visíveis no {fluxoLabel} final: {formatMeses(processamento.meses_utilizados)}</div>
            )}
            {Array.isArray(processamento?.meses_ocultos) &&
              processamento.meses_ocultos.length > 0 && (
                <div>Meses ocultos no {fluxoLabel} final: {formatMeses(processamento.meses_ocultos)}</div>
            )}
            {processamento?.registros_processados != null && (
              <div>Registros processados: {processamento.registros_processados}</div>
            )}
            {processamento?.bancos_identificados && processamento.bancos_identificados.length > 0 && (
              <div>Bancos identificados: {processamento.bancos_identificados.join(', ')}</div>
            )}
            {validacao?.colunas_encontradas && Array.isArray(validacao.colunas_encontradas) && (
              <div>Colunas encontradas: {validacao.colunas_encontradas.join(', ')}</div>
            )}
            {downloadUrl && (
              <div>
                Download:{' '}
                <a className="aideal-action-link" href={downloadUrl} target="_blank" rel="noreferrer">
                  abrir arquivo final
                </a>
              </div>
            )}
          </div>
        </article>
      )}
    </section>
  );
}
