import React, { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, MotionConfig, motion, useReducedMotion } from 'framer-motion';
import '@fontsource-variable/archivo/wdth.css';
import '../styles/orcamento.css';
import OrcamentoLoadingScreen from './orcamento/OrcamentoLoadingScreen';
import { Calculator, CircleAlert, GitBranch, History, Plus, SearchX, SlidersHorizontal, X } from 'lucide-react';
import { readApiError } from '../auth/authClient';
import { fetchWithCsrfRecovery } from '../auth/csrfFetch';
import { GoFlowWindow } from './goflow-window';
import DfpEditor from './orcamento/DfpEditor';
import BudgetCard from './orcamento/BudgetCard';
import CatalogoPanel from './orcamento/CatalogoPanel';
import ConfirmDialog from './orcamento/ConfirmDialog';
import CreateBudgetDialog from './orcamento/CreateBudgetDialog';
import OrcamentoDialog from './orcamento/OrcamentoDialog';
import PortfolioHeader from './orcamento/PortfolioHeader';
import HistoryDrawer from './orcamento/HistoryDrawer';
import OrcamentoToast from './orcamento/OrcamentoToast';
import PortfolioToolbar from './orcamento/PortfolioToolbar';
import TransitionDialog from './orcamento/TransitionDialog';
import {
  SITUACOES, applyHeaderChange, applyDfpChange, buildOrcamentoPayload, buildRevisaoPatchPayload,
  contarFiltrosCarteira, createEmptyOrcamentoForm, createRevisaoForm, filtrarCarteira, herdarCabecalho, normalizeOrcamentos,
  resolveOrcamentoCapabilities, resumoCarteira, stripDerivedIdentity, validateOrcamentoForm, validateRevisaoForm,
} from './orcamentoModel';

const HH_IMPORT_MAX_BYTES = 5 * 1024 * 1024;
const DEFAULT_PORTFOLIO_VIEW = Object.freeze({ query: '', filter: 'todos', order: 'recentes' });

function PortfolioSkeleton({ count = 2 }) {
  return Array.from({ length: count }, (_, index) => (
    <li aria-hidden="true" className="goflow-window orc-card-skeleton" key={`skeleton-${index}`}>
      <span className="orc-skeleton orc-skeleton--title" />
      <span className="orc-skeleton orc-skeleton--line" />
      <span className="orc-skeleton orc-skeleton--block" />
    </li>
  ));
}

export default function OrcamentoPanel({ apiBase = '/api', csrfToken, currentUserId, permissions = [] }) {
  const endpoint = useMemo(() => `${String(apiBase).replace(/\/$/, '')}/orcamento`, [apiBase]);
  const [budgets, setBudgets] = useState([]);
  const [schema, setSchema] = useState(null);
  const [legacySchema, setLegacySchema] = useState(null);
  const [catalogo, setCatalogo] = useState({ funcoes: [], itens: [], custo_administrativo_diario: 0 });
  const [catalogoHistorico, setCatalogoHistorico] = useState([]);
  const [history, setHistory] = useState(null);
  const [createForm, setCreateForm] = useState(createEmptyOrcamentoForm);
  const [createErrors, setCreateErrors] = useState({});
  const [reuseId, setReuseId] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [catalogOpen, setCatalogOpen] = useState(false);
  const [catalogDirty, setCatalogDirty] = useState(false);
  const [confirmCatalogDiscard, setConfirmCatalogDiscard] = useState(false);
  const [editor, setEditor] = useState(null);
  const [editorForm, setEditorForm] = useState(() => createRevisaoForm(null));
  const [editorErrors, setEditorErrors] = useState({});
  const [transition, setTransition] = useState(null);
  const [newRevisionTarget, setNewRevisionTarget] = useState(null);
  const [loading, setLoading] = useState(true);
  const [initialized, setInitialized] = useState(false);
  const [view, setView] = useState(DEFAULT_PORTFOLIO_VIEW);
  const [exporting, setExporting] = useState(() => new Set());
  const [toast, setToast] = useState(null);
  const mountedRef = useRef(false);
  const requestsRef = useRef(new Set());
  const loadControllerRef = useRef(null);
  const historyControllerRef = useRef(null);
  const exportingRef = useRef(new Set());
  const pageErrorRef = useRef(null);
  const reducedMotion = useReducedMotion();
  const [saving, setSaving] = useState(false);
  // Erros por superfície: o da página nunca aparece dentro de um diálogo e vice-versa.
  const [loadError, setLoadError] = useState('');
  const [pageError, setPageError] = useState(null);
  const [dialogError, setDialogError] = useState('');
  const busy = loading || saving;
  const summary = useMemo(() => resumoCarteira(budgets), [budgets]);
  const counts = useMemo(() => contarFiltrosCarteira(budgets), [budgets]);
  const deferredQuery = useDeferredValue(view.query);
  const visibleBudgets = useMemo(
    () => filtrarCarteira(budgets, { busca: deferredQuery, situacao: view.filter, ordem: view.order }),
    [budgets, deferredQuery, view.filter, view.order],
  );
  const filtersActive = view.query.trim() !== '' || view.filter !== 'todos';
  const { canEdit, canTransition } = useMemo(() => resolveOrcamentoCapabilities(permissions), [permissions]);

  const notifySuccess = useCallback((message) => setToast({ id: Date.now(), message }), []);
  const dismissToast = useCallback(() => setToast(null), []);

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
    setLoadError('');
    setPageError((current) => (current?.source === 'load' ? null : current));
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
      const message = requestError.message || 'Não foi possível carregar os orçamentos.';
      setLoadError(message);
      setPageError({ message, retry: () => load(), source: 'load', title: 'Não foi possível atualizar a carteira' });
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
      historyControllerRef.current?.abort();
      requestsRef.current.forEach((controller) => controller.abort());
      requestsRef.current.clear();
    };
  }, [load]);

  // O alerta da página recebe foco para ser lido e ficar à vista.
  useEffect(() => {
    if (!pageError) return;
    const node = pageErrorRef.current;
    node?.focus({ preventScroll: true });
    node?.scrollIntoView?.({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'nearest' });
  }, [pageError, reducedMotion]);

  // scope "dialog": o erro fica no diálogo aberto. scope "page": alerta na página, com
  // "Tentar novamente" refazendo só esta operação.
  const runMutation = async (operation, message, { scope = 'page', title } = {}) => {
    const retry = () => runMutation(operation, message, { scope, title });
    setSaving(true);
    if (scope === 'dialog') setDialogError('');
    else setPageError(null);
    try {
      await operation();
      if (!mountedRef.current) return false;
      await load();
      if (!mountedRef.current) return false;
      notifySuccess(message);
      return true;
    } catch (requestError) {
      if (!mountedRef.current || requestError.name === 'AbortError') return false;
      const messageText = requestError.message || 'Não foi possível concluir a operação.';
      if (scope === 'dialog') setDialogError(messageText);
      else setPageError({ message: messageText, retry, source: 'action', title });
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

  const resetCreateForm = () => {
    setCreateForm(createEmptyOrcamentoForm(schema));
    setCreateErrors({});
    setReuseId('');
  };

  const handleCreate = async (event) => {
    event.preventDefault();
    const errors = validateOrcamentoForm(createForm);
    setCreateErrors(errors);
    if (Object.keys(errors).length) return;
    const created = await runMutation(
      () => request('/orcamentos', { body: buildOrcamentoPayload(createForm, { hhDefaults: schema?.hh?.defaults }), method: 'POST' }),
      'Orçamento criado com a revisão 0 em rascunho.',
      { scope: 'dialog' },
    );
    if (!created) return;
    resetCreateForm();
    setCreateOpen(false);
  };

  const openCreate = () => {
    setDialogError('');
    setCreateOpen(true);
  };

  const closeCreate = () => {
    setCreateOpen(false);
    setDialogError('');
  };

  const openCatalog = () => {
    setDialogError('');
    setCatalogOpen(true);
  };

  const closeCatalog = () => {
    setCatalogOpen(false);
    setCatalogDirty(false);
    setConfirmCatalogDiscard(false);
    setDialogError('');
  };

  // Fechar o diálogo desmonta o rascunho do catálogo: com alterações pendentes, confirma antes.
  const requestCloseCatalog = () => {
    if (catalogDirty) setConfirmCatalogDiscard(true);
    else closeCatalog();
  };

  const openEditor = (budget, revision = budget.revisaoAtual, readOnly = false) => {
    if (!revision) return;
    setDialogError('');
    const editable = canEdit && !readOnly && revision.id === budget.revisaoAtual?.id && revision.situacao === 'rascunho';
    setEditor({ budget, canEdit: editable, revision });
    const next = createRevisaoForm(revision, schema);
    setEditorForm({ ...next, dfp: { ...next.dfp, metadata: { ...next.dfp?.metadata,
      cliente_unidade: next.dfp?.metadata?.cliente_unidade || budget.contratante,
    } } });
    setEditorErrors({});
  };

  const closeEditor = () => {
    setEditor(null);
    setDialogError('');
  };

  const handleSaveRevision = async (event) => {
    event?.preventDefault?.();
    if (!editor?.canEdit) return false;
    const errors = validateRevisaoForm(editorForm);
    setEditorErrors(errors);
    if (Object.keys(errors).length) return false;
    const saved = await runMutation(
      () => request(`/revisoes/${editor.revision.id}`, { body: buildRevisaoPatchPayload(editorForm), method: 'PATCH' }),
      `Revisão ${editor.revision.numero} e snapshot DFP atualizados.`,
      { scope: 'dialog' },
    );
    if (saved) closeEditor();
    return saved;
  };

  const askNewRevision = (budget) => {
    setDialogError('');
    setNewRevisionTarget(budget);
  };

  const cancelNewRevision = () => {
    setNewRevisionTarget(null);
    setDialogError('');
  };

  const confirmNewRevision = async () => {
    const budget = newRevisionTarget;
    if (!budget) return;
    const created = await runMutation(
      () => request(`/orcamentos/${budget.id}/revisoes`, { body: herdarCabecalho(budget.revisaoAtual), method: 'POST' }),
      `Nova revisão criada para ${budget.codigo}; o histórico foi preservado.`,
      { scope: 'dialog' },
    );
    if (created) cancelNewRevision();
  };

  const fetchHistory = useCallback(async (budget) => {
    historyControllerRef.current?.abort();
    const controller = new AbortController();
    historyControllerRef.current = controller;
    setHistory({ budget, entries: [], error: '', status: 'loading' });
    try {
      const payload = await request(`/orcamentos/${budget.id}/historico`, { signal: controller.signal });
      if (!mountedRef.current || controller.signal.aborted) return;
      setHistory((current) => current && current.budget.id === budget.id
        ? { budget, entries: Array.isArray(payload?.historico) ? payload.historico : [], error: '', status: 'ready' }
        : current);
    } catch (err) {
      if (!mountedRef.current || controller.signal.aborted) return;
      setHistory((current) => current && current.budget.id === budget.id
        ? { ...current, error: err.message || 'Não foi possível carregar o histórico.', status: 'error' }
        : current);
    }
  }, [request]);

  const closeHistory = () => {
    historyControllerRef.current?.abort();
    setHistory(null);
  };

  // A planilha vai crua no corpo: o backend só lê e devolve a composição, sem gravar.
  const importHhWorkbook = async (file) => {
    setDialogError('');
    if (file.size > HH_IMPORT_MAX_BYTES) {
      setDialogError('A planilha excede 5 MB.');
      return null;
    }
    try {
      const response = await fetchWithCsrfRecovery(`${endpoint}/hh/importar`, {
        body: file,
        headers: { 'Content-Type': file.type || 'application/octet-stream' },
        method: 'POST',
      }, { csrfToken, apiBase });
      if (!response.ok) throw new Error(await readApiError(response));
      const payload = await response.json();
      notifySuccess(`Planilha “${file.name}” importada. Revise e salve a revisão.`);
      return payload.hh;
    } catch (err) {
      setDialogError(err.message);
      return null;
    }
  };

  // Uma exportação por revisão/formato de cada vez; o botão mostra o progresso.
  const downloadRevision = async (revision, formato, { scope = 'page' } = {}) => {
    const key = `${revision.id}:${formato}`;
    if (exportingRef.current.has(key)) return false;
    exportingRef.current.add(key);
    setExporting(new Set(exportingRef.current));
    if (scope === 'dialog') setDialogError('');
    try {
      const response = await fetch(`${endpoint}/revisoes/${revision.id}/exportar?formato=${formato}`, { credentials: 'same-origin' });
      if (!response.ok) throw new Error(await readApiError(response));
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = url;
      link.download = response.headers.get('Content-Disposition')?.match(/filename="([^"]+)"/)?.[1] || `orcamento.${formato}`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      if (mountedRef.current) notifySuccess(`${formato.toUpperCase()} da revisão ${revision.numero} gerado.`);
      return true;
    } catch (err) {
      if (!mountedRef.current) return false;
      const message = err.message || `Não foi possível exportar o ${formato.toUpperCase()}.`;
      if (scope === 'dialog') setDialogError(message);
      else setPageError({ message, retry: () => downloadRevision(revision, formato), source: 'action', title: `Falha ao exportar ${formato.toUpperCase()}` });
      return false;
    } finally {
      exportingRef.current.delete(key);
      if (mountedRef.current) setExporting(new Set(exportingRef.current));
    }
  };

  const reuseBudget = (id) => {
    setReuseId(id);
    if (!id) return;
    const budget = budgets.find((item) => item.id === id);
    if (!budget?.revisaoAtual) return;
    // O código DFP pertence ao orçamento de origem; mantê-lo faz o backend recusar a criação.
    const base = createRevisaoForm(budget.revisaoAtual, schema);
    setCreateForm({ ...base, contratante: budget.contratante, dfp: stripDerivedIdentity(base.dfp) });
    setCreateErrors({});
  };

  const openTransition = (revision, situation) => {
    setDialogError('');
    setTransition({ revision, situation });
  };

  const cancelTransition = () => {
    setTransition(null);
    setDialogError('');
  };

  const handleConfirmTransition = async (reason) => {
    if (!transition) return;
    const changed = await runMutation(
      () => request(`/revisoes/${transition.revision.id}/situacao`, {
        body: { motivo: reason, situacao: transition.situation }, method: 'POST',
      }),
      `Revisão ${transition.revision.numero} agora está em “${SITUACOES[transition.situation]}”.`,
      { scope: 'dialog' },
    );
    if (changed) cancelTransition();
  };

  const applyView = (patch) => setView((current) => ({ ...current, ...patch }));
  const editorExporting = editor
    ? ['docx', 'pdf'].find((format) => exporting.has(`${editor.revision.id}:${format}`)) || null
    : null;

  return (
    <MotionConfig reducedMotion="user">
    <section className="orc-root" aria-label="Orçamento">
      <AnimatePresence mode="wait" initial={false}>
      {!initialized && loading ? <OrcamentoLoadingScreen key="loading" /> : !initialized ? (
        <motion.div key="initial-error" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <GoFlowWindow className="orc-error-window" icon={CircleAlert} role="alert" title="Não foi possível carregar os orçamentos">
            <p>{loadError}</p>
            <button className="orc-btn orc-btn--primary" onClick={() => load({ initialize: true })} type="button">Tentar novamente</button>
          </GoFlowWindow>
        </motion.div>
      ) : (
      <motion.div key="content" className="orc-content" aria-busy={busy}
        initial={{ opacity: reducedMotion ? 1 : 0 }} animate={{ opacity: 1 }} transition={{ duration: reducedMotion ? 0 : .24 }}>

      <PortfolioHeader budgets={budgets} canEdit={canEdit} filter={view.filter} onCatalog={openCatalog} onCreate={openCreate}
        onFilter={(filter) => applyView({ filter })} summary={summary} />

      {!canEdit && (
        <p className="orc-readonly-note"><History aria-hidden="true" /> Acesso somente leitura: você consulta cada revisão e o histórico, sem alterar os dados.</p>
      )}

      <AnimatePresence initial={false}>
        {pageError && (
          <motion.div animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} initial={{ opacity: 0, y: reducedMotion ? 0 : -6 }} key="page-error">
            <GoFlowWindow
              actions={<button aria-label="Dispensar erro" className="orc-icon-btn" onClick={() => setPageError(null)} type="button"><X aria-hidden="true" /></button>}
              className="orc-error-window"
              icon={CircleAlert}
              ref={pageErrorRef}
              role="alert"
              tabIndex={-1}
              title={pageError.title || 'Não foi possível concluir'}
            >
              <p>{pageError.message}</p>
              {pageError.retry && <button className="orc-btn" disabled={busy} onClick={pageError.retry} type="button">Tentar novamente</button>}
            </GoFlowWindow>
          </motion.div>
        )}
      </AnimatePresence>

      {budgets.length > 0 && (
        <PortfolioToolbar counts={counts} filter={view.filter} onFilter={(filter) => applyView({ filter })}
          onOrder={(order) => applyView({ order })} onQuery={(query) => applyView({ query })} order={view.order} query={view.query} />
      )}

      <p aria-live="polite" className="orc-portfolio-count">
        {loading ? <span className="orc-skeleton orc-skeleton--pill" aria-label="Atualizando carteira" role="img" />
          : filtersActive ? `Mostrando ${visibleBudgets.length} de ${budgets.length} orçamentos` : ''}
      </p>

      {budgets.length === 0 && !loading && (
        <GoFlowWindow className="orc-empty" icon={Calculator} title="Carteira vazia">
          <p>{canEdit ? 'Crie o primeiro orçamento. Ele receberá o código ORC-0001.' : 'Nenhum orçamento foi criado ainda.'}</p>
          {canEdit && <button className="orc-btn orc-btn--primary" onClick={openCreate} type="button"><Plus aria-hidden="true" /> Criar o primeiro orçamento</button>}
        </GoFlowWindow>
      )}

      {budgets.length > 0 && visibleBudgets.length === 0 && (
        <GoFlowWindow className="orc-empty" icon={SearchX} title="Nenhum orçamento encontrado">
          <p>Nenhum orçamento corresponde à busca e aos filtros atuais.</p>
          <button className="orc-btn" onClick={() => setView(DEFAULT_PORTFOLIO_VIEW)} type="button">Limpar filtros</button>
        </GoFlowWindow>
      )}

      {(visibleBudgets.length > 0 || (loading && budgets.length === 0)) && (
        <ul className="orc-portfolio" data-refreshing={loading || undefined}>
          {budgets.length === 0 ? <PortfolioSkeleton /> : (
            <AnimatePresence initial={false} mode="popLayout">
              {visibleBudgets.map((budget, index) => (
                <BudgetCard
                  budget={budget}
                  busy={busy}
                  canEdit={canEdit}
                  canTransition={canTransition}
                  exporting={exporting}
                  index={index}
                  key={budget.id}
                  onExport={(revision, format) => downloadRevision(revision, format)}
                  onHistory={fetchHistory}
                  onNewRevision={askNewRevision}
                  onOpen={openEditor}
                  onTransition={openTransition}
                />
              ))}
            </AnimatePresence>
          )}
        </ul>
      )}

      </motion.div>
      )}
      </AnimatePresence>

      <AnimatePresence>
      {editor && schema && (
        <DfpEditor key={editor.revision.id} budget={editor.budget} catalogo={catalogo} hhSchema={schema.hh} onImportHh={importHhWorkbook}
          exportingFormat={editorExporting}
          onExport={(format) => downloadRevision(editor.revision, format, { scope: 'dialog' })} busy={saving} canEdit={editor.canEdit} errors={editorErrors} form={editorForm} onClose={closeEditor} onDfpChange={(dfp) => setEditorForm((current) => applyDfpChange(current, dfp))} onDfpUpdate={(update) => setEditorForm((current) => applyDfpChange(current, update(current.dfp)))} onHeaderChange={(field, value) => {
          setEditorForm((current) => applyHeaderChange(current, field, value));
          setEditorErrors((current) => {
            if (!current[field]) return current;
            const { [field]: _removed, ...rest } = current;
            return rest;
          });
        }} serverError={dialogError} onSave={handleSaveRevision} revision={editor.revision} schema={editorForm.dfp?.calculation_version === 2 ? schema : legacySchema || schema} />
      )}
      </AnimatePresence>
      <AnimatePresence>
      {createOpen && canEdit && (
        <CreateBudgetDialog budgets={budgets} busy={busy} error={dialogError} errors={createErrors} form={createForm} key="create"
          onChange={updateCreateForm} onClose={closeCreate} onDfpChange={updateCreateDfp} onReset={resetCreateForm}
          onReuse={reuseBudget} onSubmit={handleCreate} reuseId={reuseId} saving={saving} />
      )}
      </AnimatePresence>
      <AnimatePresence>
      {catalogOpen && canEdit && (
        <OrcamentoDialog className="orc-catalog-window" icon={SlidersHorizontal} key="catalog" onClose={requestCloseCatalog} title="Cadastros do orçamento">
          <CatalogoPanel busy={busy} catalogo={catalogo} currentUserId={currentUserId} embedded historico={catalogoHistorico} onDirtyChange={setCatalogDirty}
            onSave={(data) => runMutation(() => request('/catalogo', { body: data, method: 'POST' }), 'Catálogo salvo.', { scope: 'dialog' })} />
          {dialogError && <p className="orc-validation-error" role="alert">{dialogError}</p>}
        </OrcamentoDialog>
      )}
      </AnimatePresence>
      <AnimatePresence>
      {confirmCatalogDiscard && (
        <ConfirmDialog cancelLabel="Continuar editando" confirmLabel="Descartar e fechar" eyebrow="Alterações não salvas" icon={CircleAlert}
          key="catalog-discard" onCancel={() => setConfirmCatalogDiscard(false)} onConfirm={closeCatalog} title="Descartar alterações dos cadastros?" tone="danger">
          <p>As mudanças em funções, itens ou custo administrativo ainda não foram salvas. Ao fechar, elas serão perdidas.</p>
        </ConfirmDialog>
      )}
      </AnimatePresence>
      <AnimatePresence>
      {transition && <TransitionDialog key={transition.revision.id} busy={saving} label={SITUACOES[transition.situation]} onCancel={cancelTransition} onConfirm={handleConfirmTransition} revision={transition.revision} serverError={dialogError} />}
      </AnimatePresence>
      <AnimatePresence>
      {newRevisionTarget && (
        <ConfirmDialog
          busy={saving}
          confirmLabel="Criar revisão"
          error={dialogError}
          eyebrow={newRevisionTarget.codigo}
          icon={GitBranch}
          key={`new-revision-${newRevisionTarget.id}`}
          onCancel={cancelNewRevision}
          onConfirm={confirmNewRevision}
          title="Criar nova revisão"
        >
          <p>
            A revisão R{newRevisionTarget.revisaoAtual?.numero ?? 0} de <strong>{newRevisionTarget.contratante}</strong> fica preservada
            no histórico. A nova revisão começa em rascunho e herda o cabeçalho e a composição atuais.
          </p>
        </ConfirmDialog>
      )}
      </AnimatePresence>
      <AnimatePresence>
      {history && <HistoryDrawer currentUserId={currentUserId} key={`history-${history.budget.id}`} onClose={closeHistory} onRetry={() => fetchHistory(history.budget)} state={history} />}
      </AnimatePresence>
      <OrcamentoToast onDismiss={dismissToast} toast={toast} />
    </section>
    </MotionConfig>
  );
}
