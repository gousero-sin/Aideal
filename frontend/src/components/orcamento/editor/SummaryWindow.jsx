import React, { useEffect, useId, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { AlertTriangle, BadgeDollarSign, ChevronDown, ChevronUp } from 'lucide-react';
import { GoFlowWindow } from '../../goflow-window';
import AnimatedValue from './AnimatedValue';
import { changedSummaryEntries } from './editorState';
import { formatMoney } from './editorShared';

const HIGHLIGHT_MS = 1600;

const signedMoney = (delta) => `${delta > 0 ? '+' : '−'}${formatMoney(Math.abs(delta))}`;

/** Linhas do resumo: números viram moeda animada; textos (percentuais, contagens) ficam fixos. */
export const buildSummaryItems = (summary, hhSummary) => (hhSummary ? [
  ['Colaboradores', hhSummary.colaboradores.toLocaleString('pt-BR')],
  ['Encargos sociais', `${hhSummary.encargos.totalPercent.toLocaleString('pt-BR', { maximumFractionDigits: 4 })}%`],
  ['Total mensal', hhSummary.totalMensal],
  ['Prazo do contrato', `${hhSummary.meses.toLocaleString('pt-BR')} mês(es)`],
  ['Custos diretos no prazo', hhSummary.custosDiretosTotal],
  ['Despesas indiretas no prazo', hhSummary.custosIndiretosTotal],
  ['Lucro no prazo', hhSummary.lucroTotal],
  ['Tributos', `${hhSummary.aliquotaImpostosTotal.toLocaleString('pt-BR')}%`],
] : [
  ['Custos diretos', summary.custosDiretosTotal],
  ['Custos indiretos', summary.custosIndiretosTotal],
  ['Lucro / BDI', summary.lucroTotal],
  ['Custos totais', summary.custosTotais],
  ['Impostos', `${summary.aliquotaImpostosTotal.toLocaleString('pt-BR')}%`],
  ['Preço por área', Number(summary.precoPorArea || 0)],
  ['Valor dia / colaborador', Number(summary.valorDiaColaborador || 0)],
]);

/** Destaca por alguns instantes as linhas cujo valor mudou desde a última renderização. */
function useChangedEntries(entries) {
  const previous = useRef(null);
  const timer = useRef(null);
  const [changed, setChanged] = useState(() => new Map());
  const signature = JSON.stringify(entries);
  useEffect(() => () => clearTimeout(timer.current), []);
  useEffect(() => {
    const next = JSON.parse(signature);
    const diff = changedSummaryEntries(previous.current, next);
    previous.current = next;
    if (!diff.length) return;
    setChanged(new Map(diff));
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setChanged(new Map()), HIGHLIGHT_MS);
  }, [signature]);
  return changed;
}

export default function SummaryWindow({ hhSummary, summary, warnings }) {
  const reducedMotion = useReducedMotion();
  const [collapsed, setCollapsed] = useState(false);
  const contentId = useId();
  const items = useMemo(() => buildSummaryItems(summary, hhSummary), [summary, hhSummary]);
  const totalLabel = hhSummary ? 'Total estimado do contrato (HH)' : 'Preço total de faturamento';
  const changed = useChangedEntries([...items, [totalLabel, summary.precoTotalFaturamento]]);
  const totalDelta = changed.get(totalLabel);

  return (
    <GoFlowWindow
      actions={(
        <button
          aria-controls={contentId}
          aria-expanded={!collapsed}
          className="orc-btn orc-btn--compact"
          onClick={() => setCollapsed((current) => !current)}
          type="button"
        >
          {collapsed ? <ChevronDown aria-hidden="true" /> : <ChevronUp aria-hidden="true" />}
          {collapsed ? 'Mostrar detalhes' : 'Recolher detalhes'}
        </button>
      )}
      className={`orc-summary-window ${collapsed ? 'is-collapsed' : ''}`}
      eyebrow="Cálculo em tempo real"
      icon={BadgeDollarSign}
      id="orc-section-summary"
      title="Impostos e resumo"
    >
      {warnings.length > 0 && (
        <ul className="orc-summary-warnings" role="status" aria-label="Avisos do cálculo">
          {warnings.map((warning) => (
            <li key={warning}><AlertTriangle aria-hidden="true" /><span>{warning}</span></li>
          ))}
        </ul>
      )}
      <dl className="orc-summary-grid" id={contentId}>
        <AnimatePresence initial={false}>
          {!collapsed && items.map(([label, value]) => {
            const delta = changed.get(label);
            return (
              <motion.div
                animate={{ opacity: 1, y: 0 }}
                className={delta !== undefined ? 'is-changed' : undefined}
                exit={{ opacity: 0, y: -4 }}
                initial={{ opacity: 0, y: -4 }}
                key={label}
                transition={{ duration: reducedMotion ? 0 : 0.2 }}
              >
                <dt>{label}</dt>
                <dd>{typeof value === 'number' ? <AnimatedValue value={value} /> : value}</dd>
                {delta !== undefined && <span className="orc-summary-delta" data-trend={delta > 0 ? 'up' : 'down'}>{signedMoney(delta)}</span>}
              </motion.div>
            );
          })}
        </AnimatePresence>
        <div className={`orc-summary-total ${totalDelta !== undefined ? 'is-changed' : ''}`}>
          <dt>{totalLabel}</dt>
          <dd><AnimatedValue value={summary.precoTotalFaturamento} /></dd>
          {totalDelta !== undefined && <span className="orc-summary-delta" data-trend={totalDelta > 0 ? 'up' : 'down'}>{signedMoney(totalDelta)}</span>}
        </div>
      </dl>
    </GoFlowWindow>
  );
}
