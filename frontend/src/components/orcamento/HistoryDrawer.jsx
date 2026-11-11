import React, { useMemo, useRef } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { ArrowRight, CircleAlert, FilePlus2, GitCommitHorizontal, History, PencilLine, RotateCcw, X } from 'lucide-react';
import useOrcamentoDialog, { closeOnBackdrop } from './useOrcamentoDialog';
import { backdropMotion, listItemMotion, springSoft } from './orcamentoMotion';
import { resumirEventoHistorico, rotuloResponsavel } from '../orcamentoModel';

const ICONES = Object.freeze({ criacao: FilePlus2, edicao: PencilLine, situacao: GitCommitHorizontal });
const formatInstant = (value) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
};

function drawerMotion(reducedMotion) {
  return {
    initial: { x: reducedMotion ? 0 : '100%', opacity: reducedMotion ? 0 : 1 },
    animate: { x: 0, opacity: 1 },
    exit: { x: reducedMotion ? 0 : '100%', opacity: reducedMotion ? 0 : 1, transition: { duration: reducedMotion ? 0 : 0.2 } },
    transition: reducedMotion ? { duration: 0 } : springSoft,
  };
}

function TimelineEntry({ entry, budget, currentUserId, index, reducedMotion }) {
  const resumo = resumirEventoHistorico(entry);
  const revisao = budget.revisoes.find((item) => item.id === entry.revisao_id);
  const Icon = ICONES[resumo.tipo] || History;
  return (
    <motion.li className="orc-timeline__item" data-tipo={resumo.tipo} {...listItemMotion(reducedMotion, index)}>
      <span className="orc-timeline__dot" aria-hidden="true"><Icon /></span>
      <div className="orc-timeline__body">
        <div className="orc-timeline__head">
          <strong>{resumo.titulo}</strong>
          <span className="orc-revision-tag">R{revisao?.numero ?? '?'}</span>
        </div>
        <p className="orc-timeline__meta">
          <time dateTime={entry.created_at}>{formatInstant(entry.created_at)}</time>
          <span aria-hidden="true">·</span>
          <span>{rotuloResponsavel(entry.responsavel_user_id, currentUserId)}</span>
        </p>
        {resumo.tipo === 'situacao' && (resumo.de || resumo.para) && (
          <p className="orc-timeline__transition">
            <span>{resumo.de || '—'}</span><ArrowRight aria-hidden="true" /><span className="orc-visually-hidden">para</span><span>{resumo.para || '—'}</span>
          </p>
        )}
        {resumo.motivo && <p className="orc-timeline__reason">“{resumo.motivo}”</p>}
        {resumo.tipo === 'edicao' && (resumo.campos.length ? (
          <ul className="orc-timeline__fields" aria-label="Campos alterados">
            {resumo.campos.map((campo) => <li key={campo}>{campo}</li>)}
          </ul>
        ) : <p className="orc-timeline__reason">Salvo sem alterações nos campos.</p>)}
      </div>
    </motion.li>
  );
}

/**
 * Gaveta lateral com a linha do tempo de edição. `state` vem do painel:
 * { budget, status: 'loading' | 'ready' | 'error', entries, error }.
 */
export default function HistoryDrawer({ currentUserId, onClose, onRetry, state }) {
  const reducedMotion = useReducedMotion();
  const closeRef = useRef(null);
  const dialogRef = useOrcamentoDialog({ busy: false, initialFocusRef: closeRef, onClose });
  const { budget, entries = [], error, status } = state;
  const ordered = useMemo(() => [...entries].reverse(), [entries]);
  const titleId = `orc-history-title-${budget.id}`;

  return (
    <motion.div
      {...backdropMotion(reducedMotion)}
      className="orc-dialog-layer orc-drawer-layer"
      data-orc-dialog-layer="true"
      onClick={closeOnBackdrop(false, onClose)}
      ref={dialogRef}
      tabIndex={-1}
    >
      <motion.aside
        {...drawerMotion(reducedMotion)}
        aria-busy={status === 'loading'}
        aria-labelledby={titleId}
        aria-modal="true"
        className="orc-drawer"
        role="dialog"
      >
        <header className="orc-drawer__bar">
          <span className="goflow-window__icon" aria-hidden="true"><History /></span>
          <div>
            <span className="goflow-window__eyebrow">{budget.codigo} · {budget.contratante}</span>
            <h2 className="goflow-window__title" id={titleId}>Histórico de edição</h2>
          </div>
          <button aria-label="Fechar histórico" className="orc-icon-btn" onClick={onClose} ref={closeRef} type="button"><X aria-hidden="true" /></button>
        </header>
        <div className="orc-drawer__content">
          {status === 'loading' && (
            <ul className="orc-timeline" aria-label="Carregando histórico">
              {[0, 1, 2].map((key) => <li className="orc-timeline__item orc-skeleton-row" key={key}><span className="orc-skeleton orc-skeleton--dot" /><span className="orc-skeleton orc-skeleton--line" /></li>)}
            </ul>
          )}
          {status === 'error' && (
            <div className="orc-validation-error orc-drawer__error" role="alert">
              <p><CircleAlert aria-hidden="true" /> {error || 'Não foi possível carregar o histórico.'}</p>
              <button className="orc-btn orc-btn--compact" onClick={onRetry} type="button"><RotateCcw aria-hidden="true" /> Tentar novamente</button>
            </div>
          )}
          {status === 'ready' && ordered.length === 0 && (
            <p className="orc-note">Sem eventos registrados. Revisões anteriores à trilha de auditoria não têm histórico.</p>
          )}
          {status === 'ready' && ordered.length > 0 && (
            <ol className="orc-timeline" aria-label={`${ordered.length} evento(s), do mais recente ao mais antigo`}>
              {ordered.map((entry, index) => (
                <TimelineEntry budget={budget} currentUserId={currentUserId} entry={entry} index={index} key={entry.id || `${entry.created_at}-${index}`} reducedMotion={reducedMotion} />
              ))}
            </ol>
          )}
        </div>
      </motion.aside>
    </motion.div>
  );
}
