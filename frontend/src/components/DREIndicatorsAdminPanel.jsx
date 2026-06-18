import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  CalendarDays,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Database,
  Loader2,
  Receipt,
  Save,
} from 'lucide-react';

const pad = (value) => String(value).padStart(2, '0');
const MESES_LABEL = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

const hoje = () => new Date();

const emptyForm = {
  contas_pagar: '0',
  contas_receber: '0',
  total_impostos_retidos_acima_meta: '0',
  total_impostos_retidos: '0',
};

const fields = [
  {
    key: 'contas_pagar',
    label: 'Contas a Pagar',
    hint: 'Campo mensal editável; usado no NCG do DRE do mês anterior',
  },
  {
    key: 'contas_receber',
    label: 'Contas a Receber',
    hint: 'Campo mensal editável; usado no NCG do DRE do mês anterior',
  },
  {
    key: 'total_impostos_retidos_acima_meta',
    label: 'Total de Impostos Retidos Acima da Meta',
    hint: 'Campo mensal editável; base do IIRRL no mesmo mês do DRE',
  },
  {
    key: 'total_impostos_retidos',
    label: 'Total de Impostos Retidos',
    hint: 'Campo mensal editável; base do ITMIR no mesmo mês do DRE',
  },
];

const competenciaParaExibicao = (ano, mes) => `${pad(mes)}/${ano}`;

const inputValue = (value) => {
  const numberValue = Number(value || 0);
  if (!Number.isFinite(numberValue)) return '0';
  return String(numberValue);
};

const parseMoney = (key, value) => {
  const normalized = String(value || '0').replace(',', '.');
  const parsed = Number(normalized);
  if (!Number.isFinite(parsed) || parsed < 0) {
    const field = fields.find((item) => item.key === key);
    throw new Error(`${field?.label || key} deve ser maior ou igual a 0.`);
  }
  return parsed;
};

export default function DREIndicatorsAdminPanel({ apiBase, onNotify, onBusyChange }) {
  const [ano, setAno] = useState(() => hoje().getFullYear());
  const [mesAtivo, setMesAtivo] = useState(() => hoje().getMonth() + 1);
  const [form, setForm] = useState(emptyForm);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [recordInfo, setRecordInfo] = useState({ existe: false, updatedAt: null });
  const requestIdRef = useRef(0);
  const loadingRequestIdRef = useRef(0);
  const anoAtual = hoje().getFullYear();
  const busy = loading || saving;
  const competenciaLabel = competenciaParaExibicao(ano, mesAtivo);

  const anosDisponiveis = useMemo(() => {
    const base = new Set([ano, anoAtual, anoAtual - 1, anoAtual - 2, anoAtual + 1]);
    return [...base].sort((a, b) => b - a);
  }, [ano, anoAtual]);

  useEffect(() => {
    onBusyChange?.(busy);
  }, [busy, onBusyChange]);

  useEffect(() => () => onBusyChange?.(false), [onBusyChange]);

  const carregarIndicadores = async (anoRef = ano, mesRef = mesAtivo, options = {}) => {
    const mostrarLoading = options.mostrarLoading ?? true;
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    if (mostrarLoading) {
      loadingRequestIdRef.current = requestId;
      setLoading(true);
    }
    setError(null);
    try {
      const response = await fetch(
        `${apiBase}/dre/admin/indicadores?ano=${anoRef}&mes=${mesRef}`,
        { credentials: 'same-origin' },
      );
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail?.detail || 'Erro ao consultar indicadores DRE.');
      }
      const payload = await response.json();
      if (requestId !== requestIdRef.current) return;
      const indicadores = payload?.indicadores || {};
      setForm({
        contas_pagar: inputValue(indicadores.contas_pagar),
        contas_receber: inputValue(indicadores.contas_receber),
        total_impostos_retidos_acima_meta: inputValue(indicadores.total_impostos_retidos_acima_meta),
        total_impostos_retidos: inputValue(indicadores.total_impostos_retidos),
      });
      setRecordInfo({
        existe: Boolean(payload?.existe),
        updatedAt: payload?.updated_at || null,
      });
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      setError(err.message);
      onNotify?.({ type: 'error', message: err.message });
    } finally {
      if (mostrarLoading && loadingRequestIdRef.current === requestId) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    carregarIndicadores(ano, mesAtivo, { mostrarLoading: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBase, ano, mesAtivo]);

  const navegarAno = (delta) => {
    if (busy) return;
    setAno((prev) => prev + delta);
  };

  const handleFieldChange = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (busy) return;

    setSaving(true);
    setError(null);
    try {
      const valores = fields.reduce((acc, field) => ({
        ...acc,
        [field.key]: parseMoney(field.key, form[field.key]),
      }), {});
      const formData = new FormData();
      formData.append('ano', String(ano));
      formData.append('mes', String(mesAtivo));
      fields.forEach((field) => formData.append(field.key, String(valores[field.key])));
      formData.append('confirmar', 'true');

      const response = await fetch(`${apiBase}/dre/admin/indicadores`, {
        method: 'POST',
        credentials: 'same-origin',
        body: formData,
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail?.detail || 'Erro ao salvar indicadores DRE.');
      }
      const payload = await response.json();
      const indicadores = payload?.indicadores || {};
      setForm({
        contas_pagar: inputValue(indicadores.contas_pagar),
        contas_receber: inputValue(indicadores.contas_receber),
        total_impostos_retidos_acima_meta: inputValue(indicadores.total_impostos_retidos_acima_meta),
        total_impostos_retidos: inputValue(indicadores.total_impostos_retidos),
      });
      setRecordInfo({ existe: true, updatedAt: payload?.updated_at || null });
      onNotify?.({ type: 'success', message: `Indicadores DRE ${competenciaLabel} salvos.` });
    } catch (err) {
      setError(err.message);
      onNotify?.({ type: 'error', message: err.message });
    } finally {
      setSaving(false);
    }
  };

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
              <p>Selecione ano e mês para consulta</p>
            </div>
          </header>

          <div className="aideal-year-stepper">
            <button type="button" onClick={() => navegarAno(-1)} disabled={busy} aria-label="Ano anterior">
              <ChevronLeft size={18} aria-hidden="true" />
            </button>
            <label className="aideal-year-pick">
              <select
                value={ano}
                onChange={(event) => setAno(Number(event.target.value))}
                disabled={busy}
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
            <button type="button" onClick={() => navegarAno(1)} disabled={busy} aria-label="Próximo ano">
              <ChevronRight size={18} aria-hidden="true" />
            </button>
          </div>

          <div className="aideal-month-flags" role="group" aria-label="Meses">
            {MESES_LABEL.map((label, index) => {
              const mes = index + 1;
              const ativo = mes === mesAtivo;
              return (
                <button
                  key={mes}
                  type="button"
                  className={`aideal-month-flag ${ativo ? 'is-active' : ''}`}
                  data-saved={ativo && recordInfo.existe ? 'true' : 'false'}
                  onClick={() => setMesAtivo(mes)}
                  disabled={busy}
                  aria-pressed={ativo}
                  style={{ '--flag-index': index }}
                  title={`${label}/${ano}`}
                >
                  <span className="aideal-month-flag-label">{label}</span>
                  <span className="aideal-month-flag-dot" aria-hidden="true" />
                </button>
              );
            })}
          </div>
        </div>

        <div className="aideal-bank-status">
          <div className="aideal-bank-status-head">
            <span>ADM · Indicadores</span>
            <strong>{recordInfo.existe ? 'OK' : '0'}</strong>
          </div>
          <div className="aideal-bank-status-bar" aria-hidden="true">
            <span style={{ width: recordInfo.existe ? '100%' : '0%' }} />
          </div>
          <p>
            {recordInfo.existe
              ? `Registro disponível para ${competenciaLabel}.`
              : `Sem registro salvo para ${competenciaLabel}.`}
          </p>
        </div>
      </aside>

      <form className="aideal-admin-main aideal-indicators-form" onSubmit={handleSubmit}>
        <header className="aideal-workspace-head">
          <div>
            <h3>DRE · indicadores manuais</h3>
            <p>Consulta e atualização dos quatro campos mensais usados pelos indicadores.</p>
          </div>
          <div className="aideal-competencia-chip" data-saved={recordInfo.existe ? 'true' : 'false'}>
            <CalendarDays size={15} aria-hidden="true" />
            <span>{competenciaLabel}</span>
            <em>{recordInfo.existe ? 'salvo' : 'novo'}</em>
          </div>
        </header>

        <span className={`aideal-competencia-status is-${recordInfo.existe ? 'success' : 'manual'}`}>
          {loading
            ? 'Consultando indicadores...'
            : recordInfo.updatedAt
              ? `Última atualização: ${new Date(recordInfo.updatedAt).toLocaleString('pt-BR')}.`
              : 'Preencha os valores mensais e confirme o salvamento.'}
        </span>

        <div className="aideal-indicator-field-grid">
          {fields.map((field) => (
            <label key={field.key} className="aideal-field aideal-money-field">
              {field.label}
              <input
                type="number"
                min="0"
                step="0.01"
                inputMode="decimal"
                value={form[field.key]}
                onChange={(event) => handleFieldChange(field.key, event.target.value)}
                disabled={busy}
              />
              <em>{field.hint}</em>
            </label>
          ))}
        </div>

        <div className="aideal-indicator-summary">
          <span>
            <Database size={15} aria-hidden="true" />
            {recordInfo.existe ? 'Consulta carregada do banco' : 'Novo registro mensal'}
          </span>
          <span>
            <Receipt size={15} aria-hidden="true" />
            Fonte dos objetivos de imposto e NCG
          </span>
        </div>

        {error && <p className="aideal-inline-error">{error}</p>}

        <div className="aideal-action-row">
          <button className="aideal-action aideal-action-primary" type="submit" disabled={busy}>
            {saving ? <Loader2 size={16} aria-hidden="true" /> : <Save size={16} aria-hidden="true" />}
            <span>{saving ? 'Salvando...' : 'Confirmar e salvar'}</span>
          </button>
          <button
            className="aideal-action aideal-action-secondary"
            type="button"
            onClick={() => carregarIndicadores(ano, mesAtivo)}
            disabled={busy}
          >
            {loading ? <Loader2 size={16} aria-hidden="true" /> : <CheckCircle2 size={16} aria-hidden="true" />}
            <span>{loading ? 'Consultando...' : 'Consultar mês'}</span>
          </button>
        </div>
      </form>
    </div>
  );
}
