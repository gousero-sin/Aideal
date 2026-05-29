import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  CheckCircle2,
  Database,
  Download,
  FileSpreadsheet,
  Loader2,
  ShieldCheck,
  Trash2,
  X,
} from 'lucide-react';

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
  onBusyChange,
}) {
  const [arquivos, setArquivos] = useState([]);
  const [loadingValidation, setLoadingValidation] = useState(false);
  const [loadingIngestao, setLoadingIngestao] = useState(false);
  const [loadingGeracao, setLoadingGeracao] = useState(false);
  const [loadingLimpeza, setLoadingLimpeza] = useState(false);
  const [loadingCompetencia, setLoadingCompetencia] = useState(false);
  const [competencia, setCompetencia] = useState(defaultCompetencia());
  const [competenciaStatus, setCompetenciaStatus] = useState({
    type: 'idle',
    message: 'Selecione um arquivo para detectar automaticamente.',
  });
  const [mesesDisponiveis, setMesesDisponiveis] = useState([]);
  const [mesesSelecionados, setMesesSelecionados] = useState([]);
  const [anoTodo, setAnoTodo] = useState(false);
  const [loadingMeses, setLoadingMeses] = useState(false);
  const [erroMeses, setErroMeses] = useState(null);
  const fileInputRef = useRef(null);
  const competenciaRequestRef = useRef(0);

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

  const detectarCompetencia = async (files) => {
    if (!usaBancoMensal || files.length === 0) {
      setCompetenciaStatus({
        type: 'idle',
        message: 'Selecione um arquivo para detectar automaticamente.',
      });
      return;
    }

    const requestId = competenciaRequestRef.current + 1;
    competenciaRequestRef.current = requestId;
    setLoadingCompetencia(true);
    setCompetenciaStatus({
      type: 'loading',
      message: 'Detectando competência pelo conteúdo do arquivo...',
    });

    try {
      const formData = new FormData();
      if (isDre) {
        formData.append('arquivo', files[0]);
      } else {
        files.forEach((file) => formData.append('arquivos', file));
      }

      const response = await fetch(`${apiBase}/detectar-competencia/${fluxo}`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err?.detail || 'Não foi possível detectar a competência.');
      }

      const payload = await response.json();
      if (competenciaRequestRef.current !== requestId) return;

      if (payload?.detectado && payload?.competencia_input) {
        setCompetencia(payload.competencia_input);
        setMesesSelecionados([]);
        setCompetenciaStatus({
          type: 'success',
          message: `Competência detectada: ${payload.competencia}. Você pode alterar manualmente.`,
        });
        return;
      }

      setCompetenciaStatus({
        type: 'warning',
        message: payload?.message || 'Competência não detectada. Ajuste manualmente.',
      });
    } catch (err) {
      if (competenciaRequestRef.current !== requestId) return;
      setCompetenciaStatus({
        type: 'warning',
        message: `${err.message} Ajuste manualmente.`,
      });
    } finally {
      if (competenciaRequestRef.current === requestId) {
        setLoadingCompetencia(false);
      }
    }
  };

  const handleFileChange = (e) => {
    const files = Array.from(e.target.files);
    setArquivos(files);
    onValidation?.(null);
    if (processamento) {
      onProcess?.(null);
    }
    detectarCompetencia(files);
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
    if (!anoCompetencia || !mesCompetencia) {
      onProcess?.({
        status: 'error',
        valido: false,
        _stage: 'limpeza',
        erros: [{ campo: 'limpeza', mensagem: 'Selecione uma competência válida.', severidade: 'bloqueante' }],
        warnings: [],
      });
      return;
    }

    const competenciaLabel = competenciaParaExibicao(competencia);
    const confirmado = window.confirm(
      `Excluir somente os dados de ${competenciaLabel} em ${fluxoLabel}? Os demais meses serão preservados.`,
    );
    if (!confirmado) return;

    setLoadingLimpeza(true);
    try {
      const recurso = isDre ? 'dre' : 'fluxo_caixa';
      const formData = new FormData();
      formData.append('ano', String(anoCompetencia));
      formData.append('mes', String(mesCompetencia));
      formData.append('confirmar', 'true');

      const response = await fetch(`${apiBase}/${recurso}/admin/limpar`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err?.detail || `Erro ao excluir mês ${fluxoLabel}`);
      }

      const result = await response.json();
      await carregarMesesDisponiveis(anoCompetencia, mesCompetencia);
      setAnoTodo(false);
      onProcess?.({
        _stage: 'limpeza',
        _competenciaLabel: competenciaLabel,
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
    const next = arquivos.filter((_, i) => i !== index);
    setArquivos(next);
    if (next.length === 0) {
      competenciaRequestRef.current += 1;
      setLoadingCompetencia(false);
      setCompetenciaStatus({
        type: 'idle',
        message: 'Selecione um arquivo para detectar automaticamente.',
      });
      return;
    }
    detectarCompetencia(next);
  };

  const gerarTravado =
    loadingCompetencia || loadingValidation || loadingIngestao || loadingGeracao || loadingLimpeza;

  useEffect(() => {
    onBusyChange?.(gerarTravado);
  }, [gerarTravado, onBusyChange]);

  return (
    <section className="aideal-card aideal-upload-panel">
      <div className="aideal-upload-header">
        <div>
          <h3>
            Upload de arquivo{isMultiple ? 's' : ''}
          </h3>
          <p>
            {isDre
              ? 'Fluxo DRE: 1) salvar mês no banco; 2) escolher meses de geração; 3) gerar DRE.'
              : 'Fluxo de Caixa: 1) salvar lote mensal no banco; 2) escolher meses; 3) gerar consolidado.'}
          </p>
        </div>

        {usaBancoMensal && (
          <label className="aideal-field">
            Competência
            <input
              type="month"
              value={competencia}
              onChange={(e) => {
                setCompetencia(e.target.value);
                setCompetenciaStatus({
                  type: 'manual',
                  message: 'Competência ajustada manualmente.',
                });
              }}
            />
            <span className={`aideal-competencia-status is-${competenciaStatus.type}`}>
              {loadingCompetencia ? 'Detectando...' : competenciaStatus.message}
            </span>
          </label>
        )}
      </div>

      {usaBancoMensal && (
        <article
          className="aideal-panel aideal-panel-neutral"
        >
          <div className="aideal-panel-title-row">
            <strong>
              Meses a incluir
            </strong>
            <label className="aideal-check-inline">
              <input type="checkbox" checked={anoTodo} onChange={handleAnoTodo} disabled={gerarTravado} />
              ANO TODO
            </label>
          </div>

          <div className="aideal-month-grid">
            {loadingMeses && <span className="aideal-muted-text">Carregando meses...</span>}

            {!loadingMeses &&
              mesesDisponiveis.map((mes) => (
                <label
                  key={mes}
                  className={`aideal-month-pill ${mesesSelecionados.includes(mes) ? 'is-selected' : ''}`}
                  data-disabled={anoTodo ? 'true' : 'false'}
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
              <span className="aideal-muted-text">
                Sem meses disponíveis no banco para {anoCompetencia || '-'}.
              </span>
            )}
          </div>

          {erroMeses && (
            <div className="aideal-inline-error">
              {erroMeses}
            </div>
          )}

          <p className="aideal-helper-text">
            {anoTodo
              ? 'Modo ativo: geração com todos os meses disponíveis no banco para o ano da competência.'
              : mesesSelecionadosOrdenados.length > 0
                ? `Modo ativo: meses ${mesesSelecionadosOrdenados.map((m) => MESES_LABEL[m - 1]).join(', ')}.`
                : 'Sem seleção manual: usa regra padrão (meses disponíveis até a competência).'}
          </p>
        </article>
      )}

      <div className="aideal-input-drop" onClick={() => fileInputRef.current?.click()}>
        <FileSpreadsheet size={28} aria-hidden="true" />
        <p>
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
          className="aideal-file-input"
        />
      </div>

      {arquivos.length > 0 && (
        <div className="aideal-file-list">
          {arquivos.map((f, i) => (
            <div key={i} className="aideal-file-row">
              <span>
                {f.name} ({(f.size / 1024).toFixed(0)} KB)
              </span>
              <button
                className="aideal-action aideal-action-secondary"
                onClick={() => handleRemover(i)}
                title="Remover arquivo"
              >
                <X size={15} aria-hidden="true" />
                <span>Remover</span>
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
          {loadingValidation ? <Loader2 size={16} aria-hidden="true" /> : <ShieldCheck size={16} aria-hidden="true" />}
          <span>{loadingValidation ? 'Validando...' : 'Validar estrutura'}</span>
        </button>

        {usaBancoMensal && (
          <button
            className="aideal-action aideal-action-primary"
            onClick={handleIngestao}
            disabled={arquivos.length === 0 || gerarTravado}
          >
            {loadingIngestao ? <Loader2 size={16} aria-hidden="true" /> : <Database size={16} aria-hidden="true" />}
            <span>{loadingIngestao ? 'Salvando mês...' : 'Salvar mês no banco'}</span>
          </button>
        )}

        {usaBancoMensal && (
          <button
            className="aideal-action aideal-action-primary"
            onClick={handleGerarDoBanco}
            disabled={gerarTravado}
          >
            {loadingGeracao ? <Loader2 size={16} aria-hidden="true" /> : <CheckCircle2 size={16} aria-hidden="true" />}
            <span>{loadingGeracao ? `Gerando ${fluxoLabel}...` : `Gerar ${fluxoLabel} do banco`}</span>
          </button>
        )}

        {!usaBancoMensal && (
          <button
            className="aideal-action aideal-action-primary"
            onClick={handleGerarFluxo}
            disabled={arquivos.length === 0 || gerarTravado}
          >
            {loadingGeracao ? <Loader2 size={16} aria-hidden="true" /> : <CheckCircle2 size={16} aria-hidden="true" />}
            <span>{loadingGeracao ? 'Gerando Fluxo...' : 'Gerar Fluxo de Caixa'}</span>
          </button>
        )}

        {usaBancoMensal && (
          <button
            className="aideal-action aideal-action-secondary"
            onClick={handleLimparBase}
            disabled={gerarTravado}
            title={`Remove somente os dados ${fluxoLabel} da competência selecionada`}
          >
            {loadingLimpeza ? <Loader2 size={16} aria-hidden="true" /> : <Trash2 size={16} aria-hidden="true" />}
            <span>{loadingLimpeza ? 'Excluindo mês...' : 'Excluir mês selecionado'}</span>
          </button>
        )}

        {downloadUrl && (
          <a
            className="aideal-action aideal-action-secondary aideal-action-link"
            href={downloadUrl}
            target="_blank"
            rel="noreferrer"
          >
            <Download size={16} aria-hidden="true" />
            <span>Baixar resultado</span>
          </a>
        )}

        {gerarTravado && <span className="aideal-loader" aria-hidden="true" />}
      </div>

      {usaBancoMensal && !validacao?.valido && (
        <p className="aideal-helper-text">
          Recomenda-se validar antes da ingestão. A geração final usa somente dados já no banco.
        </p>
      )}

      {arquivoPareceTemplate && (
        <p className="aideal-inline-error">
          O arquivo selecionado parece ser template/saída final. Para processar DRE, use o relatório bruto
          de entrada (ex.: RELATORIO DRE MES 05.xls).
        </p>
      )}

      {usaBancoMensal && processamento?.arquivo_saida && (
        <p className="aideal-helper-text">
          Saída gerada: <strong>{processamento.arquivo_saida}</strong>
        </p>
      )}
    </section>
  );
}
