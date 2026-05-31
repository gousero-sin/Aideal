import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  CalendarDays,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Database,
  Download,
  FileSpreadsheet,
  Loader2,
  ShieldCheck,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react';

const pad = (value) => String(value).padStart(2, '0');

const MESES_LABEL = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

const hoje = () => new Date();

const competenciaParaExibicao = (ano, mes) => {
  if (!ano || !mes) return '';
  return `${pad(mes)}/${ano}`;
};

export default function UploadPanel({
  fluxo,
  apiBase,
  onValidation,
  onProcess,
  processamento,
  validacao,
  onBusyChange,
  statusSlot = null,
}) {
  const [arquivos, setArquivos] = useState([]);
  const [loadingValidation, setLoadingValidation] = useState(false);
  const [loadingIngestao, setLoadingIngestao] = useState(false);
  const [loadingGeracao, setLoadingGeracao] = useState(false);
  const [loadingLimpeza, setLoadingLimpeza] = useState(false);
  const [loadingCompetencia, setLoadingCompetencia] = useState(false);
  const [ano, setAno] = useState(() => hoje().getFullYear());
  const [mesAtivo, setMesAtivo] = useState(() => hoje().getMonth() + 1);
  const [anoTodo, setAnoTodo] = useState(false);
  const [competenciaStatus, setCompetenciaStatus] = useState({
    type: 'idle',
    message: 'Selecione um arquivo para detectar a competência automaticamente.',
  });
  const [mesesDisponiveis, setMesesDisponiveis] = useState([]);
  const [loadingMeses, setLoadingMeses] = useState(false);
  const [erroMeses, setErroMeses] = useState(null);
  const fileInputRef = useRef(null);
  const competenciaRequestRef = useRef(0);

  const isFluxoCaixa = fluxo === 'fluxo_caixa';
  const isMultiple = isFluxoCaixa;
  const isDre = fluxo === 'dre';
  const fluxoLabel = isDre ? 'DRE' : 'Fluxo de Caixa';
  const anoAtual = hoje().getFullYear();
  const competenciaLabelCurto = `${MESES_LABEL[mesAtivo - 1]} ${ano}`;
  const mesAtivoSalvo = mesesDisponiveis.includes(mesAtivo);
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

  const anosDisponiveis = useMemo(() => {
    const base = new Set([ano, anoAtual, anoAtual - 1, anoAtual - 2, anoAtual + 1]);
    return [...base].sort((a, b) => b - a);
  }, [ano, anoAtual]);

  const carregarMesesDisponiveis = async (anoRef) => {
    if (!anoRef) return;
    setLoadingMeses(true);
    setErroMeses(null);
    try {
      const recurso = isDre ? 'dre' : 'fluxo_caixa';
      const response = await fetch(`${apiBase}/${recurso}/ingestoes?ano=${anoRef}&limit=500`, {
        credentials: 'same-origin',
      });
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
            if (Number(anoStr) !== anoRef) return null;
            const m = Number(mesStr);
            if (Number.isNaN(m) || m < 1 || m > 12) return null;
            return m;
          })
          .filter((m) => m != null),
      )].sort((a, b) => a - b);

      setMesesDisponiveis(meses);
    } catch (err) {
      setMesesDisponiveis([]);
      setErroMeses(err.message);
    } finally {
      setLoadingMeses(false);
    }
  };

  useEffect(() => {
    carregarMesesDisponiveis(ano);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBase, isDre, ano]);

  const handleSelecionarMes = (mes) => {
    if (gerarTravado) return;
    setMesAtivo(mes);
    setCompetenciaStatus({
      type: 'manual',
      message: `Competência ativa: ${competenciaParaExibicao(ano, mes)}.`,
    });
  };

  const handleAnoTodo = () => setAnoTodo((prev) => !prev);

  const navegarAno = (delta) => {
    if (gerarTravado) return;
    setAno((prev) => prev + delta);
  };

  const detectarCompetencia = async (files) => {
    if (files.length === 0) {
      setCompetenciaStatus({
        type: 'idle',
        message: 'Selecione um arquivo para detectar a competência automaticamente.',
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
        credentials: 'same-origin',
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err?.detail || 'Não foi possível detectar a competência.');
      }

      const payload = await response.json();
      if (competenciaRequestRef.current !== requestId) return;

      if (payload?.detectado && payload?.competencia_input) {
        const [anoStr, mesStr] = String(payload.competencia_input).split('-');
        const anoDet = Number(anoStr);
        const mesDet = Number(mesStr);
        if (!Number.isNaN(anoDet)) setAno(anoDet);
        if (!Number.isNaN(mesDet) && mesDet >= 1 && mesDet <= 12) setMesAtivo(mesDet);
        setCompetenciaStatus({
          type: 'success',
          message: `Competência detectada: ${payload.competencia}. Ajuste pelas flags se precisar.`,
        });
        return;
      }

      setCompetenciaStatus({
        type: 'warning',
        message: payload?.message || 'Competência não detectada. Ajuste pelas flags.',
      });
    } catch (err) {
      if (competenciaRequestRef.current !== requestId) return;
      setCompetenciaStatus({
        type: 'warning',
        message: `${err.message} Ajuste pelas flags.`,
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
          credentials: 'same-origin',
          body: formData,
        });
      } else {
        const formData = new FormData();
        formData.append('arquivo', arquivos[0]);
        if (isDre) {
          formData.append('competencia', competenciaParaExibicao(ano, mesAtivo));
          formData.append('modo_cumulativo', 'false');
        }
        response = await fetch(`${apiBase}/validar/${fluxo}`, {
          method: 'POST',
          credentials: 'same-origin',
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
    if (arquivos.length === 0) return;

    setLoadingIngestao(true);
    try {
      const formData = new FormData();
      if (isDre) {
        formData.append('arquivo', arquivos[0]);
      } else {
        arquivos.forEach((f) => formData.append('arquivos', f));
      }
      formData.append('competencia', competenciaParaExibicao(ano, mesAtivo));
      formData.append('replace', 'true');

      const recurso = isDre ? 'dre' : 'fluxo_caixa';
      const response = await fetch(`${apiBase}/${recurso}/ingestoes`, {
        method: 'POST',
        credentials: 'same-origin',
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
      await carregarMesesDisponiveis(ano);

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
      formData.append('competencia', competenciaParaExibicao(ano, mesAtivo));
      formData.append('ano_todo', String(anoTodo));
      if (!anoTodo) {
        formData.append('meses_incluir', String(mesAtivo));
      }

      const recurso = isDre ? 'dre' : 'fluxo_caixa';
      const response = await fetch(`${apiBase}/${recurso}/gerar`, {
        method: 'POST',
        credentials: 'same-origin',
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

  const handleLimparBase = async () => {
    const competenciaLabel = competenciaParaExibicao(ano, mesAtivo);
    const confirmado = window.confirm(
      `Excluir somente os dados de ${competenciaLabel} em ${fluxoLabel}? Os demais meses serão preservados.`,
    );
    if (!confirmado) return;

    setLoadingLimpeza(true);
    try {
      const recurso = isDre ? 'dre' : 'fluxo_caixa';
      const formData = new FormData();
      formData.append('ano', String(ano));
      formData.append('mes', String(mesAtivo));
      formData.append('confirmar', 'true');

      const response = await fetch(`${apiBase}/${recurso}/admin/limpar`, {
        method: 'POST',
        credentials: 'same-origin',
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err?.detail || `Erro ao excluir mês ${fluxoLabel}`);
      }

      const result = await response.json();
      await carregarMesesDisponiveis(ano);
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
        message: 'Selecione um arquivo para detectar a competência automaticamente.',
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

  const escopoGeracao = anoTodo
    ? `Geração: todos os meses salvos de ${ano}.`
    : `Geração: apenas ${competenciaLabelCurto}.`;

  return (
    <div className="aideal-admin-grid">
      <aside className="aideal-admin-sidebar">
        <div className="aideal-period-block">
          <header className="aideal-period-head">
            <span className="aideal-period-icon">
              <CalendarDays size={16} aria-hidden="true" />
            </span>
            <div>
              <h3>Período</h3>
              <p>Selecione ano e mês ativo</p>
            </div>
          </header>

          <div className="aideal-year-stepper">
            <button
              type="button"
              onClick={() => navegarAno(-1)}
              disabled={gerarTravado}
              aria-label="Ano anterior"
            >
              <ChevronLeft size={18} aria-hidden="true" />
            </button>
            <label className="aideal-year-pick">
              <select
                value={ano}
                onChange={(event) => setAno(Number(event.target.value))}
                disabled={gerarTravado}
                aria-label="Ano"
              >
                {anosDisponiveis.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
              <strong>{ano}</strong>
            </label>
            <button
              type="button"
              onClick={() => navegarAno(1)}
              disabled={gerarTravado}
              aria-label="Próximo ano"
            >
              <ChevronRight size={18} aria-hidden="true" />
            </button>
          </div>

          <div className="aideal-month-flags" role="group" aria-label="Meses">
            {MESES_LABEL.map((label, index) => {
              const mes = index + 1;
              const salvo = mesesDisponiveis.includes(mes);
              const ativo = mes === mesAtivo;
              return (
                <button
                  key={mes}
                  type="button"
                  className={`aideal-month-flag ${ativo ? 'is-active' : ''}`}
                  data-saved={salvo ? 'true' : 'false'}
                  onClick={() => handleSelecionarMes(mes)}
                  disabled={gerarTravado}
                  aria-pressed={ativo}
                  style={{ '--flag-index': index }}
                  title={salvo ? `${label}/${ano} — salvo no banco` : `${label}/${ano} — sem dados`}
                >
                  <span className="aideal-month-flag-label">{label}</span>
                  <span className="aideal-month-flag-dot" aria-hidden="true" />
                </button>
              );
            })}
          </div>

          <label className={`aideal-anotodo-toggle ${anoTodo ? 'is-on' : ''}`}>
            <input type="checkbox" checked={anoTodo} onChange={handleAnoTodo} disabled={gerarTravado} />
            <span className="aideal-anotodo-track" aria-hidden="true">
              <span className="aideal-anotodo-thumb" />
            </span>
            <span className="aideal-anotodo-text">
              <strong>Ano todo</strong>
              <em>Consolida todos os meses salvos de {ano}</em>
            </span>
          </label>
        </div>

        <div className="aideal-bank-status">
          <div className="aideal-bank-status-head">
            <span>Banco · {fluxoLabel}</span>
            <strong>
              {loadingMeses ? '...' : `${mesesDisponiveis.length}`}<i>/12</i>
            </strong>
          </div>
          <div className="aideal-bank-status-bar" aria-hidden="true">
            <span style={{ width: `${(mesesDisponiveis.length / 12) * 100}%` }} />
          </div>
          <p>
            {loadingMeses
              ? 'Carregando meses salvos...'
              : mesesDisponiveis.length === 0
                ? `Nenhum mês salvo em ${ano}.`
                : `Salvos: ${mesesDisponiveis.map((m) => MESES_LABEL[m - 1]).join(', ')}.`}
          </p>
          {erroMeses && <p className="aideal-inline-error">{erroMeses}</p>}
        </div>
      </aside>

      <section className="aideal-admin-main">
        <header className="aideal-workspace-head">
          <div>
            <h3>{fluxoLabel} · ingestão e geração</h3>
            <p>
              {isDre
                ? '1) Validar  →  2) Salvar mês no banco  →  3) Gerar DRE.'
                : '1) Validar  →  2) Salvar lote mensal  →  3) Gerar consolidado.'}
            </p>
          </div>
          <div className="aideal-competencia-chip" data-saved={mesAtivoSalvo ? 'true' : 'false'}>
            <CalendarDays size={15} aria-hidden="true" />
            <span>{competenciaLabelCurto}</span>
            <em>{mesAtivoSalvo ? 'salvo' : 'novo'}</em>
          </div>
        </header>

        <span className={`aideal-competencia-status is-${competenciaStatus.type}`}>
          {loadingCompetencia ? 'Detectando competência...' : competenciaStatus.message}
        </span>

        <div
          className="aideal-input-drop"
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click();
          }}
        >
          <FileSpreadsheet size={28} aria-hidden="true" />
          <p>
            {isMultiple
              ? 'Clique para selecionar arquivos bancários (.xls, .xlsx)'
              : 'Clique para selecionar arquivo DRE (.xls, .xlsx)'}
          </p>
          <span className="aideal-drop-hint">A competência é detectada automaticamente</span>
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

          <button
            className="aideal-action aideal-action-primary"
            onClick={handleIngestao}
            disabled={arquivos.length === 0 || gerarTravado}
          >
            {loadingIngestao ? <Loader2 size={16} aria-hidden="true" /> : <Database size={16} aria-hidden="true" />}
            <span>{loadingIngestao ? 'Salvando mês...' : 'Salvar mês no banco'}</span>
          </button>

          <button
            className="aideal-action aideal-action-primary"
            onClick={handleGerarDoBanco}
            disabled={gerarTravado}
          >
            {loadingGeracao ? <Loader2 size={16} aria-hidden="true" /> : <CheckCircle2 size={16} aria-hidden="true" />}
            <span>{loadingGeracao ? `Gerando ${fluxoLabel}...` : `Gerar ${fluxoLabel}`}</span>
          </button>

          <button
            className="aideal-action aideal-action-secondary"
            onClick={handleLimparBase}
            disabled={gerarTravado}
            title={`Remove somente os dados ${fluxoLabel} da competência ativa`}
          >
            {loadingLimpeza ? <Loader2 size={16} aria-hidden="true" /> : <Trash2 size={16} aria-hidden="true" />}
            <span>{loadingLimpeza ? 'Excluindo mês...' : 'Excluir mês ativo'}</span>
          </button>

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

        <p className="aideal-scope-line">
          <Sparkles size={13} aria-hidden="true" />
          {escopoGeracao}
        </p>

        {!validacao?.valido && (
          <p className="aideal-helper-text">
            Recomenda-se validar antes da ingestão. A geração usa somente dados já salvos no banco.
          </p>
        )}

        {arquivoPareceTemplate && (
          <p className="aideal-inline-error">
            O arquivo selecionado parece ser template/saída final. Para processar DRE, use o relatório bruto
            de entrada (ex.: RELATORIO DRE MES 05.xls).
          </p>
        )}

        {processamento?.arquivo_saida && (
          <p className="aideal-helper-text">
            Saída gerada: <strong>{processamento.arquivo_saida}</strong>
          </p>
        )}

        {statusSlot}
      </section>
    </div>
  );
}
