import React, { forwardRef, useId, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import {
  ArrowUpRight, Calculator, ChevronDown, Download, GitBranch, History, Loader2, Lock, Pencil, Send,
} from 'lucide-react';
import { GoFlowWindow } from '../goflow-window';
import { SITUACOES, limitarRevisoesVisiveis, transicoesDisponiveis } from '../orcamentoModel';
import { listItemMotion, springSoft } from './orcamentoMotion';

const MAX_REVISION_CHIPS = 4;
const formatMoney = (value) => Number(value || 0).toLocaleString('pt-BR', {
  style: 'currency', currency: 'BRL', maximumFractionDigits: 0,
});
const formatDate = (iso) => (iso ? new Date(`${iso}T00:00:00`).toLocaleDateString('pt-BR') : null);
const stop = (event) => event.stopPropagation();

function StatusBadge({ budgetId, revision }) {
  const reducedMotion = useReducedMotion();
  const label = revision.vencida ? 'Vencida' : revision.situacaoLabel;
  return (
    <motion.span
      className="orc-badge"
      data-situacao={revision.situacao}
      data-vencida={revision.vencida || undefined}
      layout={!reducedMotion}
      layoutId={reducedMotion ? undefined : `orc-status-${budgetId}`}
      transition={springSoft}
    >
      <AnimatePresence initial={false} mode="popLayout">
        <motion.span
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: reducedMotion ? 0 : -6 }}
          initial={{ opacity: 0, y: reducedMotion ? 0 : 6 }}
          key={label}
          transition={{ duration: reducedMotion ? 0 : 0.18 }}
        >
          {label}
        </motion.span>
      </AnimatePresence>
    </motion.span>
  );
}

function MetaItem({ label, value }) {
  return <div><dt>{label}</dt><dd title={String(value)}>{value}</dd></div>;
}

const BudgetCard = forwardRef(function BudgetCard({
  budget, busy, canEdit, canTransition, exporting, index, onExport, onHistory, onNewRevision, onOpen, onTransition,
}, ref) {
  const reducedMotion = useReducedMotion();
  const [moreOpen, setMoreOpen] = useState(false);
  const [allRevisions, setAllRevisions] = useState(false);
  const moreId = useId();
  const current = budget.revisaoAtual;
  const transitions = current && canTransition ? transicoesDisponiveis(current.situacao) : [];
  const editable = canEdit && current?.situacao === 'rascunho';
  const readOnly = !editable;
  const { visiveis, ocultas } = allRevisions
    ? { visiveis: budget.revisoes, ocultas: 0 }
    : limitarRevisoesVisiveis(budget.revisoes, current?.id, MAX_REVISION_CHIPS);
  // Rascunho editável: editar é a ação principal. Fora dele, quem edita parte de uma nova revisão.
  const newRevisionIsPrimary = canEdit && !editable;
  const isExporting = (format) => exporting.has(`${current?.id}:${format}`);

  return (
    <GoFlowWindow
      activationLabel={`Abrir ${budget.codigo}, ${budget.contratante}`}
      aria-busy={busy || undefined}
      as="li"
      className="orc-card"
      data-readonly={readOnly || undefined}
      eyebrow={`${budget.codigo}-R${current?.numero ?? 0}`}
      icon={Calculator}
      interactive
      motionProps={{ layout: reducedMotion ? false : 'position', ...listItemMotion(reducedMotion, index) }}
      onActivate={() => onOpen(budget)}
      ref={ref}
      title={budget.contratante}
    >
      <div className="orc-card-summary">
        <div className="orc-card-tags">
          {current && <StatusBadge budgetId={budget.id} revision={current} />}
          {readOnly && <span className="orc-readonly-tag" title="O editor abre somente para consulta"><Lock aria-hidden="true" /> Somente leitura</span>}
        </div>
        <strong title={formatMoney(budget.dfpSummary.precoTotalFaturamento)}>{formatMoney(budget.dfpSummary.precoTotalFaturamento)}</strong>
        <span>{current?.modalidade === 'HH' && current?.dfp?.hh ? 'total estimado do contrato (HH)' : 'preço de faturamento'}</span>
      </div>
      <dl className="orc-card-meta">
        <MetaItem label="Revisão atual" value={current?.numero ?? '—'} />
        <MetaItem label="Modalidade" value={current?.modalidade || 'Pendente'} />
        <MetaItem label="Região da Obra" value={current?.regiao || 'Pendente'} />
        <MetaItem label="Validade" value={formatDate(current?.validoAte) || 'Ainda não emitido'} />
      </dl>
      {budget.cabecalhoPendente.length > 0 && <p className="orc-pending">Cabeçalho pendente: {budget.cabecalhoPendente.join(', ')}.</p>}
      <div aria-label={`Histórico de ${budget.codigo}`} className="orc-history" onClick={stop} role="group">
        <span><History aria-hidden="true" /> Revisões</span>
        <div>
          {visiveis.map((revision) => revision.id === current?.id ? (
            <span aria-current="true" className="orc-revision-chip is-current" key={revision.id} title="Revisão atual">r{revision.numero}</span>
          ) : (
            <button aria-label={`Abrir revisão ${revision.numero} somente leitura`} className="orc-revision-chip" key={revision.id} onClick={() => onOpen(budget, revision, true)} type="button">r{revision.numero}</button>
          ))}
          {ocultas > 0 && (
            <button aria-label={`Mostrar mais ${ocultas} revisões`} className="orc-revision-more" onClick={() => setAllRevisions(true)} type="button">+{ocultas}</button>
          )}
        </div>
      </div>
      <div className="orc-card-actions" onClick={stop}>
        {editable && (
          <button className="orc-btn orc-btn--primary" disabled={busy} onClick={() => onOpen(budget)} type="button">
            <Pencil aria-hidden="true" />{budget.cabecalhoPendente.length ? 'Completar orçamento' : 'Editar orçamento'}
          </button>
        )}
        {newRevisionIsPrimary && (
          <button className="orc-btn orc-btn--primary" disabled={busy} onClick={() => onNewRevision(budget)} type="button"><GitBranch aria-hidden="true" /> Nova revisão</button>
        )}
        {transitions.map((situation) => (
          <button className={`orc-btn ${situation === 'inativo' ? 'orc-btn--quiet' : ''}`} disabled={busy} key={situation} onClick={() => onTransition(current, situation)} type="button">
            {situation === 'emitido' ? <Send aria-hidden="true" /> : <ArrowUpRight aria-hidden="true" />}{SITUACOES[situation]}
          </button>
        ))}
        <button aria-controls={moreId} aria-expanded={moreOpen} className="orc-btn orc-btn--quiet orc-more-toggle" onClick={() => setMoreOpen((open) => !open)} type="button">
          Mais ações <ChevronDown aria-hidden="true" />
        </button>
      </div>
      <AnimatePresence initial={false}>
        {moreOpen && (
          <motion.div
            animate={{ height: 'auto', opacity: 1 }}
            className="orc-card-more"
            exit={{ height: 0, opacity: 0 }}
            id={moreId}
            initial={{ height: 0, opacity: 0 }}
            onClick={stop}
            transition={{ duration: reducedMotion ? 0 : 0.2 }}
          >
            <div className="orc-card-more__row">
              <button className="orc-btn" onClick={() => onHistory(budget)} type="button"><History aria-hidden="true" /> Histórico de edição</button>
              {current && ['docx', 'pdf'].map((format) => (
                <button aria-busy={isExporting(format) || undefined} className="orc-btn" disabled={isExporting(format)} key={format} onClick={() => onExport(current, format)} type="button">
                  {isExporting(format) ? <Loader2 className="orc-spin" aria-hidden="true" /> : <Download aria-hidden="true" />}
                  {isExporting(format) ? `Exportando ${format.toUpperCase()}…` : `Exportar ${format.toUpperCase()}`}
                </button>
              ))}
              {canEdit && !newRevisionIsPrimary && (
                <button className="orc-btn" disabled={busy} onClick={() => onNewRevision(budget)} type="button"><GitBranch aria-hidden="true" /> Nova revisão</button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </GoFlowWindow>
  );
});

export default BudgetCard;
