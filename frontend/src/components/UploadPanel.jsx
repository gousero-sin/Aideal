import React, { useEffect, useMemo, useRef, useState } from 'react';

const pad = (value) => String(value).padStart(2, '0');

const MESES_LABEL = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

const defaultCompetencia = () => {
  const hoje = new Date();
  return `${hoje.getFullYear()}-${pad(hoje.getMonth() + 1)}`;
};

const competenciaParaExibicao = (valor) => {
  if (!valor || !valor.includes('-')) return '';
  const [ano, mes] = valor.split('-');
  return `${pad(mes)}/${ano}`;
};

const anoDaCompetencia = (valor) => {
  if (!valor || !valor.includes('-')) return null;
  const [ano] = valor.split('-');
  const parsed = Number(ano);
  return Number.isNaN(parsed) ? null : parsed;
};

const mesDaCompetencia = (valor) => {
  if (!valor || !valor.includes('-')) return null;
  const [, mes] = valor.split('-');
  const parsed = Number(mes);
  return Number.isNaN(parsed) ? null : parsed;
};

export default function UploadPanel({
  fluxo,
  apiBase,
  onValidation,
  onProcess,
  processamento,
  validacao,
}) {
  const [arquivos, setArquivos] = useState([]);
  const [loadingValidation, setLoadingValidation] = useState(false);
  const [loadingIngestao, setLoadingIngestao] = useState(false);
  const [loadingGeracao, setLoadingGeracao] = useState(false);
  const [loadingLimpeza, setLoadingLimpeza] = useState(false);
  const [competencia, setCompetencia] = useState(defaultCompetencia());
  const [mesesDisponiveis, setMesesDisponiveis] = useState([]);
  const [mesesSelecionados, setMesesSelecionados] = useState([]);
  const [anoTodo, setAnoTodo] = useState(false);
  const [loadingMeses, setLoadingMeses] = useState(false);
  const [erroMeses, setErroMeses] = useState(null);
  const fileInputRef = useRef(null);

  const isFluxoCaixa = fluxo === 'fluxo_caixa';
  const isMultiple = isFluxoCaixa;
  const isDre = fluxo === 'dre';
  const usaBancoMensal = isDre || isFluxoCaixa;
  const fluxoLabel = isDre ? 'DRE' : 'Fluxo de Caixa';
  const anoCompetencia = anoDaCompetencia(competencia);
  const mesCompetencia = mesDaCompetencia(competencia);
  const arquivoPareceTemplate =
    isDre &&
    arquivos.some((f) => {
      const nome = (f?.name || '').toLowerCase();
      return nome.includes('aideal') || nome.includes('obra') || nome.includes('bd_fluxo');
    });
  const acceptFormats = '.xls,.xlsx';
  const downloadUrl =
    processamento?.download_url ||
    (processamento?.id ? `${apiBase}/processamentos/${processamento.id}/download` : null);

  const mesesSelecionadosOrdenados = useMemo(
    () => [...mesesSelecionados].sort((a, b) => a - b),
    [mesesSelecionados],
  );

  const carregarMesesDisponiveis = async (ano, mesRef) => {
    if (!usaBancoMensal || !ano) return;

    setLoadingMeses(true);
    setErroMeses(null);
    try {
      const recurso = isDre ? 'dre' : 'fluxo_caixa';
      const response = await fetch(`${apiBase}/${recurso}/ingestoes?ano=${ano}&limit=500`);
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err?.detail || 'Erro ao carregar meses disponíveis');
      }

      const payload = await response.json();
      const ingestoes = Array.isArray(payload?.ingestoes) ? payload.ingestoes : [];
      const meses = [...new Set(
        ingestoes
          .filter((ing) => ing?.status === 'completed')
          .map((ing) => {
            const comp = String(ing?.competencia || '');
            const [mesStr, anoStr] = comp.split('/');
            if (!mesStr || !anoStr) return null;
            if (Number(anoStr) !== ano) return null;
            const m = Number(mesStr);
            if (Number.isNaN(m) || m < 1 || m > 12) return null;
            return m;
          })
          .filter((m) => m != null),
      )].sort((a, b) => a - b);

      setMesesDisponiveis(meses);
      setMesesSelecionados((prev) => {
        const filtrados = prev.filter((m) => meses.includes(m));
        if (filtrados.length > 0) return filtrados;
        if (!mesRef) return [];
        return meses.filter((m) => m <= mesRef);
      });
    } catch (err) {
      setMesesDisponiveis([]);
      setMesesSelecionados([]);
      setErroMeses(err.message);
    } finally {
      setLoadingMeses(false);
    }
  };

  useEffect(() => {
    if (!usaBancoMensal) return;
    carregarMesesDisponiveis(anoCompetencia, mesCompetencia);
  }, [apiBase, usaBancoMensal, isDre, anoCompetencia, mesCompetencia]);

  const handleToggleMes = (mes) => {
    if (anoTodo) return;
    setMesesSelecionados((prev) => {
      if (prev.includes(mes)) return prev.filter((m) => m !== mes);
      return [...prev, mes].sort((a, b) => a - b);
    });
  };

  const handleAnoTodo = () => {
    setAnoTodo((prev) => !prev);
  };

  const handleFileChange = (e) => {
    const files = Array.from(e.target.files);
    setArquivos(files);
    onValidation?.(null);
    if (processamento) {
      onProcess?.(null);
    }
  };

  const handleValidar = async () => {
    if (arquivos.length === 0) return;

    setLoadingValidation(true);
    try {
      let response;

      if (isMultiple && arquivos.length > 1) {
        const formData = new FormData();
        arquivos.forEach((f) => formData.append('arquivos', f));
        response = await fetch(`${apiBase}/validar/fluxo_caixa/lote`, {
          method: 'POST',
          body: formData,
        });
      } else {
        const formData = new FormData();
        formData.append('arquivo', arquivos[0]);
        if (isDre) {
          formData.append('competencia', competenciaParaExibicao(competencia));
          formData.append('modo_cumulativo', 'false');
        }
        response = await fetch(`${apiBase}/validar/${fluxo}`, {
          method: 'POST',
          body: formData,
        });
      }

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Erro na validacao');
      }

      const result = await response.json();
      onValidation?.(result);
    } catch (err) {
      onValidation?.({
        valido: false,
        erros: [{ campo: 'upload', mensagem: err.message, severidade: 'bloqueante' }],
        warnings: [],
      });
    } finally {
      setLoadingValidation(false);
    }
  };

  const handleIngestao = async () => {
    if (!usaBancoMensal || arquivos.length === 0) return;

    setLoadingIngestao(true);
    try {
      const formData = new FormData();
      if (isDre) {
        formData.append('arquivo', arquivos[0]);
      } else {
        arquivos.forEach((f) => formData.append('arquivos', f));
      }
      formData.append('competencia', competenciaParaExibicao(competencia));
      formData.append('replace', 'true');

      const recurso = isDre ? 'dre' : 'fluxo_caixa';
      const response = await fetch(`${apiBase}/${recurso}/ingestoes`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        const detail = err?.detail;
        throw new Error(
          typeof detail === 'string'
            ? detail
            : detail?.error || detail?.message || `Erro ao salvar mês ${fluxoLabel} no banco`,
        );
      }

      const result = await response.json();
      await carregarMesesDisponiveis(anoCompetencia, mesCompetencia);

      onProcess?.({
        _stage: 'ingestao',
        status: 'completed',
        ...result,
      });
    } catch (err) {
      onProcess?.({
        status: 'error',
        valido: false,
        _stage: 'ingestao',
        erros: [{ campo: 'ingestao', mensagem: err.message, severidade: 'bloqueante' }],
        warnings: [],
      });
    } finally {
      setLoadingIngestao(false);
    }
  };

  const handleGerarDoBanco = async () => {
    if (!usaBancoMensal) return;
    if (mesesDisponiveis.length === 0) {
      onProcess?.({
        status: 'error',
        valido: false,
        _stage: 'geracao',
        erros: [
          {
            campo: 'geracao',
            mensagem: `Nenhum mês salvo no banco para ${fluxoLabel}. Clique em "Salvar mês no banco" antes de gerar.`,
            severidade: 'bloqueante',
          },
        ],
        warnings: [],
      });
      return;
    }

    setLoadingGeracao(true);
    try {
      const formData = new FormData();
      formData.append('competencia', competenciaParaExibicao(competencia));
      formData.append('ano_todo', String(anoTodo));
      if (!anoTodo && mesesSelecionadosOrdenados.length > 0) {
        mesesSelecionadosOrdenados.forEach((mes) => {
          formData.append('meses_incluir', String(mes));
        });
      }

      const recurso = isDre ? 'dre' : 'fluxo_caixa';
      const response = await fetch(`${apiBase}/${recurso}/gerar`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        const detail = err?.detail;
        throw new Error(
          typeof detail === 'string'
            ? detail
            : detail?.error || detail?.message || `Erro ao gerar ${fluxoLabel} do banco`,
        );
      }

      const result = await response.json();
      onProcess?.({
        _stage: 'geracao',
        status: 'completed',
        ...result,
      });
    } catch (err) {
      onProcess?.({
        status: 'error',
        valido: false,
        _stage: 'geracao',
        erros: [{ campo: 'geracao', mensagem: err.message, severidade: 'bloqueante' }],
        warnings: [],
      });
    } finally {
      setLoadingGeracao(false);
    }
  };

  const handleGerarFluxo = async () => {
    if (isDre || arquivos.length === 0) return;

    setLoadingGeracao(true);
    try {
      const formData = new FormData();
      arquivos.forEach((f) => formData.append('arquivos', f));
      formData.append('periodo', competenciaParaExibicao(competencia));

      const response = await fetch(`${apiBase}/fluxo_caixa/gerar`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        const detail = err?.detail;
        throw new Error(
          typeof detail === 'string'
            ? detail
            : detail?.error || detail?.message || 'Erro ao gerar Fluxo de Caixa',
        );
      }

      const result = await response.json();
      onProcess?.({
        _stage: 'geracao',
        status: 'completed',
        ...result,
      });
    } catch (err) {
      onProcess?.({
        status: 'error',
        valido: false,
        _stage: 'geracao',
        erros: [{ campo: 'geracao', mensagem: err.message, severidade: 'bloqueante' }],
        warnings: [],
      });
    } finally {
      setLoadingGeracao(false);
    }
  };

  const handleLimparBase = async () => {
    if (!usaBancoMensal) return;

    setLoadingLimpeza(true);
    try {
      const recurso = isDre ? 'dre' : 'fluxo_caixa';
      const response = await fetch(`${apiBase}/${recurso}/admin/limpar`, {
        method: 'POST',
        body: new FormData(),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err?.detail || `Erro ao limpar base ${fluxoLabel}`);
      }

      const result = await response.json();
      setMesesDisponiveis([]);
      setMesesSelecionados([]);
      setAnoTodo(false);
      onProcess?.({
        _stage: 'limpeza',
        status: 'completed',
        ...result,
      });
    } catch (err) {
      onProcess?.({
        status: 'error',
        valido: false,
        _stage: 'limpeza',
        erros: [{ campo: 'limpeza', mensagem: err.message, severidade: 'bloqueante' }],
        warnings: [],
      });
    } finally {
      setLoadingLimpeza(false);
    }
  };

  const handleRemover = (index) => {
    setArquivos((prev) => prev.filter((_, i) => i !== index));
  };

  const gerarTravado = loadingValidation || loadingIngestao || loadingGeracao || loadingLimpeza;

  return (
    <section className="aideal-card" style={{ padding: '14px' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px' }}>
        <div>
          <h3
            style={{
              margin: '0 0 8px',
              fontSize: '0.96rem',
              color: 'var(--aideal-primary-dark)',
            }}
          >
            Upload de arquivo{isMultiple ? 's' : ''}
          </h3>
          <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--aideal-text-soft)' }}>
            {isDre
              ? 'Fluxo DRE: 1) salvar mês no banco; 2) escolher meses de geração; 3) gerar DRE.'
              : 'Fluxo de Caixa: 1) salvar lote mensal no banco; 2) escolher meses; 3) gerar consolidado.'}
          </p>
        </div>

        {usaBancoMensal && (
          <label
            style={{
              display: 'grid',
              gap: '6px',
              minWidth: '180px',
              fontSize: '0.78rem',
              fontWeight: 700,
              color: 'var(--aideal-primary-dark)',
            }}
          >
            Competência
            <input
              type="month"
              value={competencia}
              onChange={(e) => setCompetencia(e.target.value)}
              style={{
                border: '1px solid var(--aideal-border)',
                borderRadius: '10px',
                padding: '9px 10px',
                fontFamily: 'inherit',
                color: 'var(--aideal-text)',
                background: '#fff',
              }}
            />
          </label>
        )}
      </div>

      {usaBancoMensal && (
        <article
          className="aideal-panel aideal-panel-neutral"
          style={{ marginTop: '10px', marginBottom: '10px', padding: '10px 12px' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
            <strong style={{ color: 'var(--aideal-primary-dark)', fontSize: '0.85rem' }}>
              Meses a incluir
            </strong>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.82rem' }}>
              <input type="checkbox" checked={anoTodo} onChange={handleAnoTodo} disabled={gerarTravado} />
              ANO TODO
            </label>
          </div>

          <div style={{ marginTop: '8px', display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {loadingMeses && <span style={{ fontSize: '0.8rem', color: 'var(--aideal-text-soft)' }}>Carregando meses...</span>}

            {!loadingMeses &&
              mesesDisponiveis.map((mes) => (
                <label
                  key={mes}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    fontSize: '0.8rem',
                    padding: '5px 8px',
                    borderRadius: '8px',
                    border: '1px solid var(--aideal-border)',
                    opacity: anoTodo ? 0.55 : 1,
                    background: mesesSelecionados.includes(mes) ? 'rgba(19, 61, 122, 0.08)' : '#fff',
                  }}
                >
                  <input
                    type="checkbox"
                    checked={mesesSelecionados.includes(mes)}
                    onChange={() => handleToggleMes(mes)}
                    disabled={anoTodo || gerarTravado}
                  />
                  {MESES_LABEL[mes - 1]}
                </label>
              ))}

            {!loadingMeses && mesesDisponiveis.length === 0 && (
              <span style={{ fontSize: '0.8rem', color: 'var(--aideal-text-soft)' }}>
                Sem meses disponíveis no banco para {anoCompetencia || '-'}.
              </span>
            )}
          </div>

          {erroMeses && (
            <div style={{ marginTop: '6px', fontSize: '0.8rem', color: 'var(--aideal-accent-red)' }}>
              {erroMeses}
            </div>
          )}

          <p style={{ margin: '8px 0 0', fontSize: '0.78rem', color: 'var(--aideal-text-soft)' }}>
            {anoTodo
              ? 'Modo ativo: geração com todos os meses disponíveis no banco para o ano da competência.'
              : mesesSelecionadosOrdenados.length > 0
                ? `Modo ativo: meses ${mesesSelecionadosOrdenados.map((m) => MESES_LABEL[m - 1]).join(', ')}.`
                : 'Sem seleção manual: usa regra padrão (meses disponíveis até a competência).'}
          </p>
        </article>
      )}

      <div className="aideal-input-drop" onClick={() => fileInputRef.current?.click()}>
        <p style={{ margin: 0, fontSize: '0.9rem' }}>
          {isMultiple
            ? 'Clique para selecionar arquivos bancários (.xls, .xlsx)'
            : 'Clique para selecionar arquivo DRE (.xls, .xlsx)'}
        </p>
        <input
          ref={fileInputRef}
          type="file"
          accept={acceptFormats}
          multiple={isMultiple}
          onChange={handleFileChange}
          style={{ display: 'none' }}
        />
      </div>

      {arquivos.length > 0 && (
        <div style={{ marginTop: '10px', marginBottom: '10px', display: 'grid', gap: '8px' }}>
          {arquivos.map((f, i) => (
            <div key={i} className="aideal-file-row">
              <span style={{ fontSize: '0.84rem' }}>
                {f.name} ({(f.size / 1024).toFixed(0)} KB)
              </span>
              <button
                className="aideal-action aideal-action-secondary"
                style={{ padding: '7px 10px', fontSize: '0.78rem' }}
                onClick={() => handleRemover(i)}
              >
                Remover
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="aideal-action-row">
        <button
          className="aideal-action aideal-action-primary"
          onClick={handleValidar}
          disabled={arquivos.length === 0 || gerarTravado}
        >
          {loadingValidation ? 'Validando...' : 'Validar estrutura'}
        </button>

        {usaBancoMensal && (
          <button
            className="aideal-action aideal-action-primary"
            onClick={handleIngestao}
            disabled={arquivos.length === 0 || gerarTravado}
          >
            {loadingIngestao ? 'Salvando mês...' : 'Salvar mês no banco'}
          </button>
        )}

        {usaBancoMensal && (
          <button
            className="aideal-action aideal-action-primary"
            onClick={handleGerarDoBanco}
            disabled={gerarTravado}
          >
            {loadingGeracao ? `Gerando ${fluxoLabel}...` : `Gerar ${fluxoLabel} do banco`}
          </button>
        )}

        {!usaBancoMensal && (
          <button
            className="aideal-action aideal-action-primary"
            onClick={handleGerarFluxo}
            disabled={arquivos.length === 0 || gerarTravado}
          >
            {loadingGeracao ? 'Gerando Fluxo...' : 'Gerar Fluxo de Caixa'}
          </button>
        )}

        {usaBancoMensal && (
          <button
            className="aideal-action aideal-action-secondary"
            onClick={handleLimparBase}
            disabled={gerarTravado}
            title={`Remove todos os uploads e lançamentos ${fluxoLabel} da base`}
          >
            {loadingLimpeza ? 'Limpando base...' : `Limpar base ${fluxoLabel}`}
          </button>
        )}

        {downloadUrl && (
          <a
            className="aideal-action aideal-action-secondary aideal-action-link"
            href={downloadUrl}
            target="_blank"
            rel="noreferrer"
          >
            Baixar resultado
          </a>
        )}

        {gerarTravado && <span className="aideal-loader" aria-hidden="true" />}
      </div>

      {usaBancoMensal && !validacao?.valido && (
        <p style={{ margin: '10px 0 0', fontSize: '0.8rem', color: 'var(--aideal-text-soft)' }}>
          Recomenda-se validar antes da ingestão. A geração final usa somente dados já no banco.
        </p>
      )}

      {arquivoPareceTemplate && (
        <p style={{ margin: '8px 0 0', fontSize: '0.8rem', color: 'var(--aideal-accent-red)' }}>
          O arquivo selecionado parece ser template/saída final. Para processar DRE, use o relatório bruto
          de entrada (ex.: RELATORIO DRE MES 05.xls).
        </p>
      )}

      {usaBancoMensal && processamento?.arquivo_saida && (
        <p style={{ margin: '8px 0 0', fontSize: '0.8rem', color: 'var(--aideal-text-soft)' }}>
          Saída gerada: <strong>{processamento.arquivo_saida}</strong>
        </p>
      )}
    </section>
  );
}
