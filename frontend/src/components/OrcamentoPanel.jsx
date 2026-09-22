import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, MotionConfig, motion, useReducedMotion } from 'framer-motion';
import OrcamentoLoadingScreen from './orcamento/OrcamentoLoadingScreen';
import {
  ArrowUpRight, Calculator, CircleAlert, FilePlus2, GitBranch, History,
  Loader2, Pencil, ScrollText, Send, Sparkles,
} from 'lucide-react';
import { readApiError } from '../auth/authClient';
import { fetchWithCsrfRecovery } from '../auth/csrfFetch';
import { GoFlowWindow } from './goflow-window';
import DfpEditor, { LocationHeaderField } from './orcamento/DfpEditor';
import CatalogoPanel from './orcamento/CatalogoPanel';
import StartDateField from './orcamento/StartDateField';
import TransitionDialog from './orcamento/TransitionDialog';
import {
  CAMPOS_CABECALHO, SITUACOES, applyHeaderChange, applyDfpChange, buildOrcamentoPayload, buildRevisaoPatchPayload,
  createEmptyOrcamentoForm, createRevisaoForm, herdarCabecalho, normalizeOrcamentos,
  resolveOrcamentoCapabilities, resumoCarteira, stripDerivedIdentity, transicoesDisponiveis,
  validateOrcamentoForm, validateRevisaoForm,
} from './orcamentoModel';
import '../styles/orcamento.css';

const TIPOS_EDICAO = Object.freeze({
  criacao: 'Criação', edicao: 'Edição', situacao: 'Mudança de situação',
});

const formatMoney = (value) => Number(value || 0).toLocaleString('pt-BR', {
  style: 'currency', currency: 'BRL', maximumFractionDigits: 0,
});
const formatDate = (iso) => (iso ? new Date(`${iso}T00:00:00`).toLocaleDateString('pt-BR') : null);

function StatusBadge({ revision }) {
  return (
    <span className="orc-badge" data-situacao={revision.situacao} data-vencida={revision.vencida || undefined}>
      {revision.vencida ? 'Vencida' : revision.situacaoLabel}
    </span>
  );
}

function CreateFields({ disabled, errors, form, onChange, onDfpChange }) {
  return (
    <div className="orc-field-grid orc-create-grid">
      {CAMPOS_CABECALHO.map(({ field, label, long, options, type }) => field === 'regiao' ? (
        <LocationHeaderField disabled={disabled} error={errors[field]} form={form} idPrefix="orc-create-location" key={field} onDfpChange={onDfpChange} />
      ) : field === 'dataInicio' ?
        <StartDateField key={field} value={form[field]} disabled={disabled} error={errors[field]} onChange={(value) => onChange(field, value)} /> : (
        <label className={`orc-field ${long ? 'orc-field--wide' : ''}`} key={field}>
          <span>{label}</span>
          {long ? (
            <textarea aria-invalid={Boolean(errors[field])} disabled={disabled} onChange={(event) => onChange(field, event.target.value)} rows="2" value={form[field] ?? ''} />
          ) : options ? (
            <select aria-invalid={Boolean(errors[field])} disabled={disabled} onChange={(event) => onChange(field, event.target.value)} value={form[field] ?? ''}>
              <option value="">Selecione</option>
              {options.map((option) => <option value={option} key={option}>{option}</option>)}
            </select>
          ) : (
            <input aria-invalid={Boolean(errors[field])} disabled={disabled} min={type === 'number' ? '0' : undefined} onChange={(event) => onChange(field, event.target.value)} type={type || 'text'} value={form[field] ?? ''} />
          )}
          {errors[field] && <small role="alert">{errors[field]}</small>}
        </label>
      ))}
    </div>
  );
}

export default function OrcamentoPanel({ apiBase = '/api', csrfToken, onNotify, permissions = [] }) {
  const endpoint = useMemo(() => `${String(apiBase).replace(/\/$/, '')}/orcamento`, [apiBase]);
  const [budgets, setBudgets] = useState([]);
  const [schema, setSchema] = useState(null);
  const [legacySchema, setLegacySchema] = useState(null);
  const [catalogo, setCatalogo] = useState({ funcoes: [], itens: [], custo_administrativo_diario: 0 });
  const [catalogoHistorico, setCatalogoHistorico] = useState([]);
  const [history, setHistory] = useState(null);
  const [createForm, setCreateForm] = useState(createEmptyOrcamentoForm);
  const [createErrors, setCreateErrors] = useState({});
  const [editor, setEditor] = useState(null);
  const [editorForm, setEditorForm] = useState(() => createRevisaoForm(null));
  const [editorErrors, setEditorErrors] = useState({});
  const [transition, setTransition] = useState(null);
  const [loading, setLoading] = useState(true);
  const [initialized, setInitialized] = useState(false);
  const mountedRef = useRef(false);
  const requestsRef = useRef(new Set());
  const loadControllerRef = useRef(null);
  const reducedMotion = useReducedMotion();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const busy = loading || saving;
  const summary = useMemo(() => resumoCarteira(budgets), [budgets]);
  const { canEdit, canTransition } = useMemo(() => resolveOrcamentoCapabilities(permissions), [permissions]);

  const request = useCallback(async (path, { body, method = 'GET', signal } = {}) => {
    const controller = new AbortController();
    requestsRef.current.add(controller);
    const abort = () => controller.abort();
    signal?.addEventListener('abort', abort, { once: true });
    if (signal?.aborted) controller.abort();
    const headers = {};
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (csrfToken && method !== 'GET') headers['X-CSRF-Token'] = csrfToken;
    try {
      const response = await fetchWithCsrfRecovery(`${endpoint}${path}`, {
        body: body === undefined ? undefined : JSON.stringify(body),
        credentials: 'same-origin', headers, method, signal: controller.signal,
      }, { csrfToken, apiBase });
      if (!response.ok) throw new Error(await readApiError(response));
      return await response.json();
    } finally {
      signal?.removeEventListener('abort', abort);
      requestsRef.current.delete(controller);
    }
  }, [csrfToken, endpoint, apiBase]);

  const load = useCallback(async ({ initialize = false } = {}) => {
    loadControllerRef.current?.abort();
    const controller = new AbortController();
    loadControllerRef.current = controller;
    setLoading(true);
    setError('');
    try {
      const options = { signal: controller.signal };
      const [budgetPayload, schemaPayload, legacy, catalog, catalogHistory] = await Promise.all([
        request('/orcamentos', options), request('/schema', options),
        request('/schema?calculation_version=1', options), request('/catalogo', options),
        request('/catalogo/historico', options),
      ]);
      if (!mountedRef.current || controller.signal.aborted) return;
      setBudgets(normalizeOrcamentos(budgetPayload));
      setSchema(schemaPayload);
      setLegacySchema(legacy);
      setCatalogo(catalog);
      setCatalogoHistorico(Array.isArray(catalogHistory?.historico) ? catalogHistory.historico : []);
      setInitialized(true);
      if (initialize) setCreateForm(createEmptyOrcamentoForm(schemaPayload));
    } catch (requestError) {
      if (!mountedRef.current || controller.signal.aborted) return;
      controller.abort();
      setError(requestError.message || 'Não foi possível carregar os orçamentos.');
    } finally {
      if (mountedRef.current && loadControllerRef.current === controller) setLoading(false);
    }
  }, [request]);

  useEffect(() => {
    mountedRef.current = true;
    load({ initialize: true });
    return () => {
      mountedRef.current = false;
      loadControllerRef.current?.abort();
      requestsRef.current.forEach((controller) => controller.abort());
      requestsRef.current.clear();
    };
  }, [load]);

  const runMutation = async (operation, message) => {
    setSaving(true);
    setError('');
    try {
      await operation();
      if (!mountedRef.current) return false;
      await load();
      if (!mountedRef.current) return false;
      onNotify?.({ message, type: 'success' });
      return true;
    } catch (requestError) {
      if (!mountedRef.current || requestError.name === 'AbortError') return false;
      const messageText = requestError.message || 'Não foi possível concluir a operação.';
      setError(messageText);
      onNotify?.({ message: messageText, type: 'error' });
      return false;
    } finally {
      if (mountedRef.current) setSaving(false);
    }
  };

  const updateCreateForm = (field, value) => {
    setCreateForm((current) => applyHeaderChange(current, field, value));
    setCreateErrors((current) => {
      if (!current[field]) return current;
      const { [field]: _removed, ...rest } = current;
      return rest;
    });
  };

  const updateCreateDfp = (dfp) => {
    setCreateForm((current) => applyDfpChange(current, dfp));
    setCreateErrors((current) => {
      if (!current.regiao) return current;
      const { regiao: _removed, ...rest } = current;
      return rest;
    });
  };

  const handleCreate = async (event) => {
    event.preventDefault();
    const errors = validateOrcamentoForm(createForm);
    setCreateErrors(errors);
    if (Object.keys(errors).length) return;
    const created = await runMutation(
      () => request('/orcamentos', { body: buildOrcamentoPayload(createForm), method: 'POST' }),
      'Orçamento criado com a revisão 0 em rascunho.',
    );
    if (created) setCreateForm(createEmptyOrcamentoForm(schema));
  };

  const openEditor = (budget, revision = budget.revisaoAtual, readOnly = false) => {
    if (!revision) return;
    setError('');
    const editable = canEdit && !readOnly && revision.id === budget.revisaoAtual?.id && revision.situacao === 'rascunho';
    setEditor({ budget, canEdit: editable, revision });
    const next = createRevisaoForm(revision, schema);
    setEditorForm({ ...next, dfp: { ...next.dfp, metadata: { ...next.dfp?.metadata,
      cliente_unidade: next.dfp?.metadata?.cliente_unidade || budget.contratante,
    } } });
    setEditorErrors({});
  };

  const handleSaveRevision = async (event) => {
    event.preventDefault();
    if (!editor?.canEdit) return;
    const errors = validateRevisaoForm(editorForm);
    setEditorErrors(errors);
    if (Object.keys(errors).length) return;
    const saved = await runMutation(
      () => request(`/revisoes/${editor.revision.id}`, { body: buildRevisaoPatchPayload(editorForm), method: 'PATCH' }),
      `Revisão ${editor.revision.numero} e snapshot DFP atualizados.`,
    );
    if (saved) setEditor(null);
  };

  const handleNewRevision = (budget) => runMutation(
    () => request(`/orcamentos/${budget.id}/revisoes`, { body: herdarCabecalho(budget.revisaoAtual), method: 'POST' }),
    `Nova revisão criada para ${budget.codigo}; o histórico foi preservado.`,
  );

  const showHistory = async (budget) => {
    try { setHistory({ budget, entries: (await request(`/orcamentos/${budget.id}/historico`)).historico }); }
    catch (err) { setError(err.message); }
  };

  const downloadRevision = async (revision, formato) => {
    try {
      const response = await fetch(`${endpoint}/revisoes/${revision.id}/exportar?formato=${formato}`, { credentials: 'same-origin' });
      if (!response.ok) throw new Error(await readApiError(response));
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = url;
      link.download = response.headers.get('Content-Disposition')?.match(/filename="([^"]+)"/)?.[1] || `orcamento.${formato}`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) { setError(err.message); onNotify?.({ message: err.message, type: 'error' }); }
  };

  const reuseBudget = (id) => {
    const budget = budgets.find((item) => item.id === id);
    if (!budget?.revisaoAtual) return;
    // O código DFP pertence ao orçamento de origem; mantê-lo faz o backend recusar a criação.
    const base = createRevisaoForm(budget.revisaoAtual, schema);
    setCreateForm({ ...base, contratante: budget.contratante, dfp: stripDerivedIdentity(base.dfp) });
  };

  const handleConfirmTransition = async (reason) => {
    if (!transition) return;
    const changed = await runMutation(
      () => request(`/revisoes/${transition.revision.id}/situacao`, {
        body: { motivo: reason, situacao: transition.situation }, method: 'POST',
      }),
      `Revisão ${transition.revision.numero} agora está em “${SITUACOES[transition.situation]}”.`,
    );
    if (changed) setTransition(null);
  };

  return (
    <MotionConfig reducedMotion="user">
    <section className="orc-root" aria-label="Orçamento">
      <AnimatePresence mode="wait" initial={false}>
      {!initialized && loading ? <OrcamentoLoadingScreen key="loading" /> : !initialized ? (
        <motion.div key="initial-error" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <GoFlowWindow className="orc-error-window" icon={CircleAlert} role="alert" title="Não foi possível carregar os orçamentos">
            <p>{error}</p>
            <button className="orc-btn orc-btn--primary" onClick={() => load({ initialize: true })} type="button">Tentar novamente</button>
          </GoFlowWindow>
        </motion.div>
      ) : (
      <motion.div key="content" className="orc-content" aria-busy={busy}
        initial={{ opacity: reducedMotion ? 1 : 0 }} animate={{ opacity: 1 }} transition={{ duration: reducedMotion ? 0 : .24 }}>

      <GoFlowWindow className="orc-hero" eyebrow="AIDEAL · GoFlowOS" icon={Calculator} title="Central de Orçamentos" titleAs="h2">
        <div className="orc-hero-copy">
          <div>
            <p>Componha custos, acompanhe revisões e prepare cada orçamento com clareza.</p>
            <span className="orc-schema-version">{schema?.version ? `Catálogo ${schema.version}` : 'Formação de preços'}</span>
          </div>
          <dl className="orc-metrics">
            <div><dt>Carteira</dt><dd>{summary.total}</dd></div>
            <div><dt>Em curso</dt><dd>{summary.emAndamento}</dd></div>
            <div><dt>Prontos</dt><dd>{summary.prontos}</dd></div>
            <div><dt>Faturamento</dt><dd>{formatMoney(summary.totalFaturamento)}</dd></div>
          </dl>
        </div>
      </GoFlowWindow>

      {canEdit ? (
        <GoFlowWindow className="orc-create-window" eyebrow="Novo orçamento" icon={FilePlus2} title="Criar orçamento">
          <label className="orc-field">Preencher a partir de orçamento existente<select defaultValue="" onChange={(e) => reuseBudget(e.target.value)} disabled={busy}>
            <option value="">Selecione para reaproveitar dados</option>{budgets.map((b) => <option key={b.id} value={b.id}>{b.codigo} — {b.contratante}</option>)}
          </select></label>
          <form onSubmit={handleCreate}>
            <CreateFields disabled={busy} errors={createErrors} form={createForm} onChange={updateCreateForm} onDfpChange={updateCreateDfp} />
            <div className="orc-create-actions">
              <p>Comece pela contratante. Você poderá completar os detalhes no editor.</p>
              <button className="orc-btn orc-btn--primary" disabled={busy} type="submit">
                {saving ? <Loader2 className="orc-spin" aria-hidden="true" /> : <Sparkles aria-hidden="true" />} Criar orçamento
              </button>
            </div>
          </form>
        </GoFlowWindow>
      ) : (
        <GoFlowWindow className="orc-readonly-window" icon={History} title="Acesso somente leitura">
          <p>Você pode consultar cada snapshot e o histórico, sem alterar os dados.</p>
        </GoFlowWindow>
      )}

      {canEdit && <GoFlowWindow title="Cadastros do orçamento"><CatalogoPanel catalogo={catalogo} historico={catalogoHistorico} busy={busy}
        onSave={(data) => runMutation(() => request('/catalogo', { body: data, method: 'POST' }), 'Catálogo salvo.')} /></GoFlowWindow>}

      {history && <GoFlowWindow title={`Histórico de edição — ${history.budget.codigo}`}>
        <button className="orc-btn" type="button" onClick={() => setHistory(null)}>Fechar histórico</button>
        {history.entries.length === 0 ? <p>Sem eventos registrados para esta revisão anterior à atualização.</p> : history.entries.map((entry, index) => {
          const revisao = history.budget.revisoes.find((item) => item.id === entry.revisao_id);
          const alterados = Object.keys(entry.depois || {}).filter((key) => JSON.stringify(entry.antes?.[key]) !== JSON.stringify(entry.depois?.[key]));
          return (
            <details key={entry.id || index}>
              <summary>{`R${revisao?.numero ?? '?'}`} · {TIPOS_EDICAO[entry.tipo] || entry.tipo} · {new Date(entry.created_at).toLocaleString('pt-BR')} · {entry.responsavel_user_id}</summary>
              <p>Campos alterados: {alterados.length ? alterados.join(', ') : 'nenhum'}</p>
            </details>
          );
        })}
      </GoFlowWindow>}

      {error && <GoFlowWindow className="orc-error-window" icon={CircleAlert} role="alert" title="Não foi possível concluir"><p>{error}</p><button className="orc-btn" disabled={busy} onClick={() => load()} type="button">Tentar novamente</button></GoFlowWindow>}

      <GoFlowWindow className="orc-portfolio-title" eyebrow="Seus orçamentos" icon={ScrollText} title="Carteira">
        <p>{loading ? 'Atualizando carteira…' : `${budgets.length} orçamento(s) disponível(is)`}</p>
      </GoFlowWindow>

      {budgets.length === 0 && <GoFlowWindow className="orc-empty" icon={Calculator} title="Carteira vazia"><p>Crie o primeiro orçamento. Ele receberá o código ORC-0001.</p></GoFlowWindow>}

      {budgets.length > 0 && (
        <ul className="orc-portfolio">
          {budgets.map((budget, index) => {
            const current = budget.revisaoAtual;
            const transitions = current ? transicoesDisponiveis(current.situacao) : [];
            return (
              <GoFlowWindow activationLabel={`Abrir ${budget.codigo}, ${budget.contratante}`} as="li" className="orc-card" eyebrow={`${budget.codigo}-R${current?.numero ?? 0}`} icon={Calculator} interactive key={budget.id} onActivate={() => openEditor(budget)} motionIndex={index} title={budget.contratante}>
                <div className="orc-card-summary">
                  {current && <StatusBadge revision={current} />}
                  <strong>{formatMoney(budget.dfpSummary.precoTotalFaturamento)}</strong>
                  <span>preço de faturamento</span>
                </div>
                <dl className="orc-card-meta">
                  <div><dt>Revisão atual</dt><dd>{current?.numero ?? '—'}</dd></div>
                  <div><dt>Modalidade</dt><dd>{current?.modalidade || 'Pendente'}</dd></div>
                  <div><dt>Região da Obra</dt><dd>{current?.regiao || 'Pendente'}</dd></div>
                  <div><dt>Validade</dt><dd>{formatDate(current?.validoAte) || 'Ainda não emitido'}</dd></div>
                </dl>
                {budget.cabecalhoPendente.length > 0 && <p className="orc-pending">Cabeçalho pendente: {budget.cabecalhoPendente.join(', ')}.</p>}
                <div className="orc-history" aria-label={`Histórico de ${budget.codigo}`} onClick={(event) => event.stopPropagation()}>
                  <span><History aria-hidden="true" /> Histórico somente leitura</span>
                  <div>
                    {budget.revisoes.map((revision) => revision.id === current?.id ? (
                      <span className="orc-revision-chip is-current" key={revision.id}>r{revision.numero}</span>
                    ) : (
                      <button aria-label={`Abrir revisão ${revision.numero} somente leitura`} className="orc-revision-chip" key={revision.id} onClick={() => openEditor(budget, revision, true)} type="button">r{revision.numero}</button>
                    ))}
                  </div>
                </div>
                <div className="orc-card-actions" onClick={(event) => event.stopPropagation()}>
                  <button className="orc-btn" type="button" onClick={() => showHistory(budget)}>Histórico de edição</button>
                  {current && ['docx', 'pdf'].map((format) => <button key={format} className="orc-btn" type="button" onClick={() => downloadRevision(current, format)}>Exportar {format.toUpperCase()}</button>)}
                  {canEdit && current?.situacao === 'rascunho' && <button className="orc-btn" disabled={busy} onClick={() => openEditor(budget)} type="button"><Pencil aria-hidden="true" />{budget.cabecalhoPendente.length ? 'Completar orçamento' : 'Editar orçamento'}</button>}
                  {canEdit && <button className="orc-btn" disabled={busy} onClick={() => handleNewRevision(budget)} type="button"><GitBranch aria-hidden="true" /> Nova revisão</button>}
                  {canTransition && current && transitions.map((situation) => (
                    <button className="orc-btn" disabled={busy} key={situation} onClick={() => { setError(''); setTransition({ revision: current, situation }); }} type="button">
                      {situation === 'emitido' ? <Send aria-hidden="true" /> : <ArrowUpRight aria-hidden="true" />}{SITUACOES[situation]}
                    </button>
                  ))}
                </div>
              </GoFlowWindow>
            );
          })}
        </ul>
      )}

      </motion.div>
      )}
      </AnimatePresence>

      <AnimatePresence>
      {editor && schema && (
        <DfpEditor key={editor.revision.id} budget={editor.budget} catalogo={catalogo} onExport={(format) => downloadRevision(editor.revision, format)} busy={saving} canEdit={editor.canEdit} errors={editorErrors} form={editorForm} onClose={() => setEditor(null)} onDfpChange={(dfp) => setEditorForm((current) => applyDfpChange(current, dfp))} onHeaderChange={(field, value) => {
          setEditorForm((current) => applyHeaderChange(current, field, value));
          setEditorErrors((current) => {
            if (!current[field]) return current;
            const { [field]: _removed, ...rest } = current;
            return rest;
          });
        }} serverError={error} onSave={handleSaveRevision} revision={editor.revision} schema={editorForm.dfp?.calculation_version === 2 ? schema : legacySchema || schema} />
      )}

      </AnimatePresence>
      <AnimatePresence>
      {transition && <TransitionDialog key={transition.revision.id} busy={saving} label={SITUACOES[transition.situation]} onCancel={() => setTransition(null)} onConfirm={handleConfirmTransition} revision={transition.revision} serverError={error} />}
      </AnimatePresence>
    </section>
    </MotionConfig>
  );
}
