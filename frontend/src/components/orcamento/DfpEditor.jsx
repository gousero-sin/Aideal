import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { AlertTriangle, Calculator, FileText } from 'lucide-react';
import { useHhSections } from './HhEditor';
import { collectHhWarnings, mesesDoPrazo } from './hhModel';
import useOrcamentoDialog from './useOrcamentoDialog';
import ConfirmDialog from './ConfirmDialog';
import { backdropMotion, springSoft, windowMotion } from './orcamentoMotion';
import { GoFlowWindow } from '../goflow-window';
import {
  applyDfpChange,
  collectOrcamentoWarnings,
  computeDfpSummary,
  getSchemaSections,
} from '../orcamentoModel';
import { CatalogContext } from './editor/editorShared';
import { HeaderFields } from './editor/FieldInputs';
import SchemaSection from './editor/SchemaSection';
import SummaryWindow from './editor/SummaryWindow';
import EditorTitlebar from './editor/EditorTitlebar';
import EditorFooter from './editor/EditorFooter';
import { EditorSectionNav, MobileSectionNav } from './editor/EditorNav';
import { firstIssueIn, useActiveSection, useSectionIssues } from './editor/useActiveSection';
import {
  isSaveShortcut,
  rebaseIfClean,
  serializeEditorForm,
  shouldBlockEnterSubmit,
} from './editor/editorState';
import '../../styles/orcamento-editor.css';

export { LocationHeaderField, LocationSelectors } from './editor/FieldInputs';

const SECTION_EYEBROWS = {
  fields: 'Premissas do orçamento',
  'labor-table': 'Equipe e encargos',
  'cost-table': 'Composição de custos',
  'percent-groups': 'Tributos e margem',
};
const cloneJson = (value) => JSON.parse(JSON.stringify(value));

// Arquivo solto fora da área de importação não deve fazer o navegador abrir a planilha.
const preventFileDrop = (event) => {
  if ([...(event.dataTransfer?.types || [])].includes('Files')) event.preventDefault();
};

/** Enter em uma célula leva ao mesmo campo da linha seguinte (Shift+Enter: anterior). */
const focusSiblingRowInput = (event) => {
  const cell = event.target.closest('td, th');
  const row = cell?.parentElement;
  if (!cell || row?.tagName !== 'TR' || !row.parentElement || row.parentElement.tagName !== 'TBODY') return;
  const index = [...row.children].indexOf(cell);
  const step = (current) => (event.shiftKey ? current.previousElementSibling : current.nextElementSibling);
  for (let sibling = step(row); sibling; sibling = step(sibling)) {
    const target = sibling.children[index]?.querySelector('input:not([disabled]):not([readonly])');
    if (target) {
      target.focus();
      try { target.select(); } catch { /* alguns tipos não aceitam seleção */ }
      return;
    }
  }
};

export default function DfpEditor({
  budget,
  catalogo,
  onExport,
  serverError,
  busy,
  canEdit,
  errors,
  exportingFormat,
  form,
  hhSchema,
  onClose,
  onDfpChange,
  onDfpUpdate,
  onHeaderChange,
  onImportHh,
  onSave,
  revision,
  schema,
}) {
  const closeButtonRef = useRef(null);
  const saveButtonRef = useRef(null);
  const formRef = useRef(null);
  const mountedRef = useRef(true);
  const scrollPosition = useRef(0);
  const tableScrollPositions = useRef({});
  const reducedMotion = useReducedMotion();
  const [minimized, setMinimized] = useState(false);
  const [maximized, setMaximized] = useState(true);
  const [importingHh, setImportingHh] = useState(null);
  const [exporting, setExporting] = useState(null);
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const pendingIssueFocus = useRef(false);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  // Snapshot do formulário ao abrir: base do aviso de alterações não salvas.
  const baselineRef = useRef(null);
  if (baselineRef.current === null) baselineRef.current = serializeEditorForm(form);
  const serializedForm = useMemo(() => serializeEditorForm(form), [form]);
  const dirty = canEdit && serializedForm !== baselineRef.current;

  const isHh = form.modalidade === 'HH';
  const hhDefaults = hhSchema?.defaults;
  const editable = canEdit && !busy;
  // Modalidade HH abre a planilha de composição por Homem-Hora; sem composição salva, uma
  // revisão editável parte do modelo padrão (a planilha de referência) e uma somente leitura
  // não finge ter valores que nunca foram gravados.
  // Revisão que já era HH e tem preço DFP (criada antes da composição HH) não troca de valor
  // sozinha: o modelo de exemplo só entra por ação explícita. Orçamento novo, sem preço DFP, ou
  // que acabou de mudar para HH parte direto do modelo.
  const dfpSalvoTemPreco = useMemo(
    () => computeDfpSummary(revision?.dfp || {}).precoTotalFaturamento > 0,
    [revision],
  );
  const semeiaSozinho = revision?.modalidade !== 'HH' || !dfpSalvoTemPreco;
  const hh = form.dfp?.hh || (canEdit && semeiaSozinho ? hhDefaults : null);
  const carregarModeloHh = () => onDfpChange({ ...form.dfp, hh: cloneJson(hhDefaults) });
  useEffect(() => {
    if (isHh && canEdit && semeiaSozinho && !form.dfp?.hh && hhDefaults) {
      const nextDfp = { ...form.dfp, hh: cloneJson(hhDefaults) };
      // A semeadura automática não é alteração do usuário: se o formulário estava limpo,
      // o modelo semeado passa a ser a nova base.
      baselineRef.current = rebaseIfClean(baselineRef.current, form, applyDfpChange(form, nextDfp));
      onDfpChange(nextDfp);
    }
  }, [isHh, canEdit, semeiaSozinho, form, hhDefaults, onDfpChange]);
  const changeHh = (next) => onDfpChange({ ...form.dfp, hh: next });
  const importHh = async (file) => {
    if (!onImportHh) return;
    setImportingHh(file?.name || 'planilha');
    try {
      const imported = await onImportHh(file);
      // Aplica sobre o estado atual: o usuário pode ter editado o cabeçalho durante o upload.
      if (imported && onDfpUpdate) onDfpUpdate((dfp) => ({ ...dfp, hh: imported }));
      else if (imported) changeHh(imported);
    } finally {
      if (mountedRef.current) setImportingHh(null);
    }
  };
  const hhView = useHhSections({
    disabled: !editable,
    hh: hh || hhDefaults,
    importing: importingHh,
    onChange: changeHh,
    onImport: importHh,
    prazoMeses: mesesDoPrazo(form.prazoExecucaoDias),
  });
  const showHh = isHh && Boolean(hh);
  const schemaSections = getSchemaSections(schema);
  const sections = showHh ? hhView.sections : schemaSections;

  const hhSummary = showHh ? hhView.summary : null;
  const dfpSummary = useMemo(() => computeDfpSummary(form.dfp), [form.dfp]);
  const summary = hhSummary || dfpSummary;
  const warnings = useMemo(
    () => (showHh ? collectHhWarnings(hh) : collectOrcamentoWarnings(form.dfp, { prazoDias: form.prazoExecucaoDias })),
    [form.dfp, form.prazoExecucaoDias, hh, showHh],
  );
  const totalLabel = hhSummary ? 'Total estimado do contrato (HH)' : 'Preço total de faturamento';

  const requestClose = useCallback(() => {
    if (busy) return;
    if (dirty) setConfirmDiscard(true);
    else onClose();
  }, [busy, dirty, onClose]);
  const dialogRef = useOrcamentoDialog({ busy, initialFocusRef: closeButtonRef, onClose: requestClose });

  const navigation = [
    { id: 'orc-section-header', title: 'Cabeçalho' },
    ...sections.map((section) => ({ id: `orc-section-${section.id}`, title: section.title })),
    { id: 'orc-section-summary', title: 'Impostos e resumo' },
  ];
  const { active: activeSection, navigateTo } = useActiveSection(formRef, {
    enabled: !minimized,
    initial: 'orc-section-header',
    reducedMotion,
    watch: `${minimized}|${showHh}|${sections.length}`,
  });
  const issues = useSectionIssues(formRef, { enabled: attempted && !minimized });
  const issueCount = Object.values(issues).reduce((sum, count) => sum + count, 0);

  const toggleMinimized = () => {
    if (!minimized) {
      scrollPosition.current = formRef.current?.scrollTop || 0;
      const tables = [...(formRef.current?.querySelectorAll('.orc-table-scroll') || [])];
      tableScrollPositions.current = Object.fromEntries(tables.map((table) => [
        table.dataset.scrollKey,
        { left: table.scrollLeft, top: table.scrollTop },
      ]));
    }
    setMinimized((current) => !current);
  };

  useLayoutEffect(() => {
    if (minimized || !formRef.current) return;
    formRef.current.scrollTop = scrollPosition.current;
    formRef.current.querySelectorAll('.orc-table-scroll').forEach((table) => {
      const position = tableScrollPositions.current[table.dataset.scrollKey];
      if (position) {
        table.scrollLeft = position.left;
        table.scrollTop = position.top;
      }
    });
  }, [minimized]);

  // Depois de salvar com erro de validação, leva o usuário ao primeiro campo pendente.
  useEffect(() => {
    if (!pendingIssueFocus.current) return;
    pendingIssueFocus.current = false;
    if (!Object.keys(errors || {}).length) return;
    const target = firstIssueIn(formRef.current);
    if (!target) return;
    target.scrollIntoView({ behavior: reducedMotion ? 'instant' : 'smooth', block: 'center' });
    target.focus({ preventScroll: true });
  }, [errors, reducedMotion]);

  // Ctrl/Cmd+S salva a revisão (o navegador não abre "Salvar página").
  useEffect(() => {
    const handleKey = (event) => {
      if (!isSaveShortcut(event)) return;
      event.preventDefault();
      if (confirmDiscard || !canEdit || busy || minimized) return;
      formRef.current?.requestSubmit(saveButtonRef.current || undefined);
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [busy, canEdit, confirmDiscard, minimized]);

  useEffect(() => {
    if (!dirty) return undefined;
    const warnBeforeUnload = (event) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', warnBeforeUnload);
    return () => window.removeEventListener('beforeunload', warnBeforeUnload);
  }, [dirty]);

  const handleSubmit = (event) => {
    setAttempted(true);
    pendingIssueFocus.current = true;
    onSave(event);
  };
  const handleFormKeyDown = (event) => {
    if (!shouldBlockEnterSubmit(event)) return;
    event.preventDefault();
    focusSiblingRowInput(event);
  };
  const handleExport = async (format) => {
    if (!onExport || exporting || exportingFormat || dirty) return;
    setExporting(format);
    try {
      await onExport(format);
    } finally {
      if (mountedRef.current) setExporting(null);
    }
  };

  const layoutKey = `${minimized}-${maximized}`;
  const dialogMotion = windowMotion(reducedMotion);

  return (
    <CatalogContext.Provider value={catalogo || {}}>
      <motion.div
        {...backdropMotion(reducedMotion)}
        className="orc-editor-layer"
        onDragOver={preventFileDrop}
        onDrop={preventFileDrop}
        role="presentation"
      >
        <motion.div
          {...dialogMotion}
          layout={!reducedMotion}
          layoutDependency={layoutKey}
          transition={{ ...dialogMotion.transition, layout: reducedMotion ? { duration: 0 } : springSoft }}
          ref={dialogRef}
          tabIndex={-1}
          aria-describedby="orc-editor-mode"
          aria-label={budget.contratante}
          aria-modal="true"
          className={`orc-editor-dialog ${minimized ? 'is-minimized' : ''} ${maximized ? 'is-maximized' : ''} ${dirty ? 'is-dirty' : ''}`}
          data-orc-dialog-layer="true"
          role="dialog"
        >
          <EditorTitlebar
            budget={budget}
            busy={busy}
            canEdit={canEdit}
            closeButtonRef={closeButtonRef}
            dirty={dirty}
            layoutKey={layoutKey}
            maximized={maximized}
            minimized={minimized}
            onClose={requestClose}
            onToggleMaximized={() => setMaximized((current) => !current)}
            onToggleMinimized={toggleMinimized}
            reducedMotion={reducedMotion}
            revision={revision}
          />

          {!minimized && <MobileSectionNav active={activeSection} issues={issues} items={navigation} onNavigate={navigateTo} />}

          {!minimized && <div className="orc-editor-layout">
            <EditorSectionNav active={activeSection} issues={issues} items={navigation} onNavigate={navigateTo} />

            <form
              className="orc-editor-form"
              onInvalidCapture={() => setAttempted(true)}
              onKeyDown={handleFormKeyDown}
              onSubmit={handleSubmit}
              ref={formRef}
            >
              {showHh && <p className="orc-note orc-note--hh">Modalidade HH: composição por Homem-Hora (salário + encargos, custos mensais por pessoa, BDI e tributos), como na planilha de composição de custos. {!revision?.dfp?.hh && 'Modelo padrão da planilha carregado — ajuste e salve a revisão para gravá-lo.'}</p>}
              {isHh && !showHh && (
                <p className="orc-note">
                  Esta revisão está na modalidade HH, mas o preço salvo vem da composição DFP abaixo.{' '}
                  {canEdit && hhDefaults && <button className="orc-btn orc-btn--compact" disabled={busy} type="button" onClick={carregarModeloHh}>Iniciar composição HH com o modelo padrão</button>}
                </p>
              )}
              {!showHh && form.dfp?.calculation_version !== 2 && <p className="orc-note">Revisão com regras anteriores à atualização. Seus cálculos históricos foram preservados.</p>}
              {!showHh && form.dfp?.calculation_version === 2 && <p className="orc-note">Perfil de compatibilidade em validação. Confirme dias, mobilização, jornadas, incidência de horas extras e descontos conforme a regra comercial aprovada para este orçamento.</p>}

              <GoFlowWindow eyebrow="Dados contratuais" icon={FileText} id="orc-section-header" title="Cabeçalho">
                <HeaderFields disabled={!canEdit || busy} errors={errors} form={form} onChange={onHeaderChange} onDfpChange={onDfpChange} />
                {errors.dfp && <p className="orc-validation-error" role="alert" tabIndex={-1}>{errors.dfp}</p>}
              </GoFlowWindow>

              {showHh && hhView.sections.map((section) => (
                <GoFlowWindow eyebrow={section.eyebrow} icon={Calculator} id={`orc-section-${section.id}`} key={section.id} title={section.title}>
                  {section.content}
                </GoFlowWindow>
              ))}

              {!showHh && schemaSections.map((section) => (
                <GoFlowWindow
                  eyebrow={SECTION_EYEBROWS[section.kind] || 'Composição de preços'}
                  icon={Calculator}
                  id={`orc-section-${section.id}`}
                  key={section.id}
                  title={section.title}
                >
                  <SchemaSection
                    disabled={!canEdit || busy}
                    dfp={form.dfp}
                    onChange={onDfpChange}
                    schema={schema}
                    section={section}
                  />
                </GoFlowWindow>
              ))}

              <SummaryWindow hhSummary={hhSummary} summary={summary} warnings={warnings} />

              <EditorFooter
                busy={busy}
                canEdit={canEdit}
                dirty={dirty}
                exporting={exportingFormat || exporting}
                issueCount={issueCount}
                onClose={requestClose}
                onExport={handleExport}
                saveButtonRef={saveButtonRef}
                serverError={serverError}
                total={summary.precoTotalFaturamento}
                totalLabel={totalLabel}
              />
            </form>
          </div>}
        </motion.div>
      </motion.div>

      <AnimatePresence>
        {confirmDiscard && (
          <ConfirmDialog
            cancelLabel="Continuar editando"
            confirmLabel="Descartar e fechar"
            eyebrow="Alterações não salvas"
            icon={AlertTriangle}
            onCancel={() => setConfirmDiscard(false)}
            onConfirm={() => { setConfirmDiscard(false); onClose(); }}
            title="Descartar alterações?"
            tone="danger"
          >
            <p>As mudanças feitas na revisão {revision.numero} de {budget.contratante} ainda não foram salvas. Ao fechar, elas serão perdidas.</p>
          </ConfirmDialog>
        )}
      </AnimatePresence>
    </CatalogContext.Provider>
  );
}
